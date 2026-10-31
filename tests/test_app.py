import os
import sys
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["ARTROOM_DB"] = _tmp.name

import app as app_module  # noqa: E402


class ArtRoomTest(unittest.TestCase):
    def setUp(self):
        app_module.init_db()
        self.client = app_module.app.test_client()
        with app_module.app.app_context():
            conn = app_module.get_db()
            conn.execute("DELETE FROM views")
            conn.commit()

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "ok")

    def test_artwork_count(self):
        self.assertGreaterEqual(len(app_module.ARTWORKS), 18)

    def test_image_url(self):
        url = app_module.image_url(app_module.ARTWORKS[0])
        self.assertTrue(url.startswith("https://commons.wikimedia.org/wiki/Special:FilePath/"))

    def test_today_deterministic(self):
        expected = datetime.now(ZoneInfo("Asia/Tokyo")).date().toordinal() % len(app_module.ARTWORKS)
        self.assertEqual(app_module.todays_index(), expected)
        self.assertEqual(app_module.todays_index(), app_module.todays_index())

    def test_today_page_records_history(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        work = app_module.ARTWORKS[app_module.todays_index()]
        self.assertIn(work["title"], body)
        res = self.client.get("/history")
        self.assertIn(work["title"], res.get_data(as_text=True))

    def test_record_same_day_once(self):
        self.client.get("/")
        self.client.get("/")
        with app_module.app.app_context():
            conn = app_module.get_db()
            n = conn.execute("SELECT COUNT(*) AS c FROM views").fetchone()["c"]
        self.assertEqual(n, 1)

    def test_slideshow(self):
        res = self.client.get("/slideshow?interval=10")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("intervalMs = 10 * 1000", body)
        self.assertIn("commons.wikimedia.org", body)

    def test_api_record(self):
        res = self.client.get("/api/record/0")
        self.assertEqual(res.status_code, 200)
        res = self.client.get("/api/record/9999")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
