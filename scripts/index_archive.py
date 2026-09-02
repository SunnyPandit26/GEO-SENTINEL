"""
GEO-SENTINEL Archive Indexing & Change Synthesis Script
Ingests all generated multi-temporal GeoTIFF scenes into FAISS vector database
and synthesizes multi-temporal change detection candidates into SQLite review queue.
"""

import os
import sys
import glob
import time
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database import init_db, get_db_connection
from backend.engine.ingestion import IngestionPipeline
from backend.engine.change_detector import ChangeDetectorEngine
from PIL import Image
import numpy as np


def index_all_scenes():
    init_db()
    ingestor = IngestionPipeline.get_instance()
    scenes_dir = os.path.join(BASE_DIR, "data", "scenes")
    tif_files = glob.glob(os.path.join(scenes_dir, "*.tif"))
    tif_files.sort()

    print(f"Found {len(tif_files)} GeoTIFF scenes to ingest...")

    scene_catalog = []
    for filepath in tif_files:
        basename = os.path.basename(filepath)
        # format: scene_{name}_{step}_{date}.tif
        parts = basename.replace(".tif", "").split("_")
        date_str = parts[-1]
        scene_id = "_".join(parts[:-1])

        print(f"Ingesting scene: {scene_id} ({date_str})...")
        res = ingestor.ingest_scene(
            geotiff_path=filepath,
            scene_id=scene_id,
            acquisition_date=date_str,
            sensor_name="Sentinel-2 MSI"
        )
        scene_catalog.append((scene_id, date_str))

    print("All scenes indexed successfully! Now synthesizing multi-temporal change events...")
    synthesize_change_events()


def synthesize_change_events():
    """Performs bi-temporal change detection across multi-date acquisitions and populates change_events."""
    detector = ChangeDetectorEngine.get_instance()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get distinct scenarios
    scenarios = [
        ("scene_urban_river_1", "scene_urban_river_4", "Riverfront Urban Development", "2025-04-15"),
        ("scene_urban_river_1", "scene_urban_river_3", "Foundation & Crane Works", "2025-04-15"),
        ("scene_forest_clearance_1", "scene_forest_clearance_4", "Deforestation Sector Bravo", "2025-08-12"),
        ("scene_forest_clearance_1", "scene_forest_clearance_3", "Clear-cut Timber Patch", "2025-08-12"),
        ("scene_water_inundation_1", "scene_water_inundation_3", "Monsoon Floodplain Inundation", "2025-07-28"),
        ("scene_airfield_transport_1", "scene_airfield_transport_4", "Airfield Logistics Expansion", "2025-07-19"),
        ("scene_airfield_transport_1", "scene_airfield_transport_3", "Parallel Runway Construction", "2025-07-19")
    ]

    change_records = []
    for s1_id, s2_id, aoi_name, earliest_date in scenarios:
        cursor.execute("SELECT * FROM tiles WHERE scene_id = ?", (s1_id,))
        t1_tiles = {f"{r['row_idx']}_{r['col_idx']}": dict(r) for r in cursor.fetchall()}
        cursor.execute("SELECT * FROM tiles WHERE scene_id = ?", (s2_id,))
        t2_tiles = {f"{r['row_idx']}_{r['col_idx']}": dict(r) for r in cursor.fetchall()}

        cursor.execute("SELECT acquisition_date FROM scenes WHERE scene_id = ?", (s1_id,))
        s1_date = cursor.fetchone()["acquisition_date"]
        cursor.execute("SELECT acquisition_date FROM scenes WHERE scene_id = ?", (s2_id,))
        s2_date = cursor.fetchone()["acquisition_date"]

        for key, t1 in t1_tiles.items():
            if key not in t2_tiles:
                continue
            t2 = t2_tiles[key]

            p1 = os.path.join(BASE_DIR, t1["rgb_preview_path"].lstrip("/"))
            p2 = os.path.join(BASE_DIR, t2["rgb_preview_path"].lstrip("/"))

            img1 = np.array(Image.open(p1).convert("RGB"))
            img2 = np.array(Image.open(p2).convert("RGB"))

            nir1 = np.array(Image.open(os.path.join(BASE_DIR, t1["nir_path"].lstrip("/")))) if t1["nir_path"] else None
            nir2 = np.array(Image.open(os.path.join(BASE_DIR, t2["nir_path"].lstrip("/")))) if t2["nir_path"] else None

            bbox = [t1["bbox_min_lat"], t1["bbox_min_lon"], t1["bbox_max_lat"], t1["bbox_max_lon"]]

            res = detector.analyze_change(
                img_t1=img1,
                img_t2=img2,
                bbox=bbox,
                tile_id=t2["tile_id"],
                nir_t1=nir1,
                nir_t2=nir2,
                date_t1=s1_date,
                date_t2=s2_date
            )

            if res["change_detected"]:
                change_id = f"chg_{s1_id}_{s2_id}_{key}"
                change_records.append((
                    change_id,
                    t2["tile_id"],
                    s1_id,
                    s2_id,
                    s1_date,
                    s2_date,
                    res["change_type"],
                    res["severity"],
                    res["change_magnitude"],
                    res["confidence_score"],
                    earliest_date,
                    0.92,
                    res["center_coords"][0],
                    res["center_coords"][1],
                    json.dumps(bbox),
                    json.dumps(res["geojson"]),
                    res["diff_heatmap_path"],
                    min(res["quality_score_t1"], res["quality_score_t2"]),
                    "unreviewed",
                    None,
                    time.time()
                ))

    cursor.executemany("""
    INSERT OR REPLACE INTO change_events (
        change_id, tile_id, scene_t1_id, scene_t2_id,
        date_t1, date_t2, change_type, severity,
        change_magnitude, confidence_score, earliest_observation_date, onset_confidence,
        center_lat, center_lon, bbox_json, polygon_geojson, diff_heatmap_path,
        quality_factor, triage_status, analyst_notes, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, change_records)

    conn.commit()
    conn.close()
    print(f"Synthesized and populated {len(change_records)} change candidates into review queue!")


if __name__ == "__main__":
    index_all_scenes()
