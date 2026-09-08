#!/usr/bin/env python3
"""
AdGuard Home Client Synchronizer for eero Custom Dashboard
===========================================================
This script automatically pulls all active DHCP/wireless/wired clients
from your local eero Dashboard instance and registers/updates them in
AdGuard Home via its HTTP REST API (`/control/clients/add` or `/control/clients/update`).

Zero external dependencies: uses standard library (urllib, json, argparse, ipaddress).

Usage:
  python adguard_sync.py --eero http://localhost:8085 --adguard http://192.168.4.2:80 --user admin --pass secret
  python adguard_sync.py --drop-ipv6

Or configure via environment variables:
  EERO_DASHBOARD_URL=http://localhost:8085
  ADGUARD_URL=http://192.168.4.2:80
  ADGUARD_USER=admin
  ADGUARD_PASSWORD=secret
  EERO_DROP_IPV6=true
"""

import os
import sys
import json
import base64
import argparse
import ipaddress
import urllib.request
import urllib.error


def is_ipv6_address(val: str) -> bool:
    """Checks if a string is a valid IPv6 address (distinguishing from MAC addresses or hostnames)."""
    if not val or not isinstance(val, str) or ":" not in val:
        return False
    try:
        clean = val.strip().split("%")[0]
        return ipaddress.ip_address(clean).version == 6
    except ValueError:
        return False


def http_request(url: str, method: str = "GET", data: dict = None, user: str = None, password: str = None, timeout: int = 10):
    headers = {"Content-Type": "application/json"}
    if user and password:
        auth_bytes = f"{user}:{password}".encode("utf-8")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        headers["Authorization"] = f"Basic {auth_b64}"

    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_body = response.read().decode("utf-8")
            status = response.status
            return status, res_body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        return e.code, err_body
    except Exception as e:
        raise e


def sync_clients(eero_url: str, adguard_url: str, user: str = None, password: str = None, dry_run: bool = False, drop_ipv6: bool = False):
    eero_url = eero_url.rstrip("/")
    adguard_url = adguard_url.rstrip("/")

    export_url = f"{eero_url}/api/devices/export/adguard"
    if drop_ipv6:
        export_url += "?include_ipv6=false"

    print(f"📡 Fetching client list from eero Dashboard: {export_url} ...")
    if drop_ipv6:
        print("ℹ️ IPv6 exclusion enabled (--drop-ipv6). IPv6 addresses will be omitted and pruned.")

    try:
        status, body = http_request(export_url)
        if status != 200:
            print(f"❌ eero Dashboard returned HTTP {status}: {body}")
            sys.exit(1)
        data = json.loads(body)
    except Exception as e:
        print(f"❌ Failed to reach eero Dashboard: {e}")
        sys.exit(1)

    clients = data.get("clients") or []
    if drop_ipv6:
        for c in clients:
            if "ids" in c and isinstance(c["ids"], list):
                c["ids"] = [cid for cid in c["ids"] if not is_ipv6_address(cid)]

    print(f"✅ Found {len(clients)} active eero clients.")

    if dry_run:
        print("\n🔍 [DRY RUN] Showing devices to sync:")
        for c in clients:
            print(f"  • {c['name']} -> IDs: {c['ids']} (Tags: {c.get('tags', [])})")
        return

    # Check AdGuard Home existing clients to determine ADD vs UPDATE and preserve custom rules
    print(f"🔍 Inspecting existing clients on AdGuard Home: {adguard_url}/control/clients ...")
    existing_by_name = {}
    existing_by_id = {}
    try:
        status, body = http_request(f"{adguard_url}/control/clients", user=user, password=password)
        if status == 200:
            existing_data = json.loads(body) if body else {}
            for ec in (existing_data.get("clients") or []):
                if isinstance(ec, dict):
                    if ec.get("name"):
                        existing_by_name[ec.get("name").lower()] = ec
                    for cid in (ec.get("ids") or []):
                        if cid:
                            existing_by_id[str(cid).strip().lower()] = ec
        elif status == 401:
            print("❌ AdGuard Home returned 401 Unauthorized. Check your username and password.")
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ Could not fetch existing AdGuard clients (will attempt direct upsert): {e}")

    success_count = 0
    for client in clients:
        name = client["name"]
        ids = client.get("ids") or []

        matched_client = None
        for cid in ids:
            matched_client = existing_by_id.get(str(cid).lower())
            if matched_client:
                break
        if not matched_client:
            matched_client = existing_by_name.get(name.lower())

        is_update = matched_client is not None
        endpoint = f"{adguard_url}/control/clients/update" if is_update else f"{adguard_url}/control/clients/add"

        if is_update:
            # Preserve 100% of user's rules, upstreams, and blocked services
            merged_data = dict(matched_client)
            merged_data["name"] = name
            existing_ids = [str(x).strip() for x in (matched_client.get("ids") or []) if str(x).strip()]
            if drop_ipv6:
                existing_ids = [x for x in existing_ids if not is_ipv6_address(x)]

            merged_ids = list(existing_ids)
            existing_ids_lower = {x.lower() for x in existing_ids}
            for i_id in ids:
                if drop_ipv6 and is_ipv6_address(i_id):
                    continue
                if str(i_id).lower() not in existing_ids_lower:
                    merged_ids.append(str(i_id).strip())
                    existing_ids_lower.add(str(i_id).lower())

            if drop_ipv6:
                merged_ids = [x for x in merged_ids if not is_ipv6_address(x)]

            merged_data["ids"] = merged_ids
            if not matched_client.get("tags") and client.get("tags"):
                merged_data["tags"] = client["tags"]

            payload = {
                "name": matched_client.get("name") or name,
                "data": merged_data
            }
        else:
            if drop_ipv6:
                client_copy = dict(client)
                client_copy["ids"] = [x for x in client.get("ids", []) if not is_ipv6_address(x)]
                payload = client_copy
            else:
                payload = client

        try:
            status, res_text = http_request(endpoint, method="POST", data=payload, user=user, password=password)
            if status in (200, 201, 204):
                print(f"  ✅ {'Updated (rules preserved)' if is_update else 'Added'} client '{name}' -> {payload['data']['ids'] if is_update else payload['ids']}")
                success_count += 1
            else:
                print(f"  ⚠️ Warning for '{name}' (HTTP {status}): {res_text.strip()}")
        except Exception as e:
            print(f"  ❌ Error syncing '{name}': {e}")

    print(f"\n🎉 Sync completed: {success_count}/{len(clients)} clients processed on AdGuard Home.")


def main():
    parser = argparse.ArgumentParser(description="Sync eero Dashboard clients into AdGuard Home")
    parser.add_argument("--eero", default=os.getenv("EERO_DASHBOARD_URL", "http://localhost:8085"), help="eero Dashboard URL")
    parser.add_argument("--adguard", default=os.getenv("ADGUARD_URL", "http://192.168.4.2:80"), help="AdGuard Home base URL")
    parser.add_argument("--user", default=os.getenv("ADGUARD_USER", ""), help="AdGuard Home username")
    parser.add_argument("--pass", dest="password", default=os.getenv("ADGUARD_PASSWORD", ""), help="AdGuard Home password")
    parser.add_argument("--dry-run", action="store_true", help="Print devices without pushing to AdGuard")
    parser.add_argument(
        "--drop-ipv6",
        "--no-ipv6",
        dest="drop_ipv6",
        action="store_true",
        default=os.getenv("EERO_DROP_IPV6", "false").lower() in ("1", "true", "yes"),
        help="Exclude/drop IPv6 addresses from synced AdGuard client IDs and prune existing IPv6 from AdGuard"
    )

    args = parser.parse_args()
    sync_clients(
        eero_url=args.eero,
        adguard_url=args.adguard,
        user=args.user,
        password=args.password,
        dry_run=args.dry_run,
        drop_ipv6=args.drop_ipv6
    )


if __name__ == "__main__":
    main()
