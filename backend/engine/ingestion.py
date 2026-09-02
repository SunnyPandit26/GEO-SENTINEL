"""
GEO-SENTINEL Incremental Ingestion Pipeline
Fulfills Capability 2.2.6: Dynamically ingests new GeoTIFF / COG scenes, slices georeferenced tiles,
computes multimodal embeddings, and updates FAISS vector index & SQLite catalog incrementally with zero downtime.
"""

import os
import time
import json
import numpy as np
from typing import Dict, Any, List, Optional
from backend.database import get_db_connection
from backend.engine.geotiff_parser import GeoTIFFParser
from backend.engine.embeddings import MultimodalEmbeddingEngine
from backend.engine.vector_index import VectorIndexEngine
from backend.engine.quality_filter import QualityFilterEngine


class IngestionPipeline:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.parser = GeoTIFFParser(tile_size=256)
        self.embedding_engine = MultimodalEmbeddingEngine.get_instance()
        self.vector_index = VectorIndexEngine.get_instance()
        self.quality_filter = QualityFilterEngine.get_instance()

    def ingest_scene(
        self,
        geotiff_path: str,
        scene_id: str,
        acquisition_date: str,
        sensor_name: str = "Sentinel-2 MSI",
        sun_elevation: float = 58.4,
        sun_azimuth: float = 142.1,
        cloud_cover_percentage: float = 2.1
    ) -> Dict[str, Any]:
        """
        Incrementally processes and indexes a newly acquired GeoTIFF scene.
        """
        start_time = time.time()
        print(f"[IngestionPipeline] Starting ingestion of {scene_id} from {geotiff_path}...")

        # 1. Parse raster & slice into tiles
        scene_meta, tiles = self.parser.parse_and_slice(geotiff_path, scene_id)
        
        # 2. Quality masking & Embedding Extraction
        tile_ids = []
        embeddings_list = []
        metadatas = []
        db_records = []

        for t in tiles:
            # Quality assessment
            qa_mask, q_score = self.quality_filter.compute_quality_mask(t["image_array"], t.get("nir_array"))
            t["quality_score"] = round(q_score, 3)

            # Compute multimodal embedding vector
            emb = self.embedding_engine.embed_image(t["image_array"])
            embeddings_list.append(emb)
            tile_ids.append(t["tile_id"])

            meta_entry = {
                "scene_id": scene_id,
                "acquisition_date": acquisition_date,
                "sensor_name": sensor_name,
                "gsd_resolution": scene_meta["gsd_resolution"],
                "center_lat": t["center_lat"],
                "center_lon": t["center_lon"],
                "bbox_min_lat": t["bbox_min_lat"],
                "bbox_min_lon": t["bbox_min_lon"],
                "bbox_max_lat": t["bbox_max_lat"],
                "bbox_max_lon": t["bbox_max_lon"],
                "rgb_preview_path": t["rgb_preview_path"],
                "nir_path": t.get("nir_path"),
                "quality_score": t["quality_score"],
                "ndvi_mean": t["ndvi_mean"],
                "ndwi_mean": t["ndwi_mean"]
            }
            metadatas.append(meta_entry)

            db_records.append((
                t["tile_id"],
                scene_id,
                t["row_idx"],
                t["col_idx"],
                t["bbox_min_lat"],
                t["bbox_min_lon"],
                t["bbox_max_lat"],
                t["bbox_max_lon"],
                t["center_lat"],
                t["center_lon"],
                t["rgb_preview_path"],
                t.get("nir_path"),
                None,  # QA mask path
                t["ndvi_mean"],
                t["ndwi_mean"],
                t["quality_score"],
                None,  # embedding_id
                json.dumps(meta_entry)
            ))

        # 3. Incremental update into FAISS Vector Index
        assigned_ids = self.vector_index.add_batch(
            tile_ids=tile_ids,
            embeddings=np.array(embeddings_list, dtype=np.float32),
            metadatas=metadatas
        )

        # 4. Save metadata to SQLite Database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert Scene
        cursor.execute("""
        INSERT OR REPLACE INTO scenes (
            scene_id, acquisition_date, sensor_name, gsd_resolution,
            sun_elevation, sun_azimuth, cloud_cover_percentage,
            bbox_min_lat, bbox_min_lon, bbox_max_lat, bbox_max_lon,
            crs, geotiff_path, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scene_id, acquisition_date, sensor_name, scene_meta["gsd_resolution"],
            sun_elevation, sun_azimuth, cloud_cover_percentage,
            scene_meta["bbox_min_lat"], scene_meta["bbox_min_lon"],
            scene_meta["bbox_max_lat"], scene_meta["bbox_max_lon"],
            scene_meta["crs"], geotiff_path, time.time()
        ))

        # Insert Tiles
        cursor.executemany("""
        INSERT OR REPLACE INTO tiles (
            tile_id, scene_id, row_idx, col_idx,
            bbox_min_lat, bbox_min_lon, bbox_max_lat, bbox_max_lon,
            center_lat, center_lon, rgb_preview_path, nir_path,
            qa_mask_path, ndvi_mean, ndwi_mean, quality_score,
            embedding_id, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, db_records)

        conn.commit()
        conn.close()

        elapsed = round(time.time() - start_time, 3)
        throughput = round(len(tiles) / max(0.001, elapsed), 1)
        print(f"[IngestionPipeline] Ingested {len(tiles)} tiles in {elapsed}s ({throughput} tiles/sec). Total indexed: {self.vector_index.index.ntotal}")

        return {
            "status": "success",
            "scene_id": scene_id,
            "tiles_ingested": len(tiles),
            "total_indexed_tiles": self.vector_index.index.ntotal,
            "elapsed_seconds": elapsed,
            "throughput_tiles_per_sec": throughput,
            "spatial_extent": [scene_meta["bbox_min_lat"], scene_meta["bbox_min_lon"], scene_meta["bbox_max_lat"], scene_meta["bbox_max_lon"]]
        }
