#!/usr/bin/env python3
"""
Docker Hub Tag Retention and Cleanup Script
===========================================
Maintains a clean tag repository on Docker Hub according to retention policies:
  - Main releases: keeps the latest N versioned build tags (default: 5)
  - Test releases: keeps the latest M versioned test tags (default: 1)
  - Protected tags: 'latest' and 'test' are never deleted
  - Legacy/invalid tags: cleans up any obsolete or test tags (e.g. build number >= 90)

Usage:
  python3 scripts/prune_docker_tags.py [--image IMAGE] [--keep-main 5] [--keep-test 1] [--dry-run]
"""

import os
import sys
import json
import re
import argparse
import urllib.request
import urllib.error
from typing import Dict, List, Tuple, Optional, Any

# Configure UTF-8 stdout for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_IMAGE = "enricoflammini/eero-dashboard"
DEFAULT_KEEP_MAIN = 5
DEFAULT_KEEP_TEST = 1
PROTECTED_TAGS = {"latest", "test"}

# Legacy tags that should always be removed if found
LEGACY_TAGS_TO_REMOVE = {
    "1.5.0",
    "v1.5.0",
    "1.5.0-build.93",
    "1.5.0-build.96",
    "v1.5.0-build.94",
    "v1.5.0-build.97",
    "test-build.92",
    "test-build.95",
    "1.6.0-build.1",
}


def parse_semver_build(tag_name: str) -> Optional[Tuple[int, int, int, int]]:
    """Parse tag format '<major>.<minor>.<patch>-build.<build_num>'."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)-build\.(\d+)$", tag_name)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return None


def parse_semver_test(tag_name: str) -> Optional[Tuple[int, int, int, int]]:
    """Parse tag format '<major>.<minor>.<patch>-test.<build_num>' or legacy 'test-build.<num>'."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)-test\.(\d+)$", tag_name)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    m_legacy = re.match(r"^test-build\.(\d+)$", tag_name)
    if m_legacy:
        return (0, 0, 0, int(m_legacy.group(1)))
    return None


def fetch_all_tags(image_name: str) -> List[Dict[str, Any]]:
    """Fetch all tags for a repository from Docker Hub API v2, handling pagination."""
    all_tags: List[Dict[str, Any]] = []
    url: Optional[str] = f"https://hub.docker.com/v2/repositories/{image_name}/tags?page_size=100"

    while url:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "DockerTagPruner/1.0",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                all_tags.extend(results)
                url = data.get("next")
        except Exception as e:
            print(f"[WARN] Impossibile recuperare i tag da {url}: {e}", file=sys.stderr)
            break

    return all_tags


def get_dockerhub_token(username: Optional[str], token: Optional[str]) -> Optional[str]:
    """Obtain a JWT token from Docker Hub API v2."""
    if not username or not token:
        return None

    login_url = "https://hub.docker.com/v2/users/login/"
    payload = json.dumps({"username": username, "password": token}).encode("utf-8")
    req = urllib.request.Request(
        login_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "DockerTagPruner/1.0"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("token")
    except Exception as e:
        print(f"[WARN] Login a Docker Hub fallito per utente '{username}': {e}", file=sys.stderr)
        return None


def delete_dockerhub_tag(image_name: str, tag_name: str, jwt_token: str, dry_run: bool = False) -> bool:
    """Delete a tag from Docker Hub via API v2."""
    if dry_run:
        print(f"[DRY-RUN] Eliminazione simulata tag: {tag_name}")
        return True

    del_url = f"https://hub.docker.com/v2/repositories/{image_name}/tags/{tag_name}/"
    req = urllib.request.Request(
        del_url,
        headers={
            "Authorization": f"JWT {jwt_token}",
            "User-Agent": "DockerTagPruner/1.0",
        },
        method="DELETE",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status in (200, 204):
                print(f"[PRUNE] Tag '{tag_name}' eliminato con successo da Docker Hub.")
                return True
            else:
                print(f"[WARN] Risposta inattesa per tag '{tag_name}': HTTP {resp.status}")
                return False
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[PRUNE] Tag '{tag_name}' già non presente su Docker Hub (404).")
            return True
        print(f"[ERROR] Errore HTTP {e.code} durante eliminazione tag '{tag_name}': {e.reason}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] Errore di rete eliminando tag '{tag_name}': {e}", file=sys.stderr)
        return False


def prune_tags(
    image_name: str,
    username: Optional[str] = None,
    token: Optional[str] = None,
    keep_main: int = DEFAULT_KEEP_MAIN,
    keep_test: int = DEFAULT_KEEP_TEST,
    dry_run: bool = False,
) -> int:
    """Main pruning logic."""
    print("=" * 65)
    print(f"[POLICY] DOCKER HUB TAG RETENTION - {image_name}")
    print(f"   - Mantieni versioni Main: {keep_main} piu' recenti (+ 'latest')")
    print(f"   - Mantieni versioni Test: solo tag flottante 'test'")
    print(f"   - Tag protetti permanenti: {sorted(PROTECTED_TAGS)}")
    print(f"   - Modalita': {'DRY-RUN (Simulazione)' if dry_run else 'PRODUZIONE'}")
    print("=" * 65)

    tags = fetch_all_tags(image_name)
    if not tags:
        print("[INFO] Nessun tag trovato o repository non accessibile.")
        return 0

    print(f"[INFO] Trovati {len(tags)} tag totali su Docker Hub.")

    main_candidates: List[Tuple[Tuple[int, int, int, int], str, str]] = []
    tags_to_delete: List[str] = []

    for t in tags:
        name = t.get("name", "")
        pushed = t.get("tag_last_pushed") or t.get("last_updated") or ""

        if name in PROTECTED_TAGS:
            continue

        if name in LEGACY_TAGS_TO_REMOVE:
            tags_to_delete.append(name)
            continue

        # Check main versioned build tags (<major>.<minor>.<patch>-build.<num>)
        v_main = parse_semver_build(name)
        if v_main:
            # Check if experimental build number >= 90
            if v_main[3] >= 90:
                tags_to_delete.append(name)
            else:
                main_candidates.append((v_main, pushed, name))
            continue

        # Check test versioned tags (<version>-test.<num> o test-build.<num>)
        # Policy: il branch test usa solo il tag 'test'; tutti i tag test versionati vengono rimossi.
        v_test = parse_semver_test(name)
        if v_test:
            tags_to_delete.append(name)
            continue

    # Sort descending by semver, then pushed date
    main_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    kept_main = [c[2] for c in main_candidates[:keep_main]]
    excess_main = [c[2] for c in main_candidates[keep_main:]]

    tags_to_delete.extend(excess_main)

    # Deduplicate while preserving order
    unique_to_delete = list(dict.fromkeys(tags_to_delete))

    print(f"\n[OK] Tag Main conservati ({len(kept_main)}/{keep_main}): {kept_main}")
    print(f"[OK] Tag Test conservati: ['test'] (unico tag flottante)")
    print(f"[INFO] Tag protetti: {sorted(PROTECTED_TAGS)}")

    if not unique_to_delete:
        print("\n[OK] Nessun tag da eliminare. Il repository Docker Hub rispetta gia' la policy di retention.")
        return 0

    print(f"\n[PRUNE] Tag pianificati per l'eliminazione ({len(unique_to_delete)}): {unique_to_delete}")

    jwt_token = None
    if not dry_run:
        jwt_token = get_dockerhub_token(username, token)
        if not jwt_token:
            print("[WARN] Credenziali Docker Hub non fornite o non valide. Saltata eliminazione remota.", file=sys.stderr)
            return 0

    deleted_count = 0
    for tag_name in unique_to_delete:
        if delete_dockerhub_tag(image_name, tag_name, jwt_token or "", dry_run=dry_run):
            deleted_count += 1

    print(f"\n[COMPLETED] Pulizia completata: {deleted_count} tag rimossi con successo.")
    return deleted_count


def main():
    parser = argparse.ArgumentParser(description="Docker Hub tag retention management")
    parser.add_argument("--image", default=os.getenv("IMAGE_NAME", DEFAULT_IMAGE), help="Docker repository (es. user/repo)")
    parser.add_argument("--username", default=os.getenv("DOCKERHUB_USERNAME"), help="Docker Hub username")
    parser.add_argument("--token", default=os.getenv("DOCKERHUB_TOKEN"), help="Docker Hub access token")
    parser.add_argument("--keep-main", type=int, default=DEFAULT_KEEP_MAIN, help="Numero di versioni main da mantenere")
    parser.add_argument("--keep-test", type=int, default=DEFAULT_KEEP_TEST, help="Numero di versioni test da mantenere")
    parser.add_argument("--dry-run", action="store_true", help="Simula l'esecuzione senza cancellare i tag")

    args = parser.parse_args()
    prune_tags(
        image_name=args.image,
        username=args.username,
        token=args.token,
        keep_main=args.keep_main,
        keep_test=args.keep_test,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
