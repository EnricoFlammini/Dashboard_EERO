---
id: prometheus-grafana
title: 13. Μετρήσεις Prometheus & Πίνακας Grafana
icon: presentation-chart-line
summary: Εγγενής συλλογή OpenMetrics (/metrics), εξαγόμενες χρονοσειρές και έτοιμο πρότυπο Grafana.
---
### Μετρήσεις Prometheus & Πίνακας Grafana

Η εφαρμογή παρέχει ένα εγγενές σημείο απόληξης σύμφωνα με τις προδιαγραφές **Prometheus / OpenMetrics**:

* **Σημείο Συλλογής Μετρήσεων:**
  - Άμεσα προσβάσιμο στη διεύθυνση `GET /metrics` (ή `/api/metrics/prometheus`).
  - Επιστρέφει δεδομένα στην επίσημη μορφή κειμένου Prometheus (`text/plain; version=0.0.4; charset=utf-8`).
* **Διαθέσιμες Χρονοσειρές:**
  - `eero_info`: Μεταδεδομένα, έκδοση και όνομα ενεργού δικτύου.
  - `eero_clients_total`: Συσκευές με ετικέτα `status="connected"` ή `"disconnected"`.
  - `eero_clients_band_total`: Πελάτες ανά ζώνη συχνότητας (`2.4ghz`, `5ghz`, `6ghz`, `wired`).
  - `eero_wan_download_mbps` & `eero_wan_upload_mbps`: Συγκεντρωτική ταχύτητα WAN σε πραγματικό χρόνο.
  - `eero_wan_ping_ms`: Χρόνος απόκρισης πύλης σε χιλιοστά του δευτερολέπτου.
  - `eero_health_score`: Συνολικός δείκτης υγείας (0 έως 100).
  - `eero_mesh_nodes_total` & `eero_mesh_nodes_online`: Αριθμός και κατάσταση κόμβων mesh.
  - `eero_bufferbloat_grade_numeric` & τιμές καθυστέρησης υπό φορτίο.
  - `eero_bandwidth_rx_bytes_total` & `eero_bandwidth_tx_bytes_total`: Σωρευτικοί μετρητές διακίνησης δεδομένων.
* **Συνοδευτικό Πρότυπο Grafana:**
  - Έτοιμο αρχείο προς εισαγωγή στο `deploy/grafana/eero_dashboard.json` με 13 προρυθμισμένα γραφήματα.
* **Ασφάλεια & Έλεγχος Πρόσβασης RBAC:**
  - Η πρόσβαση στο `/metrics` απαιτεί το δικαίωμα `view_topology`.
  - Όταν είναι ενεργό το `REQUIRE_LOCAL_AUTH=true`, η συλλογή μετρήσεων απαιτεί επικυρωμένη συνεδρία χρήστη.
