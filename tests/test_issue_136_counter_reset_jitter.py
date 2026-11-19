import unittest
import tempfile
import os
import shutil
from datetime import datetime, timedelta, timezone

import aiosqlite

from app.services.db import DBService, counter_delta


class TestCounterDelta(unittest.TestCase):
    def test_rise_adds_growth(self):
        self.assertEqual(counter_delta(110.0, 100.0), (10.0, 110.0))

    def test_small_dip_is_jitter(self):
        self.assertEqual(counter_delta(95.0, 100.0), (0.0, 100.0))

    def test_dip_to_exactly_ten_percent_is_not_a_reset(self):
        # The issue's rule: a reset is a drop *below* 10% of the high-water mark.
        self.assertEqual(counter_delta(10.0, 100.0), (0.0, 100.0))

    def test_drop_below_ten_percent_is_a_reset(self):
        self.assertEqual(counter_delta(9.0, 100.0), (9.0, 9.0))

    def test_zero_high_water_mark(self):
        self.assertEqual(counter_delta(50.0, 0.0), (50.0, 50.0))
        self.assertEqual(counter_delta(0.0, 0.0), (0.0, 0.0))


async def _seed_history(db_path, mac, samples):
    """Insert raw device_usage_history rows with explicit timestamps.

    samples: list of (timestamp_str, rx_bytes, tx_bytes).
    """
    async with aiosqlite.connect(db_path) as db:
        for ts, rx, tx in samples:
            await db.execute(
                """
                INSERT INTO device_usage_history
                (timestamp, mac_address, network_id, hostname, rx_bytes, tx_bytes,
                 download_mbps, upload_mbps, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, mac, "net_test_136", mac, rx, tx, 0.0, 0.0, 0),
            )
        await db.commit()


class TestIssue136CounterResetJitter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_136.db")
        self.test_db = DBService(db_path=self.db_path)
        await self.test_db.init_db()
        self.mac = "84:0d:8e:11:22:33"

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_issue_repro_small_dip_not_a_reset(self):
        # Issue body repro, scaled to the real series:
        # deltas([5e9, 5e9+1000, 5e9-500, 5e9+2000]) is ~5.0e9 today, expected 2000.
        base = datetime.now(timezone.utc) - timedelta(minutes=10)
        pts = [5e9, 5e9 + 1000, 5e9 - 500, 5e9 + 2000]
        samples = [
            ((base + timedelta(seconds=13 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"), rx, 0.0)
            for i, rx in enumerate(pts)
        ]
        await _seed_history(self.db_path, self.mac, samples)
        hist = await self.test_db.get_device_usage_history(
            self.mac, period="daily", resolution_minutes=15
        )
        self.assertEqual(hist["summary"]["rx_bytes"], 2000.0)

    async def test_issue_series_aggregate_hourly(self):
        # Exact raw series from the issue (2026-11-19 03:45-03:47 UTC).
        # Two small dips to a slightly stale value must not add ~3.41 GB each.
        stamps = ["03:45:54", "03:46:07", "03:46:21", "03:46:34", "03:46:47", "03:46:59", "03:47:25"]
        rx_vals = [3411172280, 3418614500, 3411172280, 3418614500, 3411172280, 3411172280, 3418614500]
        tx_vals = [6413120, 6431040, 6413120, 6431040, 6413120, 6413120, 6431040]
        samples = [
            (f"2026-11-19 {ts}", rx, tx) for ts, rx, tx in zip(stamps, rx_vals, tx_vals)
        ]
        await _seed_history(self.db_path, self.mac, samples)
        count = await self.test_db.aggregate_hourly_usage(
            datetime(2026, 11, 19, 3, 0, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(count, 1)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT rx_bytes_delta, tx_bytes_delta FROM device_usage_hourly WHERE mac_address = ?",
                (self.mac,),
            ) as cur:
                row = await cur.fetchone()
        # High-water-mark total: the counter only ever grows from
        # 3,411,172,280 to 3,418,614,500 (rx) / 6,413,120 to 6,431,040 (tx).
        # The returns to the previous maximum after each dip are re-reads of
        # a value already seen, not new traffic, so they add 0.
        self.assertEqual(row[0], 7442220.0)
        self.assertEqual(row[1], 17920.0)

    async def test_aggregate_hourly_first_sample_dip_across_hour_boundary(self):
        # The prev-hour branch: a slightly stale first sample of the hour
        # must not count as a reset against the previous hour's last sample.
        samples = [
            ("2026-11-19 02:59:00", 3418614500, 6431040),
            ("2026-11-19 03:00:10", 3411172280, 6413120),
            ("2026-11-19 03:00:20", 3418619500, 6431140),
        ]
        await _seed_history(self.db_path, self.mac, samples)
        count = await self.test_db.aggregate_hourly_usage(
            datetime(2026, 11, 19, 3, 0, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(count, 1)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT rx_bytes_delta, tx_bytes_delta FROM device_usage_hourly WHERE mac_address = ?",
                (self.mac,),
            ) as cur:
                row = await cur.fetchone()
        self.assertEqual(row[0], 5000.0)
        self.assertEqual(row[1], 100.0)

    async def test_aggregate_hourly_first_sample_genuine_reset(self):
        # Same branch, genuine reset: first sample of the hour far below the
        # previous hour's last sample counts the new counter value.
        samples = [
            ("2026-11-19 02:59:00", 5_000_000_000, 1_000_000),
            ("2026-11-19 03:00:10", 400_000_000, 90_000),
            ("2026-11-19 03:00:20", 400_002_000, 90_500),
        ]
        await _seed_history(self.db_path, self.mac, samples)
        count = await self.test_db.aggregate_hourly_usage(
            datetime(2026, 11, 19, 3, 0, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(count, 1)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT rx_bytes_delta, tx_bytes_delta FROM device_usage_hourly WHERE mac_address = ?",
                (self.mac,),
            ) as cur:
                row = await cur.fetchone()
        self.assertEqual(row[0], 400_002_000.0)
        self.assertEqual(row[1], 90_500.0)

    async def test_genuine_reset_still_counted(self):
        # Control case: a drop to <10% of the high-water mark IS a real reset
        # (reconnect/reboot) and the new counter value must still be counted.
        base = datetime.now(timezone.utc) - timedelta(minutes=10)
        pts = [5e9, 5e9 + 1000, 400_000_000, 400_002_000]
        samples = [
            ((base + timedelta(seconds=13 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"), rx, 0.0)
            for i, rx in enumerate(pts)
        ]
        await _seed_history(self.db_path, self.mac, samples)
        hist = await self.test_db.get_device_usage_history(
            self.mac, period="daily", resolution_minutes=15
        )
        self.assertEqual(hist["summary"]["rx_bytes"], 1000.0 + 400_000_000.0 + 2000.0)

    async def test_top_hogs_shallow_history_reports_window_delta_not_lifetime(self):
        # Same bug class in the shallow-history branch (<12h of history):
        # 6h of samples, counter 4.9e9 -> 5.0e9, must report 1e8, not 5.0e9.
        # A device with a single sample has no measured usage in the window.
        now = datetime.now(timezone.utc)
        mac2 = "84:0d:8e:44:55:66"
        samples = [
            ((now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ"), 4_900_000_000, 9_000),
            (now.strftime("%Y-%m-%dT%H:%M:%SZ"), 5_000_000_000, 10_000),
        ]
        await _seed_history(self.db_path, self.mac, samples)
        await _seed_history(
            self.db_path,
            mac2,
            [(now.strftime("%Y-%m-%dT%H:%M:%SZ"), 5_000_000_000, 10_000)],
        )
        hogs = await self.test_db.get_top_bandwidth_hogs(
            network_id="net_test_136", limit=5, period="daily"
        )
        by_mac = {h["mac"]: h for h in hogs}
        self.assertEqual(by_mac[self.mac]["rx_bytes"], 100_000_000.0)
        self.assertEqual(by_mac[self.mac]["tx_bytes"], 1000.0)
        self.assertEqual(by_mac[mac2]["rx_bytes"], 0.0)
        self.assertEqual(by_mac[mac2]["tx_bytes"], 0.0)

    async def test_top_hogs_flat_counter_reports_zero_not_lifetime(self):
        # Fallback drop: a flat counter over >=12h of history must report 0,
        # not the lifetime counter value.
        now = datetime.now(timezone.utc)
        samples = [
            ((now - timedelta(hours=13)).strftime("%Y-%m-%dT%H:%M:%SZ"), 3411172280, 6413120),
            (now.strftime("%Y-%m-%dT%H:%M:%SZ"), 3411172280, 6413120),
        ]
        await _seed_history(self.db_path, self.mac, samples)
        hogs = await self.test_db.get_top_bandwidth_hogs(
            network_id="net_test_136", limit=5, period="daily"
        )
        self.assertEqual(len(hogs), 1)
        self.assertEqual(hogs[0]["rx_bytes"], 0.0)
        self.assertEqual(hogs[0]["tx_bytes"], 0.0)


if __name__ == "__main__":
    unittest.main()
