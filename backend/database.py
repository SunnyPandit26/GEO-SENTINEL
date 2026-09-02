"""
GEO-SENTINEL Database Layer
High-concurrency SQLite storage for geospatial tiles, scenes, change events, analyst triage, and provenance metadata.
"""

import sqlite3
import json
import os
import time
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "geosentinel.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Scenes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scenes (
        scene_id TEXT PRIMARY KEY,
        acquisition_date TEXT NOT NULL,
        sensor_name TEXT NOT NULL,
        gsd_resolution REAL NOT NULL,
        sun_elevation REAL,
        sun_azimuth REAL,
        cloud_cover_percentage REAL,
        bbox_min_lat REAL,
        bbox_min_lon REAL,
        bbox_max_lat REAL,
        bbox_max_lon REAL,
        crs TEXT,
        geotiff_path TEXT NOT NULL,
        ingested_at REAL NOT NULL
    )
    """)

    # 2. Geospatial Tiles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tiles (
        tile_id TEXT PRIMARY KEY,
        scene_id TEXT NOT NULL,
        row_idx INTEGER NOT NULL,
        col_idx INTEGER NOT NULL,
        bbox_min_lat REAL NOT NULL,
        bbox_min_lon REAL NOT NULL,
        bbox_max_lat REAL NOT NULL,
        bbox_max_lon REAL NOT NULL,
        center_lat REAL NOT NULL,
        center_lon REAL NOT NULL,
        rgb_preview_path TEXT NOT NULL,
        nir_path TEXT,
        qa_mask_path TEXT,
        ndvi_mean REAL,
        ndwi_mean REAL,
        quality_score REAL NOT NULL,
        embedding_id INTEGER,
        metadata_json TEXT,
        FOREIGN KEY (scene_id) REFERENCES scenes (scene_id)
    )
    """)

    # 3. Change Events table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS change_events (
        change_id TEXT PRIMARY KEY,
        tile_id TEXT NOT NULL,
        scene_t1_id TEXT NOT NULL,
        scene_t2_id TEXT NOT NULL,
        date_t1 TEXT NOT NULL,
        date_t2 TEXT NOT NULL,
        change_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        change_magnitude REAL NOT NULL,
        confidence_score REAL NOT NULL,
        earliest_observation_date TEXT NOT NULL,
        onset_confidence REAL NOT NULL,
        center_lat REAL NOT NULL,
        center_lon REAL NOT NULL,
        bbox_json TEXT NOT NULL,
        polygon_geojson TEXT,
        diff_heatmap_path TEXT,
        quality_factor REAL NOT NULL,
        triage_status TEXT NOT NULL DEFAULT 'unreviewed',
        analyst_notes TEXT,
        created_at REAL NOT NULL,
        FOREIGN KEY (tile_id) REFERENCES tiles (tile_id)
    )
    """)

    # 4. Analyst Reviews & Audit Trail
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analyst_reviews (
        review_id TEXT PRIMARY KEY,
        change_id TEXT NOT NULL,
        analyst_id TEXT NOT NULL,
        action TEXT NOT NULL,
        previous_status TEXT,
        new_status TEXT NOT NULL,
        notes TEXT,
        timestamp REAL NOT NULL,
        rerank_weight_delta REAL DEFAULT 0.0,
        FOREIGN KEY (change_id) REFERENCES change_events (change_id)
    )
    """)

    # 5. Full Geospatial Provenance Records (STAC & Processing Lineage)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS provenance_records (
        provenance_id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        stac_item_json TEXT NOT NULL,
        processing_lineage_json TEXT NOT NULL,
        crypto_hash TEXT NOT NULL,
        created_at REAL NOT NULL
    )
    """)

    # Indexes for rapid geospatial & temporal retrieval
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiles_coords ON tiles (center_lat, center_lon)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiles_scene ON tiles (scene_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenes_date ON scenes (acquisition_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_changes_triage ON change_events (triage_status, confidence_score)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
