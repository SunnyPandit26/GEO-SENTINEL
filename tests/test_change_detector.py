"""
GEO-SENTINEL Unit Tests: Change Detector & False-Alarm Suppression
"""

import unittest
import numpy as np
from backend.engine.change_detector import ChangeDetectorEngine
from backend.engine.quality_filter import QualityFilterEngine


class TestChangeDetector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = ChangeDetectorEngine.get_instance()
        cls.quality_filter = QualityFilterEngine.get_instance()

    def test_quality_mask_cloud_rejection(self):
        # Create image with bright white cloud patch
        img = np.full((256, 256, 3), 100, dtype=np.uint8)
        img[50:150, 50:150] = 250  # Bright cloud
        
        qa_mask, quality_score = self.quality_filter.compute_quality_mask(img)
        self.assertLess(quality_score, 1.0)
        self.assertEqual(qa_mask[100, 100], 0)  # Cloud masked as 0

    def test_identical_images_no_change(self):
        img1 = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
        img2 = img1.copy()

        res = self.detector.analyze_change(
            img_t1=img1,
            img_t2=img2,
            bbox=[28.60, 77.20, 28.62, 77.22],
            tile_id="unit_test_identical"
        )
        self.assertFalse(res["change_detected"])
        self.assertEqual(res["change_type"], "No Significant Change")


if __name__ == "__main__":
    unittest.main()
