"""
GEO-SENTINEL Discovery & Unsupervised Clustering Engine
Fulfills Capability 2.2.4: Groups similar sites across wide areas using dense embedding clustering
and 2D semantic projection, enabling one-click discovery of comparable locations without manual queries.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA


class ClusterDiscoveryEngine:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, n_clusters: int = 6):
        self.n_clusters = n_clusters

    def cluster_archive(self, tiles_data: List[Dict[str, Any]], embeddings: np.ndarray) -> Dict[str, Any]:
        """
        Computes unsupervised semantic clusters and 2D projection coordinates for all indexed tiles.
        """
        n_samples = len(tiles_data)
        if n_samples == 0:
            return {"clusters": [], "points": []}

        actual_k = min(self.n_clusters, max(2, n_samples // 3))
        
        # 1. K-Means clustering in 512-dim embedding space
        kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings)

        # 2. 2D Dimensionality Reduction (PCA / Multi-Dimensional Scaling)
        pca_2d = PCA(n_components=2, random_state=42)
        coords_2d = pca_2d.fit_transform(embeddings)
        # Normalize to [-100, 100] for visual canvas rendering
        c_min = coords_2d.min(axis=0)
        c_max = coords_2d.max(axis=0)
        ranges = np.where(c_max - c_min == 0, 1.0, c_max - c_min)
        coords_norm = ((coords_2d - c_min) / ranges) * 200.0 - 100.0

        # 3. Form Cluster Summaries & Exemplars
        cluster_map = {i: [] for i in range(actual_k)}
        points = []

        for i, tile in enumerate(tiles_data):
            c_label = int(cluster_labels[i])
            x_2d = float(coords_norm[i, 0])
            y_2d = float(coords_norm[i, 1])

            point_obj = {
                "tile_id": tile["tile_id"],
                "scene_id": tile.get("scene_id"),
                "cluster_id": c_label,
                "center_lat": tile.get("center_lat"),
                "center_lon": tile.get("center_lon"),
                "preview_path": tile.get("rgb_preview_path"),
                "quality_score": tile.get("quality_score", 1.0),
                "proj_x": round(x_2d, 2),
                "proj_y": round(y_2d, 2),
                "ndvi": tile.get("ndvi_mean", 0.0),
                "ndwi": tile.get("ndwi_mean", 0.0)
            }
            points.append(point_obj)
            cluster_map[c_label].append((i, point_obj))

        # Semantic cluster auto-labeling & exemplar identification
        clusters_summary = []
        cluster_theme_names = [
            "Urban Infrastructure & Built Structures",
            "Water Bodies & Riverfront Systems",
            "Forest Canopy & Dense Vegetation",
            "Transport Corridors & Road Networks",
            "Industrial & Warehouse Complexes",
            "Bare Soil & Cleared Land"
        ]

        for c_id, members in cluster_map.items():
            if not members:
                continue

            member_indices = [m[0] for m in members]
            member_embeddings = embeddings[member_indices]
            centroid = kmeans.cluster_centers_[c_id]

            # Find exemplar: member with minimum Euclidean distance to centroid
            distances = np.linalg.norm(member_embeddings - centroid, axis=1)
            exemplar_idx_in_cluster = int(np.argmin(distances))
            exemplar_point = members[exemplar_idx_in_cluster][1]

            # Determine dominant cluster characteristics
            avg_ndvi = float(np.mean([m[1]["ndvi"] for m in members]))
            avg_ndwi = float(np.mean([m[1]["ndwi"] for m in members]))

            if avg_ndwi > 0.15:
                theme = "Water Bodies & Inundation Zones"
                color = "#00b4d8"
            elif avg_ndvi > 0.35:
                theme = "Forest Canopy & Dense Vegetation"
                color = "#2ec4b6"
            elif avg_ndvi < 0.05 and avg_ndwi < -0.1:
                theme = "Urban Built-Up & Concrete Structures"
                color = "#e63946"
            else:
                theme = cluster_theme_names[c_id % len(cluster_theme_names)]
                colors = ["#ff9f1c", "#9b5de5", "#f15bb5", "#00f5d4", "#fee440", "#00bbf9"]
                color = colors[c_id % len(colors)]

            clusters_summary.append({
                "cluster_id": c_id,
                "label": theme,
                "color": color,
                "count": len(members),
                "exemplar_tile_id": exemplar_point["tile_id"],
                "exemplar_preview": exemplar_point["preview_path"],
                "exemplar_lat": exemplar_point["center_lat"],
                "exemplar_lon": exemplar_point["center_lon"],
                "center_x": round(float(centroid[:2].mean() * 50), 2),
                "center_y": round(float(centroid[2:4].mean() * 50), 2)
            })

        return {
            "total_tiles": n_samples,
            "clusters": clusters_summary,
            "points": points
        }

    def find_similar_across_aoi(
        self,
        query_tile_id: str,
        tiles_data: List[Dict[str, Any]],
        embeddings: np.ndarray,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        One-click discovery: finds all comparable sites across the entire AOI
        given an analyst-identified tile of interest.
        """
        target_idx = None
        for i, t in enumerate(tiles_data):
            if t["tile_id"] == query_tile_id:
                target_idx = i
                break

        if target_idx is None:
            return []

        target_emb = embeddings[target_idx]
        target_norm = target_emb / (np.linalg.norm(target_emb) + 1e-8)

        # Compute cosine similarity across all archive tiles
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8
        norm_embs = embeddings / norms
        sims = np.dot(norm_embs, target_norm)

        # Rank order
        sorted_indices = np.argsort(sims)[::-1]

        similar_results = []
        for idx in sorted_indices:
            if idx == target_idx:
                continue  # Skip self

            sim_val = float(sims[idx])
            t = tiles_data[idx]
            similar_results.append({
                "tile_id": t["tile_id"],
                "similarity_score": round(max(0.0, min(1.0, (sim_val + 1.0) / 2.0)), 4),
                "scene_id": t.get("scene_id"),
                "acquisition_date": t.get("acquisition_date"),
                "center_lat": t.get("center_lat"),
                "center_lon": t.get("center_lon"),
                "bbox": [t.get("bbox_min_lat"), t.get("bbox_min_lon"), t.get("bbox_max_lat"), t.get("bbox_max_lon")],
                "rgb_preview_path": t.get("rgb_preview_path"),
                "quality_score": t.get("quality_score", 1.0)
            })

            if len(similar_results) >= top_k:
                break

        return similar_results
