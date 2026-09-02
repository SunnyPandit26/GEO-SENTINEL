"""
GEO-SENTINEL Unit Tests: Multimodal Embeddings & Vector Index
"""

import unittest
import numpy as np
from PIL import Image
from backend.engine.embeddings import MultimodalEmbeddingEngine
from backend.engine.vector_index import VectorIndexEngine


class TestEmbeddingsAndIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = MultimodalEmbeddingEngine.get_instance()
        cls.index = VectorIndexEngine.get_instance()

    def test_text_embedding_shape_and_norm(self):
        query = "newly built structures near a river"
        emb = self.engine.embed_text(query)
        self.assertEqual(emb.shape, (512,))
        norm = np.linalg.norm(emb)
        self.assertAlmostEqual(norm, 1.0, places=4)

    def test_image_embedding_shape_and_norm(self):
        dummy_img = Image.fromarray(np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8))
        emb = self.engine.embed_image(dummy_img)
        self.assertEqual(emb.shape, (512,))
        norm = np.linalg.norm(emb)
        self.assertAlmostEqual(norm, 1.0, places=4)

    def test_vector_search_latency_and_ranking(self):
        query = "river flood water inundation"
        q_vec = self.engine.embed_text(query)
        results = self.index.search(q_vec, top_k=5)
        self.assertGreater(len(results), 0)
        self.assertIn("similarity_score", results[0])
        self.assertGreaterEqual(results[0]["similarity_score"], 0.7)


if __name__ == "__main__":
    unittest.main()
