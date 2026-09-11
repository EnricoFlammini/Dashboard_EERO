# Risposta a Issue #25: "Pihole sync issues with V1.4.0"

Copia il testo sottostante e incollalo come commento nella [Issue #25](https://github.com/EnricoFlammini/Dashboard_EERO/issues/25):

---

Hi @Hatton920,

Thank you very much for the detailed report and spot-on root-cause analysis! You were completely right on both points.

### 🛠️ What was fixed:

1. **Native Pi-hole v6 REST API Synchronization:**
   - `_sync_single_pihole()` now detects Pi-hole v6 via `GET /api/config/dns/hosts` and reads existing custom hosts.
   - Slices and merges your active device list with existing records, then performs an atomic batch update via `PATCH /api/config` with `{"config": {"dns": {"hosts": [...]}}}` (with a per-record fallback to `PUT /api/config/dns/hosts/{value}`).
   - Works seamlessly with **passwordless Pi-hole v6 instances** (leaving the token/password empty now grants direct access to the v6 API), as well as instances using a Session SID or standard web password (via session authentication `POST /api/auth`).
   - Retains automatic fallback to the legacy v5 API (`/admin/api.php?customdns&action=add`) for backwards compatibility with older setups.

2. **Optional Domain / Zone (Bare Hostnames):**
   - Removed the automatic fallback that was forcing `.lan` whenever the field was left blank.
   - If you leave the **Domain / Zone** input empty, the dashboard will now sync pure, bare hostnames directly (e.g., `192.168.1.100 mypc` and `192.168.1.200 printer`). If a zone is specified, it will append it as an FQDN.
   - Updated the UI input label and placeholder in English and Italian to indicate that the zone is optional.

---

### 🧪 How to test right now:

The fix is committed on the `test` branch (commit `c4b02a3`). If you are running via Docker from source or the test compose:

```bash
git checkout test
git pull origin test
docker compose -f docker-compose.test.yml up -d --build
```

Alternatively, if you pull our Docker images, this fix will be included in the upcoming patch release.

Feel free to test it out and let us know if everything works as expected with your setup! Thanks again for helping improve the suite! 🚀
