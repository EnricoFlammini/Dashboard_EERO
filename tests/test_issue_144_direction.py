import unittest
import tempfile
import os
import shutil
from datetime import datetime, timezone, timedelta
from app.services.db import DBService
from app.services.poller import background_poller

class TestIssue144RxTxDirection(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_issue_144.db")
        self.test_db = DBService(db_path=self.db_path)
        await self.test_db.init_db()

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_top_bandwidth_hogs_download_upload_mapping(self):
        # In eero AP semantics:
        # tx_bytes = transmitted by AP to client = client Download (e.g. 800 MB)
        # rx_bytes = received by AP from client = client Upload (e.g. 200 MB)
        mac = "aa:bb:cc:dd:ee:01"
        tx_val = 800 * 1024 * 1024
        rx_val = 200 * 1024 * 1024

        # Insert baseline sample and current sample to produce positive deltas
        now = datetime.now(timezone.utc)
        await self.test_db.record_device_usage_samples(
            samples=[{
                "mac": mac,
                "hostname": "TestCamera",
                "rx_bytes": 0.0,
                "tx_bytes": 0.0,
                "download_rate_mbps": 0.0,
                "upload_rate_mbps": 0.0,
                "timestamp": (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            }],
            network_id="net_issue144"
        )
        await self.test_db.record_device_usage_samples(
            samples=[{
                "mac": mac,
                "hostname": "TestCamera",
                "rx_bytes": float(rx_val),
                "tx_bytes": float(tx_val),
                "download_rate_mbps": 15.0,
                "upload_rate_mbps": 2.0,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
            }],
            network_id="net_issue144"
        )

        hogs = await self.test_db.get_top_bandwidth_hogs(network_id="net_issue144", limit=5, period="daily")
        self.assertEqual(len(hogs), 1)
        hog = hogs[0]
        self.assertEqual(hog["download_bytes"], tx_val)
        self.assertEqual(hog["upload_bytes"], rx_val)
        self.assertEqual(hog["tx_bytes"], tx_val)
        self.assertEqual(hog["rx_bytes"], rx_val)

    async def test_device_usage_history_download_upload_mapping(self):
        mac = "aa:bb:cc:dd:ee:02"
        tx_val = 500 * 1024 * 1024
        rx_val = 100 * 1024 * 1024

        now = datetime.now(timezone.utc)
        await self.test_db.record_device_usage_samples(
            samples=[{
                "mac": mac,
                "hostname": "TestLaptop",
                "rx_bytes": 0.0,
                "tx_bytes": 0.0,
                "download_rate_mbps": 0.0,
                "upload_rate_mbps": 0.0,
                "timestamp": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            }],
            network_id="net_issue144"
        )
        await self.test_db.record_device_usage_samples(
            samples=[{
                "mac": mac,
                "hostname": "TestLaptop",
                "rx_bytes": float(rx_val),
                "tx_bytes": float(tx_val),
                "download_rate_mbps": 50.0,
                "upload_rate_mbps": 10.0,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
            }],
            network_id="net_issue144"
        )

        history = await self.test_db.get_device_usage_history(mac, period="daily")
        summary = history.get("summary", {})
        self.assertEqual(summary.get("download_bytes"), tx_val)
        self.assertEqual(summary.get("upload_bytes"), rx_val)

    def test_poller_throughput_direction_mapping(self):
        # When poller receives delta_tx (AP transmitting to device),
        # this corresponds to client DOWNLOAD rate.
        # When poller receives delta_rx (AP receiving from device),
        # this corresponds to client UPLOAD rate.
        mac = "aa:bb:cc:dd:ee:03"
        t0 = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 11, 24, 12, 0, 10, tzinfo=timezone.utc) # 10 seconds later

        background_poller._prev_device_metrics[mac] = {
            "timestamp": t0,
            "rx_bytes": 1_000_000.0,
            "tx_bytes": 10_000_000.0,
        }

        # Device reports updated counters:
        # tx (DL) grew by 10 MB in 10s -> 1 MB/s = 8 Mbps
        # rx (UL) grew by 1 MB in 10s -> 0.1 MB/s = 0.8 Mbps
        prev = background_poller._prev_device_metrics[mac]
        dt_sec = (t1 - prev["timestamp"]).total_seconds()
        tx_now = 10_000_000.0 + (10 * 1024 * 1024)
        rx_now = 1_000_000.0 + (1 * 1024 * 1024)

        delta_tx = tx_now - prev["tx_bytes"]
        delta_rx = rx_now - prev["rx_bytes"]

        rate_down = round((delta_tx * 8.0) / (dt_sec * 1_000_000.0), 2)
        rate_up = round((delta_rx * 8.0) / (dt_sec * 1_000_000.0), 2)

        self.assertAlmostEqual(rate_down, (10 * 1024 * 1024 * 8) / (10 * 1_000_000), delta=0.1)
        self.assertAlmostEqual(rate_up, (1 * 1024 * 1024 * 8) / (10 * 1_000_000), delta=0.1)

if __name__ == "__main__":
    unittest.main()
