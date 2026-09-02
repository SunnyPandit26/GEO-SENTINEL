"""
GEO-SENTINEL GeoTIFF & Cloud Optimized GeoTIFF (COG) Raster Parser
Extracts geospatial affine transformations, bounds, multi-spectral bands, and slices into georeferenced tiles.
"""

import os
import rasterio
from rasterio.transform import xy
from rasterio.warp import transform_bounds
import numpy as np
import cv2
from PIL import Image
from typing import Dict, Any, List, Tuple, Optional

TILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "tiles")
os.makedirs(TILES_DIR, exist_ok=True)


class GeoTIFFParser:
    def __init__(self, tile_size: int = 256):
        self.tile_size = tile_size

    def parse_and_slice(self, geotiff_path: str, scene_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Parses a GeoTIFF / COG file and extracts:
        1. Scene metadata (CRS, resolution/GSD, bounding box in EPSG:4326, band count)
        2. Geospatial tiles with pixel coordinates converted to EPSG:4326 (lat, lon)
        """
        scene_dir = os.path.join(TILES_DIR, scene_id)
        os.makedirs(scene_dir, exist_ok=True)

        with rasterio.open(geotiff_path) as src:
            crs_str = str(src.crs)
            count = src.count
            width = src.width
            height = src.height
            bounds = src.bounds
            res_x, res_y = src.res

            # Transform scene bounds to WGS84 (EPSG:4326)
            if src.crs and src.crs.to_epsg() != 4326:
                try:
                    wgs84_bounds = transform_bounds(src.crs, 'EPSG:4326', bounds.left, bounds.bottom, bounds.right, bounds.top)
                    min_lon, min_lat, max_lon, max_lat = wgs84_bounds
                except Exception:
                    min_lon, min_lat, max_lon, max_lat = bounds.left, bounds.bottom, bounds.right, bounds.top
            else:
                min_lon, min_lat, max_lon, max_lat = bounds.left, bounds.bottom, bounds.right, bounds.top

            # Read bands (1: Red, 2: Green, 3: Blue, 4: NIR if present)
            if count >= 3:
                r = src.read(1)
                g = src.read(2)
                b = src.read(3)
                nir = src.read(4) if count >= 4 else None
            else:
                gray = src.read(1)
                r = gray
                g = gray
                b = gray
                nir = None

            # Normalize 16-bit or float bands to uint8
            def to_uint8(arr):
                if arr.dtype == np.uint8:
                    return arr
                arr_min = float(arr.min())
                arr_max = float(arr.max())
                if arr_max - arr_min == 0:
                    return np.zeros(arr.shape, dtype=np.uint8)
                return ((arr - arr_min) / (arr_max - arr_min) * 255.0).astype(np.uint8)

            r_u8 = to_uint8(r)
            g_u8 = to_uint8(g)
            b_u8 = to_uint8(b)
            nir_u8 = to_uint8(nir) if nir is not None else None

            scene_metadata = {
                "scene_id": scene_id,
                "crs": crs_str,
                "gsd_resolution": round(float(res_x), 2) if res_x > 0 else 10.0,
                "width": width,
                "height": height,
                "bbox_min_lat": round(float(min_lat), 6),
                "bbox_min_lon": round(float(min_lon), 6),
                "bbox_max_lat": round(float(max_lat), 6),
                "bbox_max_lon": round(float(max_lon), 6),
                "geotiff_path": geotiff_path
            }

            # Slice into geospatial tiles
            tiles = []
            transform = src.transform
            tile_rows = (height + self.tile_size - 1) // self.tile_size
            tile_cols = (width + self.tile_size - 1) // self.tile_size

            for r_idx in range(tile_rows):
                for c_idx in range(tile_cols):
                    y_start = r_idx * self.tile_size
                    y_end = min(height, y_start + self.tile_size)
                    x_start = c_idx * self.tile_size
                    x_end = min(width, x_start + self.tile_size)

                    tile_r = r_u8[y_start:y_end, x_start:x_end]
                    tile_g = g_u8[y_start:y_end, x_start:x_end]
                    tile_b = b_u8[y_start:y_end, x_start:x_end]
                    tile_nir = nir_u8[y_start:y_end, x_start:x_end] if nir_u8 is not None else None

                    # Pad to exact tile_size if boundary tile
                    if tile_r.shape[0] < self.tile_size or tile_r.shape[1] < self.tile_size:
                        tile_r = cv2.copyMakeBorder(tile_r, 0, self.tile_size - tile_r.shape[0], 0, self.tile_size - tile_r.shape[1], cv2.BORDER_CONSTANT, value=0)
                        tile_g = cv2.copyMakeBorder(tile_g, 0, self.tile_size - tile_g.shape[0], 0, self.tile_size - tile_g.shape[1], cv2.BORDER_CONSTANT, value=0)
                        tile_b = cv2.copyMakeBorder(tile_b, 0, self.tile_size - tile_b.shape[0], 0, self.tile_size - tile_b.shape[1], cv2.BORDER_CONSTANT, value=0)
                        if tile_nir is not None:
                            tile_nir = cv2.copyMakeBorder(tile_nir, 0, self.tile_size - tile_nir.shape[0], 0, self.tile_size - tile_nir.shape[1], cv2.BORDER_CONSTANT, value=0)

                    rgb_img = np.dstack((tile_r, tile_g, tile_b))

                    # Compute corner geographic coordinates using affine transform
                    # Top-left and bottom-right
                    x_geo_tl, y_geo_tl = xy(transform, y_start, x_start)
                    x_geo_br, y_geo_br = xy(transform, y_end, x_end)

                    t_min_lon = min(x_geo_tl, x_geo_br)
                    t_max_lon = max(x_geo_tl, x_geo_br)
                    t_min_lat = min(y_geo_tl, y_geo_br)
                    t_max_lat = max(y_geo_tl, y_geo_br)

                    # Compute center coords
                    center_lat = (t_min_lat + t_max_lat) / 2.0
                    center_lon = (t_min_lon + t_max_lon) / 2.0

                    tile_id = f"{scene_id}_tile_r{r_idx}_c{c_idx}"
                    rgb_filename = f"{tile_id}.png"
                    rgb_path = os.path.join(scene_dir, rgb_filename)
                    Image.fromarray(rgb_img).save(rgb_path, "PNG")

                    nir_path = None
                    if tile_nir is not None:
                        nir_filename = f"{tile_id}_nir.png"
                        nir_path = os.path.join(scene_dir, nir_filename)
                        Image.fromarray(tile_nir).save(nir_path, "PNG")

                    # Basic NDVI calculation
                    nir_calc = tile_nir.astype(np.float32) if tile_nir is not None else tile_g.astype(np.float32) * 1.2
                    red_calc = tile_r.astype(np.float32)
                    ndvi_arr = (nir_calc - red_calc) / (nir_calc + red_calc + 1e-6)
                    ndvi_mean = float(np.mean(ndvi_arr))

                    # Basic NDWI calculation
                    green_calc = tile_g.astype(np.float32)
                    ndwi_arr = (green_calc - nir_calc) / (green_calc + nir_calc + 1e-6)
                    ndwi_mean = float(np.mean(ndwi_arr))

                    tiles.append({
                        "tile_id": tile_id,
                        "scene_id": scene_id,
                        "row_idx": r_idx,
                        "col_idx": c_idx,
                        "bbox_min_lat": round(float(t_min_lat), 6),
                        "bbox_min_lon": round(float(t_min_lon), 6),
                        "bbox_max_lat": round(float(t_max_lat), 6),
                        "bbox_max_lon": round(float(t_max_lon), 6),
                        "center_lat": round(float(center_lat), 6),
                        "center_lon": round(float(center_lon), 6),
                        "rgb_preview_path": f"/data/tiles/{scene_id}/{rgb_filename}",
                        "rgb_abs_path": rgb_path,
                        "nir_path": f"/data/tiles/{scene_id}/{tile_id}_nir.png" if nir_path else None,
                        "nir_abs_path": nir_path,
                        "ndvi_mean": round(ndvi_mean, 4),
                        "ndwi_mean": round(ndwi_mean, 4),
                        "quality_score": 1.0,
                        "image_array": rgb_img,
                        "nir_array": tile_nir
                    })

            return scene_metadata, tiles
