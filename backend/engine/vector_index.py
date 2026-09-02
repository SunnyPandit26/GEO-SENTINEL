"""
GEO-SENTINEL High-Performance Vector Indexing Engine
Powered by FAISS with incremental indexing, cosine metric, and hybrid spatial-temporal-quality re-ranking.
"""

import os
import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import faiss

INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "index_storage")


class VectorIndexEngine:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, embedding_dim: int = 512):
        self.embedding_dim = embedding_dim
        self.index_file = os.path.join(INDEX_DIR, "faiss_index.bin")
        self.meta_file = os.path.join(INDEX_DIR, "index_metadata.json")
        os.makedirs(INDEX_DIR, exist_ok=True)

        # In-memory metadata map: id -> metadata dictionary
        self.id_to_meta: Dict[int, Dict[str, Any]] = {}
        self.tile_to_id: Dict[str, int] = {}
        self.next_id: int = 0

        # FAISS Index: Inner Product on L2-normalized vectors == Cosine Similarity
        self.index = faiss.IndexIDMap2(faiss.IndexFlatIP(self.embedding_dim))
        
        self.load()

    def add_tile(self, tile_id: str, embedding: np.ndarray, metadata: Dict[str, Any]) -> int:
        """Incrementally adds a single tile embedding without index rebuild."""
        return self.add_batch([tile_id], np.expand_dims(embedding, axis=0), [metadata])[0]

    def add_batch(self, tile_ids: List[str], embeddings: np.ndarray, metadatas: List[Dict[str, Any]]) -> List[int]:
        """Incrementally adds a batch of embeddings to FAISS with direct ID mapping."""
        assigned_ids = []
        vectors = np.ascontiguousarray(embeddings.astype(np.float32))

        # Normalize to unit vectors for exact cosine similarity
        faiss.normalize_L2(vectors)

        new_ids = []
        for i, tid in enumerate(tile_ids):
            if tid in self.tile_to_id:
                curr_id = self.tile_to_id[tid]
            else:
                curr_id = self.next_id
                self.next_id += 1
                self.tile_to_id[tid] = curr_id

            self.id_to_meta[curr_id] = {
                "tile_id": tid,
                **metadatas[i]
            }
            new_ids.append(curr_id)
            assigned_ids.append(curr_id)

        ids_array = np.array(new_ids, dtype=np.int64)
        self.index.add_with_ids(vectors, ids_array)
        self.save()
        return assigned_ids

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 20,
        aoi_bbox: Optional[Dict[str, float]] = None,
        date_range: Optional[Tuple[str, str]] = None,
        sensor_filter: Optional[str] = None,
        min_quality: float = 0.0,
        weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid semantic search combining:
        1. Multimodal vector cosine similarity
        2. Spatial intersection with AOI bounding box
        3. Temporal date filter
        4. Sensor platform matching
        5. Quality score weighting
        """
        if self.index.ntotal == 0:
            return []

        q_vec = np.ascontiguousarray(np.expand_dims(query_vector, axis=0).astype(np.float32))
        faiss.normalize_L2(q_vec)

        # Retrieve candidate pool for hybrid reranking (top 5x candidates)
        pool_k = min(self.index.ntotal, max(top_k * 5, 50))
        similarities, indices = self.index.search(q_vec, pool_k)

        w_semantic = weights.get("semantic", 0.70) if weights else 0.70
        w_quality = weights.get("quality", 0.15) if weights else 0.15
        w_spatial = weights.get("spatial", 0.15) if weights else 0.15

        results = []
        for sim, idx in zip(similarities[0], indices[0]):
            if idx == -1 or idx not in self.id_to_meta:
                continue

            meta = self.id_to_meta[idx]
            
            # 1. Sensor Filter
            if sensor_filter and sensor_filter.lower() not in meta.get("sensor_name", "").lower():
                continue

            # 2. Temporal Date Range Filter
            acq_date = meta.get("acquisition_date", "")
            if date_range:
                start_date, end_date = date_range
                if start_date and acq_date < start_date:
                    continue
                if end_date and acq_date > end_date:
                    continue

            # 3. Quality Filter
            quality_score = meta.get("quality_score", 1.0)
            if quality_score < min_quality:
                continue

            # 4. Spatial Overlap Score
            spatial_score = 1.0
            if aoi_bbox:
                # Check if tile center falls in AOI bbox [min_lat, min_lon, max_lat, max_lon]
                t_lat = meta.get("center_lat", 0.0)
                t_lon = meta.get("center_lon", 0.0)
                in_lat = aoi_bbox.get("min_lat", -90) <= t_lat <= aoi_bbox.get("max_lat", 90)
                in_lon = aoi_bbox.get("min_lon", -180) <= t_lon <= aoi_bbox.get("max_lon", 180)
                spatial_score = 1.0 if (in_lat and in_lon) else 0.2

            # Hybrid Score Calculation
            raw_cosine = float(sim)
            # Rescale cosine [-1, 1] to [0, 1]
            norm_cosine = max(0.0, min(1.0, (raw_cosine + 1.0) / 2.0))
            
            composite_score = (
                w_semantic * norm_cosine +
                w_quality * quality_score +
                w_spatial * spatial_score
            )

            results.append({
                "tile_id": meta.get("tile_id"),
                "similarity_score": round(norm_cosine, 4),
                "composite_score": round(composite_score, 4),
                "scene_id": meta.get("scene_id"),
                "acquisition_date": meta.get("acquisition_date"),
                "sensor_name": meta.get("sensor_name"),
                "gsd_resolution": meta.get("gsd_resolution", 10.0),
                "center_lat": meta.get("center_lat"),
                "center_lon": meta.get("center_lon"),
                "bbox": [
                    meta.get("bbox_min_lat"), meta.get("bbox_min_lon"),
                    meta.get("bbox_max_lat"), meta.get("bbox_max_lon")
                ],
                "rgb_preview_path": meta.get("rgb_preview_path"),
                "quality_score": quality_score,
                "ndvi_mean": meta.get("ndvi_mean", 0.0),
                "ndwi_mean": meta.get("ndwi_mean", 0.0),
                "metadata": meta
            })

        # Rank order by composite score
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results[:top_k]

    def save(self):
        """Saves FAISS index and metadata state to disk."""
        faiss.write_index(self.index, self.index_file)
        with open(self.meta_file, "w") as f:
            json.dump({
                "next_id": self.next_id,
                "tile_to_id": self.tile_to_id,
                "id_to_meta": self.id_to_meta
            }, f, indent=2)

    def load(self):
        """Loads FAISS index and metadata from disk if available."""
        if os.path.exists(self.index_file) and os.path.exists(self.meta_file):
            try:
                self.index = faiss.read_index(self.index_file)
                with open(self.meta_file, "r") as f:
                    data = json.load(f)
                    self.next_id = data.get("next_id", 0)
                    self.tile_to_id = data.get("tile_to_id", {})
                    # JSON keys are strings, convert back to int
                    self.id_to_meta = {int(k): v for k, v in data.get("id_to_meta", {}).items()}
                print(f"[VectorIndexEngine] Loaded FAISS index with {self.index.ntotal} vectors.")
            except Exception as e:
                print(f"[VectorIndexEngine] Error loading index: {e}, initializing clean index.")
                self.index = faiss.IndexIDMap2(faiss.IndexFlatIP(self.embedding_dim))
