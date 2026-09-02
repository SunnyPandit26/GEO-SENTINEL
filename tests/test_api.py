"""
GEO-SENTINEL Unit Tests: FastAPI REST Endpoints
"""

import unittest
from fastapi.testclient import TestClient
from backend.app import app


class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_and_scenes(self):
        res = self.client.get("/api/scenes")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("scenes", data)
        self.assertGreater(data["total"], 0)

    def test_semantic_search_endpoint(self):
        payload = {
            "query": "newly built structures near a river",
            "top_k": 5
        }
        res = self.client.post("/api/search/semantic", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("results", data)
        self.assertGreater(data["results_count"], 0)

    def test_clusters_endpoint(self):
        res = self.client.get("/api/clusters")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("clusters", data)
        self.assertIn("points", data)

    def test_review_queue_endpoint(self):
        res = self.client.get("/api/change/queue")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("queue", data)

    def test_benchmark_metrics_endpoint(self):
        res = self.client.get("/api/metrics/benchmark")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["air_gapped"])
        self.assertTrue(data["sovereignty_verified"])
        self.assertGreater(data["indexed_tiles"], 0)


if __name__ == "__main__":
    unittest.main()
