#!/usr/bin/env python3
"""
AdGuard Home Client Synchronizer for eero Custom Dashboard
===========================================================
This script automatically pulls all active DHCP/wireless/wired clients
from your local eero Dashboard instance and registers/updates them in
AdGuard Home via its HTTP REST API (`/control/clients/add` or `/control/clients/update`).

Zero external dependencies: uses standard library (urllib, json, argparse).

Usage:
  python adguard_sync.py --eero http://localhost:8085 --adguard http://192.168.4.2:80 --user admin --pass secret

Or configure via environment variables:
  EERO_DASHBOARD_URL=http://localhost:8085
  ADGUARD_URL=http://192.168.4.2:80
  ADGUARD_USER=admin
  ADGUARD_PASSWORD=secret
"""

import os
import sys
import json
import base64
import argparse
import urllib.request
import urllib.error


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


def sync_clients(eero_url: str, adguard_url: str, user: str = None, password: str = None, dry_run: bool = False):
    eero_url = eero_url.rstrip("/")
    adguard_url = adguard_url.rstrip("/")

    print(f"📡 Fetching client list from eero Dashboard: {eero_url}/api/devices/export/adguard ...")
    try:
        status, body = http_request(f"{eero_url}/api/devices/export/adguard")
        if status != 200:
            print(f"❌ eero Dashboard returned HTTP {status}: {body}")
            sys.exit(1)
        data = json.loads(body)
    except Exception as e:
        print(f"❌ Failed to reach eero Dashboard: {e}")
        sys.exit(1)

    clients = data.get("clients") or []
    print(f"✅ Found {len(clients)} active eero clients.")

    if dry_run:
        print("\n🔍 [DRY RUN] Showing devices to sync:")
        for c in clients:
            print(f"  • {c['name']} -> IDs: {c['ids']} (Tags: {c.get('tags', [])})")
        return

    # Check AdGuard Home existing clients to determine ADD vs UPDATE
    print(f"🔍 Inspecting existing clients on AdGuard Home: {adguard_url}/control/clients ...")
    existing_names = set()
    try:
        status, body = http_request(f"{adguard_url}/control/clients", user=user, password=password)
        if status == 200:
            existing_data = json.loads(body) if body else {}
            for ec in (existing_data.get("clients") or []):
                if isinstance(ec, dict) and ec.get("name"):
                    existing_names.add(ec.get("name"))
        elif status == 401:
            print("❌ AdGuard Home returned 401 Unauthorized. Check your username and password.")
            sys.exit(1)
    except Exception as e:
        print(f"⚠️ Could not fetch existing AdGuard clients (will attempt direct upsert): {e}")

    success_count = 0
    for client in clients:
        name = client["name"]
        is_update = name in existing_names
        endpoint = f"{adguard_url}/control/clients/update" if is_update else f"{adguard_url}/control/clients/add"

        payload = client
        if is_update:
            payload = {
                "name": name,
                "data": client
            }

        try:
            status, res_text = http_request(endpoint, method="POST", data=payload, user=user, password=password)
            if status in (200, 201, 204):
                print(f"  ✅ {'Updated' if is_update else 'Added'} client '{name}' -> {client['ids']}")
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

    args = parser.parse_args()
    sync_clients(
        eero_url=args.eero,
        adguard_url=args.adguard,
        user=args.user,
        password=args.password,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
