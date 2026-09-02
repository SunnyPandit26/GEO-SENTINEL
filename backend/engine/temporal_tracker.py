"""
GEO-SENTINEL Temporal Onset Tracker & Earliest Usable Observation Engine
Estimates the earliest available observation (T*) at which change is statistically supported by cloud-free, usable imagery.
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from backend.engine.quality_filter import QualityFilterEngine


class TemporalOnsetTracker:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.quality_filter = QualityFilterEngine.get_instance()

    def estimate_earliest_observation(
        self,
        time_series_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyzes a chronological sequence of tile observations [T1, T2, ..., Tn]
        to identify the exact earliest date T* when change statistically emerged.

        Each record contains:
        {
            "acquisition_date": "YYYY-MM-DD",
            "image": np.ndarray (RGB),
            "nir": Optional[np.ndarray],
            "scene_id": str
        }
        """
        if len(time_series_records) < 2:
            return {
                "earliest_observation_date": time_series_records[0]["acquisition_date"] if time_series_records else "N/A",
                "onset_confidence": 0.0,
                "timeline": []
            }

        # Sort chronologically
        sorted_records = sorted(time_series_records, key=lambda x: x["acquisition_date"])
        
        # Compute quality mask & scores for all time steps
        quality_scores = []
        qa_masks = []
        for rec in sorted_records:
            qa_mask, q_score = self.quality_filter.compute_quality_mask(rec["image"], rec.get("nir"))
            quality_scores.append(q_score)
            qa_masks.append(qa_mask)

        # Base reference: first usable image
        baseline_idx = 0
        for i, q in enumerate(quality_scores):
            if q >= 0.75:
                baseline_idx = i
                break

        base_img = sorted_records[baseline_idx]["image"]
        base_qa = qa_masks[baseline_idx]

        trajectory = []
        earliest_onset_date = sorted_records[-1]["acquisition_date"]
        onset_found = False
        onset_conf = 0.0

        diff_values = []
        for i, rec in enumerate(sorted_records):
            img_curr = rec["image"]
            q_curr = quality_scores[i]
            qa_curr = qa_masks[i]
            date_curr = rec["acquisition_date"]

            if i == baseline_idx:
                trajectory.append({
                    "date": date_curr,
                    "scene_id": rec.get("scene_id"),
                    "quality_score": round(q_curr, 3),
                    "is_usable": True,
                    "change_metric": 0.0,
                    "is_onset": False,
                    "status": "Baseline Calibration"
                })
                diff_values.append(0.0)
                continue

            # Check if usable imagery
            is_usable = bool(q_curr >= 0.70)
            if not is_usable:
                trajectory.append({
                    "date": date_curr,
                    "scene_id": rec.get("scene_id"),
                    "quality_score": round(q_curr, 3),
                    "is_usable": False,
                    "change_metric": 0.0,
                    "is_onset": False,
                    "status": "Rejected Confounding Factor (Cloud/Shadow/Haze)"
                })
                diff_values.append(diff_values[-1] if diff_values else 0.0)
                continue

            # Radiometrically normalize and calculate difference against baseline
            norm_img = self.quality_filter.radiometric_normalization(base_img, img_curr, base_qa, qa_curr)
            aligned_img, _ = self.quality_filter.compensate_co_registration(base_img, norm_img)

            # Difference calculation
            diff = np.mean(np.abs(aligned_img.astype(np.float32) - base_img.astype(np.float32))) / 255.0
            diff_values.append(diff)

            # Statistical onset threshold (e.g. diff > 0.15 on clean usable image)
            is_onset = False
            if diff > 0.14 and not onset_found and is_usable:
                is_onset = True
                onset_found = True
                earliest_onset_date = date_curr
                onset_conf = min(1.0, float(diff * 3.5) * q_curr)

            trajectory.append({
                "date": date_curr,
                "scene_id": rec.get("scene_id"),
                "quality_score": round(q_curr, 3),
                "is_usable": is_usable,
                "change_metric": round(float(diff), 4),
                "is_onset": is_onset,
                "status": "Confirmed Onset Step" if is_onset else ("Change Persists" if onset_found else "Stable Baseline")
            })

        if not onset_found and sorted_records:
            earliest_onset_date = sorted_records[-1]["acquisition_date"]
            onset_conf = 0.3

        return {
            "earliest_observation_date": earliest_onset_date,
            "onset_confidence": round(float(onset_conf), 3),
            "timeline": trajectory
        }
