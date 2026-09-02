"""
GEO-SENTINEL Multi-Temporal Change Detection & Classification Engine
Fulfills Capability 2.2.2: Identifies feature appearance/disappearance/expansion/contraction,
classifies change types (Construction, Clearance, Water Extent, Road Development),
and generates geospatial contours and difference heatmaps.
"""

import os
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, List, Optional, Tuple
from backend.engine.quality_filter import QualityFilterEngine

CHANGE_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "tiles", "changes")
os.makedirs(CHANGE_OUTPUT_DIR, exist_ok=True)


class ChangeDetectorEngine:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.quality_filter = QualityFilterEngine.get_instance()

    def compute_ndvi(self, rgb_or_spectral: np.ndarray, nir_band: Optional[np.ndarray] = None) -> np.ndarray:
        """Calculates Normalized Difference Vegetation Index (NDVI = (NIR - Red) / (NIR + Red))."""
        if nir_band is not None:
            red = rgb_or_spectral[:, :, 0].astype(np.float32)
            nir = nir_band.astype(np.float32)
        else:
            # Pseudo-NIR approximation from Green vs Red for 3-band RGB imagery
            red = rgb_or_spectral[:, :, 0].astype(np.float32)
            green = rgb_or_spectral[:, :, 1].astype(np.float32)
            nir = green * 1.3  # Enhanced green reflection surrogate

        denom = nir + red
        denom[denom == 0] = 1e-6
        ndvi = (nir - red) / denom
        return np.clip(ndvi, -1.0, 1.0)

    def compute_ndwi(self, rgb_or_spectral: np.ndarray, nir_band: Optional[np.ndarray] = None) -> np.ndarray:
        """Calculates Normalized Difference Water Index (NDWI = (Green - NIR) / (Green + NIR))."""
        green = rgb_or_spectral[:, :, 1].astype(np.float32)
        if nir_band is not None:
            nir = nir_band.astype(np.float32)
        else:
            red = rgb_or_spectral[:, :, 0].astype(np.float32)
            blue = rgb_or_spectral[:, :, 2].astype(np.float32)
            nir = (red + blue) / 2.0

        denom = green + nir
        denom[denom == 0] = 1e-6
        ndwi = (green - nir) / denom
        return np.clip(ndwi, -1.0, 1.0)

    def analyze_change(
        self,
        img_t1: np.ndarray,
        img_t2: np.ndarray,
        bbox: List[float],
        tile_id: str,
        nir_t1: Optional[np.ndarray] = None,
        nir_t2: Optional[np.ndarray] = None,
        date_t1: str = "T1",
        date_t2: str = "T2"
    ) -> Dict[str, Any]:
        """
        Executes robust, quality-filtered multi-temporal change detection between T1 and T2.
        """
        # 1. Quality Masks
        qa_mask_t1, q_score_t1 = self.quality_filter.compute_quality_mask(img_t1, nir_t1)
        qa_mask_t2, q_score_t2 = self.quality_filter.compute_quality_mask(img_t2, nir_t2)

        # 2. Radiometric Normalization
        img_t2_norm = self.quality_filter.radiometric_normalization(img_t1, img_t2, qa_mask_t1, qa_mask_t2)

        # 3. Co-registration Jitter Compensation
        img_t2_aligned, reg_residual = self.quality_filter.compensate_co_registration(img_t1, img_t2_norm)

        # 4. Multimodal Differencing (Color + Texture + Spectral Indices)
        # Structural edge maps
        gray1 = cv2.cvtColor(img_t1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(img_t2_aligned, cv2.COLOR_RGB2GRAY)

        edges1 = cv2.Canny(gray1, 40, 120)
        edges2 = cv2.Canny(gray2, 40, 120)
        edge_diff = np.abs(edges2.astype(np.float32) - edges1.astype(np.float32))

        # Pixel-wise color distance in CIELAB space
        lab1 = cv2.cvtColor(img_t1, cv2.COLOR_RGB2LAB).astype(np.float32)
        lab2 = cv2.cvtColor(img_t2_aligned, cv2.COLOR_RGB2LAB).astype(np.float32)
        color_dist = np.sqrt(np.sum((lab2 - lab1) ** 2, axis=-1))

        # Spectral index differencing
        ndvi1 = self.compute_ndvi(img_t1, nir_t1)
        ndvi2 = self.compute_ndvi(img_t2_aligned, nir_t2)
        d_ndvi = ndvi2 - ndvi1

        ndwi1 = self.compute_ndwi(img_t1, nir_t1)
        ndwi2 = self.compute_ndwi(img_t2_aligned, nir_t2)
        d_ndwi = ndwi2 - ndwi1

        # Composite difference magnitude map
        combined_diff = (color_dist / 60.0) * 0.4 + (edge_diff / 255.0) * 0.3 + (np.abs(d_ndvi)) * 0.3
        combined_diff = np.clip(combined_diff, 0.0, 1.0)

        # Apply common QA valid mask
        valid_qa = (qa_mask_t1 > 0) & (qa_mask_t2 > 0)
        combined_diff[~valid_qa] = 0.0

        # Binary thresholding for significant change
        threshold = 0.22
        raw_change_mask = (combined_diff > threshold).astype(np.uint8) * 255

        # Suppress edge registration artifacts & small speckles
        cleaned_mask = self.quality_filter.suppress_edge_jitter_artifacts(raw_change_mask, edge_tolerance_pixels=1)

        # 5. Change Classification Logic
        change_pixels = np.sum(cleaned_mask > 0)
        total_valid_pixels = max(1, np.sum(valid_qa))
        change_ratio = float(change_pixels / total_valid_pixels)

        # Calculate localized spectral signals inside the changed mask
        if change_pixels > 15:
            mask_bool = cleaned_mask > 0
            mean_d_ndvi = float(np.mean(d_ndvi[mask_bool]))
            mean_d_ndwi = float(np.mean(d_ndwi[mask_bool]))
            mean_edge_increase = float(np.mean(edge_diff[mask_bool])) / 255.0

            # Classification heuristics
            if mean_d_ndwi > 0.15 or (mean_d_ndwi > 0.08 and np.mean(ndwi2[mask_bool]) > 0.10):
                change_type = "Water Extent Variation"
                subtype = "Inundation / Flood Expansion" if mean_d_ndwi > 0 else "Reservoir Contraction"
            elif mean_d_ndvi < -0.12:
                change_type = "Clearance / Deforestation"
                subtype = "Vegetation Removal / Bare Ground"
            elif mean_edge_increase > 0.15 and np.mean(gray2[mask_bool]) > np.mean(gray1[mask_bool]):
                # Check for linear structures (Roads) vs polygonal structures (Buildings)
                contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                is_linear = False
                for cnt in contours:
                    if cv2.contourArea(cnt) > 30:
                        rect = cv2.minAreaRect(cnt)
                        w, h = rect[1]
                        aspect = max(w, h) / (min(w, h) + 1e-5)
                        if aspect > 3.0:
                            is_linear = True
                            break
                if is_linear:
                    change_type = "Road / Transport Infrastructure"
                    subtype = "Linear Pavement / Transport Corridor"
                else:
                    change_type = "Construction / Built-up"
                    subtype = "New Building / Structural Footprint"
            else:
                change_type = "Land Surface Modification"
                subtype = "Terrain / Surface Alteration"
        else:
            change_type = "No Significant Change"
            subtype = "Stable Baseline"
            change_ratio = 0.0

        # Magnitude & Confidence calculation
        raw_magnitude = float(min(1.0, max(0.2, change_ratio * 4.0))) if change_type != "No Significant Change" else 0.0
        confidence_score = self.quality_filter.calculate_confidence_score(
            raw_magnitude=raw_magnitude,
            quality_score_t1=q_score_t1,
            quality_score_t2=q_score_t2,
            registration_residual=reg_residual
        )

        # Severity rating
        if confidence_score >= 0.60 and change_ratio > 0.08:
            severity = "High"
        elif confidence_score >= 0.30 and change_ratio > 0.02:
            severity = "Medium"
        elif change_ratio > 0.005:
            severity = "Low"
        else:
            severity = "Negligible"

        # 6. Generate Heatmap and Contour GeoJSON
        heatmap_filename = f"diff_heatmap_{tile_id}_{date_t1}_{date_t2}.png"
        heatmap_path = os.path.join(CHANGE_OUTPUT_DIR, heatmap_filename)
        
        # Colorize difference heatmap (Jet / Turbo colormap)
        heat_colored = cv2.applyColorMap((combined_diff * 255).astype(np.uint8), cv2.COLORMAP_JET)
        # Blend with grayscale T2
        blend_gray = cv2.cvtColor(gray2, cv2.COLOR_GRAY2BGR)
        diff_overlay = cv2.addWeighted(blend_gray, 0.4, heat_colored, 0.6, 0)
        cv2.imwrite(heatmap_path, cv2.cvtColor(diff_overlay, cv2.COLOR_BGR2RGB))

        # Vector contour polygons in EPSG:4326 geospatial coordinates
        # bbox is [min_lat, min_lon, max_lat, max_lon]
        min_lat, min_lon, max_lat, max_lon = bbox
        h_img, w_img = cleaned_mask.shape
        contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        geojson_polygons = []
        for cnt in contours:
            if cv2.contourArea(cnt) > 40:
                coords = []
                for pt in cnt[:, 0, :]:
                    px, py = pt
                    # Map pixel (px, py) to (lat, lon)
                    lon = min_lon + (px / w_img) * (max_lon - min_lon)
                    lat = max_lat - (py / h_img) * (max_lat - min_lat)
                    coords.append([round(lon, 6), round(lat, 6)])
                if coords:
                    coords.append(coords[0])  # Close polygon ring
                    geojson_polygons.append({
                        "type": "Feature",
                        "properties": {
                            "change_type": change_type,
                            "subtype": subtype,
                            "area_pixels": int(cv2.contourArea(cnt))
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [coords]
                        }
                    })

        return {
            "tile_id": tile_id,
            "change_detected": bool(change_type != "No Significant Change" and (confidence_score >= 0.08 or change_pixels > 25)),
            "change_type": change_type,
            "subtype": subtype,
            "severity": severity,
            "change_magnitude": round(raw_magnitude, 4),
            "change_ratio": round(change_ratio, 4),
            "confidence_score": confidence_score,
            "quality_score_t1": round(q_score_t1, 3),
            "quality_score_t2": round(q_score_t2, 3),
            "diff_heatmap_path": f"/data/tiles/changes/{heatmap_filename}",
            "geojson": {
                "type": "FeatureCollection",
                "features": geojson_polygons
            },
            "center_coords": [
                round((min_lat + max_lat) / 2.0, 6),
                round((min_lon + max_lon) / 2.0, 6)
            ]
        }
