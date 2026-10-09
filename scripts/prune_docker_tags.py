#!/usr/bin/env python3
"""
scripts/prune_docker_tags.py
=============================================================================
Manages Docker Hub tag retention policy for eero Custom Dashboard:
  - Keeps the latest 5 versions of 'main' releases (plus rolling 'latest')
  - Keeps only the latest 1 version of 'test' builds (plus rolling 'test')
  - Never deletes protected rolling tags: latest, test, main
=============================================================================
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime


def log(msg: str):
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)
    except UnicodeEncodeError:
        safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {safe_msg}", flush=True)


def main():
    image_name = os.environ.get("IMAGE_NAME", "enricoflammini/eero-dashboard")
    username = os.environ.get("DOCKERHUB_USERNAME")
    token = os.environ.get("DOCKERHUB_TOKEN")
    dry_run = os.environ.get("DRY_RUN", "0").lower() in ("1", "true", "yes")

    max_main_tags = int(os.environ.get("MAX_MAIN_TAGS", "5"))
    max_test_tags = int(os.environ.get("MAX_TEST_TAGS", "1"))

    if not username or not token:
        log("⚠️ Credenziali Docker Hub (DOCKERHUB_USERNAME / DOCKERHUB_TOKEN) non configurate. Salto pulizia tag.")
        sys.exit(0)

    log(f"🚀 Avvio policy retention tag Docker Hub per: {image_name}")
    log(f"📌 Regole: Max {max_main_tags} versioni Main, Max {max_test_tags} versione Test (Dry-run: {dry_run})")

    # 1. Autenticazione Docker Hub v2 API
    login_url = "https://hub.docker.com/v2/users/login/"
    login_payload = json.dumps({"username": username, "password": token}).encode("utf-8")
    req = urllib.request.Request(
        login_url,
        data=login_payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            login_data = json.loads(resp.read().decode("utf-8"))
            jwt_token = login_data.get("token")
            if not jwt_token:
                log("❌ Impossibile ottenere token JWT da Docker Hub.")
                sys.exit(0)
    except Exception as e:
        log(f"⚠️ Errore durante l'autenticazione Docker Hub: {e}. Salto pulizia.")
        sys.exit(0)

    log("🔑 Autenticazione Docker Hub completata con successo.")

    # 2. Recupero tutti i tag con paginazione
    headers = {
        "Authorization": f"JWT {jwt_token}",
        "Accept": "application/json"
    }

    all_tags = []
    next_url = f"https://hub.docker.com/v2/repositories/{image_name}/tags?page_size=100"

    while next_url:
        try:
            req = urllib.request.Request(next_url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                all_tags.extend(results)
                next_url = data.get("next")
        except Exception as e:
            log(f"⚠️ Errore durante il recupero dei tag da {next_url}: {e}")
            break

    log(f"📦 Totale tag trovati nel repository: {len(all_tags)}")

    # 3. Classificazione tag
    protected_tags = {"latest", "test", "main"}
    test_tags = []
    main_tags = []

    for t in all_tags:
        name = t.get("name", "")
        if name in protected_tags:
            continue

        # Tag di test: contiene "-test." o inizia con "test-" o finisce con "-test"
        if "-test" in name or name.startswith("test-"):
            test_tags.append(t)
        else:
            main_tags.append(t)

    # Ordina per data di aggiornamento decrescente (più recenti per primi)
    test_tags.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
    main_tags.sort(key=lambda x: x.get("last_updated", ""), reverse=True)

    # 4. Determinazione tag da cancellare
    to_delete = []

    # Per TEST: mantieni solo max_test_tags (1)
    keep_test = test_tags[:max_test_tags]
    delete_test = test_tags[max_test_tags:]
    for t in delete_test:
        to_delete.append((t["name"], "TEST", t.get("last_updated", "")))

    # Per MAIN: mantieni solo max_main_tags (5)
    keep_main = main_tags[:max_main_tags]
    delete_main = main_tags[max_main_tags:]
    for t in delete_main:
        to_delete.append((t["name"], "MAIN", t.get("last_updated", "")))

    log("─────────────────────────────────────────────────────────────")
    log(f"✅ Tag MAIN mantenuti ({len(keep_main)}):")
    for t in keep_main:
        log(f"   • {t['name']} (aggiornato: {t.get('last_updated', 'N/D')})")

    log(f"✅ Tag TEST mantenuti ({len(keep_test)}):")
    for t in keep_test:
        log(f"   • {t['name']} (aggiornato: {t.get('last_updated', 'N/D')})")

    log("─────────────────────────────────────────────────────────────")
    if not to_delete:
        log("✨ Nessun tag da eliminare. Il repository rispetta già la policy.")
        return

    log(f"🗑️ Tag identificati per l'eliminazione ({len(to_delete)}):")
    for name, kind, updated in to_delete:
        log(f"   - [{kind}] {name} (del {updated})")

    # 5. Esecuzione cancellazione
    deleted_count = 0
    for name, kind, _ in to_delete:
        delete_url = f"https://hub.docker.com/v2/repositories/{image_name}/tags/{name}/"
        if dry_run:
            log(f"🔍 [DRY-RUN] Simulazione eliminazione: {name}")
            deleted_count += 1
            continue

        del_req = urllib.request.Request(delete_url, headers=headers, method="DELETE")
        try:
            with urllib.request.urlopen(del_req) as resp:
                if resp.status in (200, 204):
                    log(f"🗑️ Eliminato tag {kind}: {name} (HTTP {resp.status})")
                    deleted_count += 1
                else:
                    log(f"⚠️ Risposta inattesa eliminando {name}: HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            log(f"❌ Errore HTTP {e.code} eliminando tag {name}: {e.reason}")
        except Exception as e:
            log(f"❌ Eccezione durante eliminazione {name}: {e}")

    log("─────────────────────────────────────────────────────────────")
    log(f"🎉 Pulizia completata! Eliminati {deleted_count} tag obsoleti.")


if __name__ == "__main__":
    main()
