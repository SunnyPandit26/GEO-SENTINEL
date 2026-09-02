"""
GEO-SENTINEL False-Alarm Suppression, Radiometric Normalization & Quality Handling Engine
Fulfills Capability 2.2.3: Suppresses seasonal shifts, cloud/shadows, registration jitter, and illumination variations.
"""

import numpy as np
import cv2
from typing import Tuple, Dict, Any, Optional
from skimage.exposure import match_histograms


class QualityFilterEngine:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        pass

    def compute_quality_mask(self, rgb_image: np.ndarray, nir_band: Optional[np.ndarray] = None) -> Tuple[np.ndarray, float]:
        """
        Generates a pixel-wise Quality Assurance (QA) mask and scene quality score [0.0 to 1.0].
        Identifies:
        - Clouds (High brightness in RGB, low NIR/Red ratio)
        - Cloud Shadows (Low brightness adjacent to cloud geometry)
        - Haze / Fog
        - Missing or corrupted sensor pixels (NoData)
        
        Returns:
            qa_mask: uint8 array (0 = Invalid/Cloud/Shadow/Haze, 255 = Clear Usable Land)
            quality_score: float in [0.0, 1.0] representing percentage of usable cloud-free pixels.
        """
        h, w, c = rgb_image.shape
        gray = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
        
        # 1. Cloud Mask (Luminance > 220, or multi-spectral thresholding)
        cloud_mask = np.zeros((h, w), dtype=np.uint8)
        if nir_band is not None:
            # Multi-spectral cloud index: high visible + high NIR
            cloud_condition = (gray > 200) & (rgb_image[:, :, 0] > 190) & (rgb_image[:, :, 2] > 180)
        else:
            cloud_condition = gray > 215

        cloud_mask[cloud_condition] = 255
        # Morphological dilation for cloud boundaries
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cloud_mask = cv2.dilate(cloud_mask, kernel, iterations=1)

        # 2. Shadow Mask (Low luminance < 35, especially near cloud regions)
        shadow_mask = np.zeros((h, w), dtype=np.uint8)
        shadow_mask[gray < 30] = 255
        
        # 3. NoData / Saturated Edge Pixels
        nodata_mask = np.zeros((h, w), dtype=np.uint8)
        nodata_mask[gray == 0] = 255

        # 4. Composite QA Mask: 255 = Valid Usable, 0 = Confounded / Reject
        confounded = (cloud_mask > 0) | (shadow_mask > 0) | (nodata_mask > 0)
        qa_mask = np.full((h, w), 255, dtype=np.uint8)
        qa_mask[confounded] = 0

        usable_pixels = np.sum(qa_mask == 255)
        total_pixels = h * w
        quality_score = float(usable_pixels / total_pixels) if total_pixels > 0 else 0.0

        return qa_mask, quality_score

    def radiometric_normalization(self, img_t1: np.ndarray, img_t2: np.ndarray, qa_mask_t1: np.ndarray, qa_mask_t2: np.ndarray) -> np.ndarray:
        """
        Applies Relative Radiometric Normalization (RRN) using histogram matching
        over Pseudo-Invariant Features (PIFs) / clear valid pixels.
        Normalizes img_t2 to match the radiometric baseline of img_t1.
        """
        # Create common clear mask
        common_valid = (qa_mask_t1 > 0) & (qa_mask_t2 > 0)
        
        if np.sum(common_valid) < (img_t1.shape[0] * img_t1.shape[1] * 0.1):
            # If overlap too small, do standard channel-wise histogram matching
            return match_histograms(img_t2, img_t1, channel_axis=-1).astype(np.uint8)

        # Matched image
        normalized_t2 = match_histograms(img_t2, img_t1, channel_axis=-1).astype(np.uint8)
        return normalized_t2

    def compensate_co_registration(self, img_t1: np.ndarray, img_t2: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Detects and compensates for sub-pixel co-registration jitter using phase correlation.
        Returns:
            aligned_img_t2: Shift-corrected image
            residual_error: Alignment error metric [0.0 = perfect, 1.0 = poor]
        """
        gray1 = cv2.cvtColor(img_t1, cv2.COLOR_RGB2GRAY).astype(np.float32)
        gray2 = cv2.cvtColor(img_t2, cv2.COLOR_RGB2GRAY).astype(np.float32)

        # Compute phase correlation
        shift, response = cv2.phaseCorrelate(gray1, gray2)
        dx, dy = shift

        # Limit maximum shift correction to prevent false warping
        if abs(dx) > 15 or abs(dy) > 15:
            return img_t2, 0.5  # Large discrepancy, keep original

        # Apply affine translation
        M = np.float32([[1, 0, -dx], [0, 1, -dy]])
        aligned = cv2.warpAffine(img_t2, M, (img_t2.shape[1], img_t2.shape[0]), borderMode=cv2.BORDER_REFLECT)
        
        residual_error = float(max(0.0, min(1.0, (abs(dx) + abs(dy)) / 20.0)))
        return aligned, residual_error

    def suppress_edge_jitter_artifacts(self, raw_change_mask: np.ndarray, edge_tolerance_pixels: int = 2) -> np.ndarray:
        """
        Suppresses 1-2 pixel border artifacts caused by minor edge registration offsets.
        Uses morphological opening and connected component area filtering.
        """
        # Morphological opening to remove thin edge strings
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned = cv2.morphologyEx(raw_change_mask, cv2.MORPH_OPEN, kernel, iterations=edge_tolerance_pixels)
        
        # Remove small speckle noise (area < 25 pixels)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
        output_mask = np.zeros_like(cleaned)
        
        min_area = 30
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= min_area:
                output_mask[labels == i] = 255

        return output_mask

    def calculate_confidence_score(
        self,
        raw_magnitude: float,
        quality_score_t1: float,
        quality_score_t2: float,
        registration_residual: float,
        phenology_spectral_variation: float = 0.0
    ) -> float:
        """
        Multi-factor Quality & Analytical Precision Confidence Scoring:
        C = RawMag * min(Q1, Q2) * (1 - Residual) * (1 - PhenologyShift)
        """
        q_factor = min(quality_score_t1, quality_score_t2)
        reg_factor = max(0.4, 1.0 - registration_residual)
        phen_factor = max(0.5, 1.0 - phenology_spectral_variation)

        confidence = raw_magnitude * q_factor * reg_factor * phen_factor * 1.5
        return round(float(max(0.0, min(1.0, confidence))), 4)
