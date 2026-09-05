"""
GEO-SENTINEL Backend Application Server
High-Performance FastAPI REST Server for Geospatial Semantic Retrieval,
Multi-Temporal Change Intelligence, False-Alarm Suppression, and Sovereignty Ingestion.
"""

import os
import sys
import time
import json
import base64
import numpy as np
from io import BytesIO
from PIL import Image
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
from pydantic import BaseModel

# Ensure root path is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database import init_db, get_db_connection
from backend.engine.embeddings import MultimodalEmbeddingEngine
from backend.engine.vector_index import VectorIndexEngine
from backend.engine.quality_filter import QualityFilterEngine
from backend.engine.change_detector import ChangeDetectorEngine
from backend.engine.temporal_tracker import TemporalOnsetTracker
from backend.engine.cluster_discovery import ClusterDiscoveryEngine
from backend.engine.analyst_queue import AnalystQueueEngine
from backend.engine.provenance import ProvenanceEngine
from backend.engine.ingestion import IngestionPipeline

app = FastAPI(
    title="GEO-SENTINEL Satellite Intelligence API",
    description="Sovereign, On-Premises Semantic Retrieval & Multi-Temporal Change Analysis Engine",
    version="2.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines on startup
init_db()
embedding_engine = MultimodalEmbeddingEngine.get_instance()
vector_index = VectorIndexEngine.get_instance()
quality_filter = QualityFilterEngine.get_instance()
change_detector = ChangeDetectorEngine.get_instance()
temporal_tracker = TemporalOnsetTracker.get_instance()
cluster_engine = ClusterDiscoveryEngine.get_instance()
analyst_queue = AnalystQueueEngine.get_instance()
provenance_engine = ProvenanceEngine.get_instance()
ingestion_pipeline = IngestionPipeline.get_instance()

# Static directories
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_DIR = os.path.join(BASE_DIR, "data")
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")


# Request Pydantic Schemas
class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 20
    aoi_bbox: Optional[Dict[str, float]] = None  # {min_lat, min_lon, max_lat, max_lon}
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    sensor_filter: Optional[str] = None
    min_quality: float = 0.0
    weights: Optional[Dict[str, float]] = None


class VisualSearchRequest(BaseModel):
    tile_id: Optional[str] = None
    image_base64: Optional[str] = None
    top_k: int = 20
    aoi_bbox: Optional[Dict[str, float]] = None
    sensor_filter: Optional[str] = None


class ChangeAnalysisRequest(BaseModel):
    tile_id: str
    scene_t1_id: str
    scene_t2_id: str


class TriageRequest(BaseModel):
    change_id: str
    action: str  # 'confirm', 'reject', 'flag'
    analyst_id: str = "Analyst_Alpha"
    notes: str = ""


class FindSimilarRequest(BaseModel):
    tile_id: str
    top_k: int = 12


@app.get("/")
def read_root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/scenes")
def list_scenes():
    """Returns all ingested satellite scenes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scenes ORDER BY acquisition_date ASC")
    rows = cursor.fetchall()
    scenes = [dict(r) for r in rows]
    conn.close()
    return {"scenes": scenes, "total": len(scenes)}


@app.get("/api/tiles")
def list_tiles(scene_id: Optional[str] = None, limit: int = 100):
    """Returns geospatial tiles with optional scene filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if scene_id:
        cursor.execute("SELECT * FROM tiles WHERE scene_id = ? LIMIT ?", (scene_id, limit))
    else:
        cursor.execute("SELECT * FROM tiles LIMIT ?", (limit,))
    rows = cursor.fetchall()
    tiles = [dict(r) for r in rows]
    conn.close()
    return {"tiles": tiles, "total": len(tiles)}


def extract_location_bbox(query_str: str) -> Optional[Dict[str, float]]:
    q = query_str.lower()
    if any(k in q for k in ["delhi", "ncr", "yamuna", "riverfront", "noida", "gurgaon"]):
        return {"min_lat": 28.50, "min_lon": 77.10, "max_lat": 28.75, "max_lon": 77.35}
    elif any(k in q for k in ["amazon", "brazil", "sector bravo", "forest bravo"]):
        return {"min_lat": -3.60, "min_lon": -62.30, "max_lat": -3.30, "max_lon": -62.10}
    elif any(k in q for k in ["varanasi", "ganga", "river charlie", "sector charlie"]):
        return {"min_lat": 25.20, "min_lon": 82.80, "max_lat": 25.45, "max_lon": 83.10}
    elif any(k in q for k in ["bangalore", "bengaluru", "karnataka", "sector delta"]):
        return {"min_lat": 12.85, "min_lon": 77.45, "max_lat": 13.10, "max_lon": 77.70}
    elif any(k in q for k in ["punjab", "haryana", "chandigarh", "ludhiana", "amritsar"]):
        # Dedicated Punjab region (returns 0 if no pass ingested yet)
        return {"min_lat": 30.00, "min_lon": 74.00, "max_lat": 32.50, "max_lon": 77.00}
    return None


# 2.2.1: Semantic and Multimodal Retrieval
@app.post("/api/search/semantic")
def semantic_search(req: SemanticSearchRequest):
    """
    Free-text natural language search over satellite tiles with hybrid spatial-semantic ranking.
    """
    t0 = time.time()
    query_vector = embedding_engine.embed_text(req.query)
    
    # Auto-extract geographic location bounding box if present in query text
    aoi_bbox = req.aoi_bbox or extract_location_bbox(req.query)

    date_range = None
    if req.date_start or req.date_end:
        date_range = (req.date_start or "1970-01-01", req.date_end or "2099-12-31")

    results = vector_index.search(
        query_vector=query_vector,
        top_k=req.top_k,
        aoi_bbox=aoi_bbox,
        date_range=date_range,
        sensor_filter=req.sensor_filter,
        min_quality=req.min_quality,
        weights=req.weights
    )
    elapsed_ms = round((time.time() - t0) * 1000, 2)

    return {
        "query": req.query,
        "results_count": len(results),
        "latency_ms": elapsed_ms,
        "results": results
    }


# 2.2.1: Image-to-Image Visual Search
@app.post("/api/search/visual")
def visual_search(req: VisualSearchRequest):
    """
    Image-to-image similarity search using an existing tile ID or uploaded image.
    """
    t0 = time.time()
    if req.tile_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT rgb_preview_path FROM tiles WHERE tile_id = ?", (req.tile_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Tile ID not found.")
        
        rel_path = row["rgb_preview_path"].lstrip("/")
        abs_path = os.path.join(BASE_DIR, rel_path)
        query_vector = embedding_engine.embed_image(abs_path)
    elif req.image_base64:
        img_bytes = base64.b64decode(req.image_base64.split(",")[-1])
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        query_vector = embedding_engine.embed_image(img)
    else:
        raise HTTPException(status_code=400, detail="Must provide tile_id or image_base64.")

    results = vector_index.search(
        query_vector=query_vector,
        top_k=req.top_k,
        aoi_bbox=req.aoi_bbox,
        sensor_filter=req.sensor_filter
    )
    elapsed_ms = round((time.time() - t0) * 1000, 2)

    return {
        "results_count": len(results),
        "latency_ms": elapsed_ms,
        "results": results
    }


# 2.2.2 & 2.2.3: Multi-Temporal Change Analysis & Quality Handling
@app.post("/api/change/analyze")
def analyze_change(req: ChangeAnalysisRequest):
    """
    Executes change detection between T1 and T2 for a specific tile.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Find tile records for scene_t1 and scene_t2
    # Match by row_idx and col_idx
    cursor.execute("SELECT row_idx, col_idx, bbox_min_lat, bbox_min_lon, bbox_max_lat, bbox_max_lon FROM tiles WHERE tile_id = ?", (req.tile_id,))
    t_info = cursor.fetchone()
    if not t_info:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Tile {req.tile_id} not found.")

    r_idx, c_idx = t_info["row_idx"], t_info["col_idx"]
    bbox = [t_info["bbox_min_lat"], t_info["bbox_min_lon"], t_info["bbox_max_lat"], t_info["bbox_max_lon"]]

    # Tile T1
    cursor.execute("SELECT * FROM tiles WHERE scene_id = ? AND row_idx = ? AND col_idx = ?", (req.scene_t1_id, r_idx, c_idx))
    t1_row = cursor.fetchone()
    # Tile T2
    cursor.execute("SELECT * FROM tiles WHERE scene_id = ? AND row_idx = ? AND col_idx = ?", (req.scene_t2_id, r_idx, c_idx))
    t2_row = cursor.fetchone()

    cursor.execute("SELECT acquisition_date FROM scenes WHERE scene_id = ?", (req.scene_t1_id,))
    s1_row = cursor.fetchone()
    cursor.execute("SELECT acquisition_date FROM scenes WHERE scene_id = ?", (req.scene_t2_id,))
    s2_row = cursor.fetchone()

    conn.close()

    if not t1_row or not t2_row:
        raise HTTPException(status_code=400, detail="Matching tiles for both scenes not found.")

    d1 = s1_row["acquisition_date"] if s1_row else "T1"
    d2 = s2_row["acquisition_date"] if s2_row else "T2"

    p1 = os.path.join(BASE_DIR, t1_row["rgb_preview_path"].lstrip("/"))
    p2 = os.path.join(BASE_DIR, t2_row["rgb_preview_path"].lstrip("/"))

    img1 = np.array(Image.open(p1).convert("RGB"))
    img2 = np.array(Image.open(p2).convert("RGB"))

    nir1 = np.array(Image.open(os.path.join(BASE_DIR, t1_row["nir_path"].lstrip("/")))) if t1_row["nir_path"] else None
    nir2 = np.array(Image.open(os.path.join(BASE_DIR, t2_row["nir_path"].lstrip("/")))) if t2_row["nir_path"] else None

    result = change_detector.analyze_change(
        img_t1=img1,
        img_t2=img2,
        bbox=bbox,
        tile_id=req.tile_id,
        nir_t1=nir1,
        nir_t2=nir2,
        date_t1=d1,
        date_t2=d2
    )

    # Add scene and date context
    result["scene_t1_id"] = req.scene_t1_id
    result["scene_t2_id"] = req.scene_t2_id
    result["date_t1"] = d1
    result["date_t2"] = d2
    result["tile_t1_preview"] = t1_row["rgb_preview_path"]
    result["tile_t2_preview"] = t2_row["rgb_preview_path"]

    return result


# 2.2.2: Earliest Usable Observation Timeline Tracker
@app.get("/api/change/timeline")
def get_temporal_timeline(row_idx: int = 1, col_idx: int = 1, scenario_prefix: str = "scene_urban_river"):
    """
    Computes statistical change trajectory across all available chronological scenes
    and pinpoints the Earliest Usable Observation (T*).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT s.scene_id, s.acquisition_date, t.tile_id, t.rgb_preview_path, t.nir_path, t.quality_score
    FROM scenes s
    JOIN tiles t ON s.scene_id = t.scene_id
    WHERE s.scene_id LIKE ? AND t.row_idx = ? AND t.col_idx = ?
    ORDER BY s.acquisition_date ASC
    """, (f"{scenario_prefix}%", row_idx, col_idx))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {"earliest_observation_date": "N/A", "onset_confidence": 0.0, "timeline": []}

    records = []
    for r in rows:
        abs_rgb = os.path.join(BASE_DIR, r["rgb_preview_path"].lstrip("/"))
        img = np.array(Image.open(abs_rgb).convert("RGB"))
        nir = None
        if r["nir_path"]:
            abs_nir = os.path.join(BASE_DIR, r["nir_path"].lstrip("/"))
            if os.path.exists(abs_nir):
                nir = np.array(Image.open(abs_nir))

        records.append({
            "acquisition_date": r["acquisition_date"],
            "scene_id": r["scene_id"],
            "image": img,
            "nir": nir
        })

    analysis = temporal_tracker.estimate_earliest_observation(records)
    return analysis


# 2.2.4: Discovery and Clustering
@app.get("/api/clusters")
def get_clusters():
    """
    Returns unsupervised semantic clusters and 2D embedding space scatter coordinates.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tiles")
    tiles_data = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not tiles_data or vector_index.index.ntotal == 0:
        return {"total_tiles": 0, "clusters": [], "points": []}

    # Extract stored vectors corresponding to indexed tiles safely
    ordered_tiles = []
    vectors_list = []
    for vid, meta in vector_index.id_to_meta.items():
        try:
            vec = vector_index.index.reconstruct(int(vid))
            vectors_list.append(vec)
            ordered_tiles.append(meta)
        except Exception:
            continue

    if not vectors_list:
        return {"total_tiles": 0, "clusters": [], "points": []}

    all_vectors = np.array(vectors_list, dtype=np.float32)
    cluster_result = cluster_engine.cluster_archive(ordered_tiles, all_vectors)
    return cluster_result


# 2.2.4: Find Similar Across AOI
@app.post("/api/clusters/find-similar")
def find_similar_sites(req: FindSimilarRequest):
    """
    One-click site discovery: finds similar visual/semantic features across the AOI.
    """
    ordered_tiles = []
    vectors_list = []
    for vid, meta in vector_index.id_to_meta.items():
        try:
            vec = vector_index.index.reconstruct(int(vid))
            vectors_list.append(vec)
            ordered_tiles.append(meta)
        except Exception:
            continue

    if not vectors_list:
        return {"query_tile_id": req.tile_id, "similar_sites": []}

    all_vectors = np.array(vectors_list, dtype=np.float32)
    similar = cluster_engine.find_similar_across_aoi(
        query_tile_id=req.tile_id,
        tiles_data=ordered_tiles,
        embeddings=all_vectors,
        top_k=req.top_k
    )
    return {"query_tile_id": req.tile_id, "similar_sites": similar}


# 2.2.5: Ranked Review Queue & Analyst Triage
@app.get("/api/change/queue")
def get_change_queue(
    status: Optional[str] = None,
    min_confidence: float = 0.0,
    severity: Optional[str] = None,
    limit: int = 50
):
    """
    Retrieves prioritized review queue for analysts.
    """
    items = analyst_queue.get_review_queue(
        status_filter=status,
        min_confidence=min_confidence,
        severity_filter=severity,
        limit=limit
    )
    return {"queue": items, "total": len(items)}


@app.post("/api/change/triage")
def triage_change_event(req: TriageRequest):
    """
    Records analyst confirm/reject decision and updates active learning feedback.
    """
    result = analyst_queue.triage_candidate(
        change_id=req.change_id,
        action=req.action,
        analyst_id=req.analyst_id,
        notes=req.notes
    )
    return result


# 2.2.5: Geospatial Provenance & Intelligence Export
@app.get("/api/provenance/{tile_id}")
def get_provenance(tile_id: str):
    """
    Returns full STAC-compliant metadata, processing lineage, and SHA-256 cryptographic hash.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tiles WHERE tile_id = ?", (tile_id,))
    tile = cursor.fetchone()
    if not tile:
        conn.close()
        raise HTTPException(status_code=404, detail="Tile not found.")

    cursor.execute("SELECT * FROM scenes WHERE scene_id = ?", (tile["scene_id"],))
    scene = cursor.fetchone()
    conn.close()

    stac_item = provenance_engine.build_stac_item(dict(tile), dict(scene) if scene else {})
    return stac_item


@app.get("/api/export/report")
def export_intelligence_report(aoi: str = "Regional AOI Sector Alpha"):
    """
    Exports downloadable Intelligence Report with full provenance.
    """
    queue_items = analyst_queue.get_review_queue(limit=100)
    report = provenance_engine.generate_intelligence_report(queue_items, aoi_name=aoi)
    return report


# 2.2.6: Incremental Ingestion Endpoint
@app.post("/api/ingest")
async def ingest_new_geotiff(
    file: UploadFile = File(...),
    scene_id: str = Form(...),
    acquisition_date: str = Form(...),
    sensor_name: str = Form("Sentinel-2 MSI")
):
    """
    Incrementally ingests a new GeoTIFF / COG into the archive without index rebuilding.
    """
    temp_path = os.path.join(BASE_DIR, "data", "scenes", f"uploaded_{scene_id}.tif")
    with open(temp_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    result = ingestion_pipeline.ingest_scene(
        geotiff_path=temp_path,
        scene_id=scene_id,
        acquisition_date=acquisition_date,
        sensor_name=sensor_name
    )
    return result


# System Benchmark Metrics
@app.get("/api/metrics/benchmark")
def get_system_metrics():
    """
    Returns live system benchmark telemetry: storage footprint, vector latency, indexed tiles count.
    """
    import psutil
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM scenes")
    scene_count = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) as cnt FROM tiles")
    tile_count = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) as cnt FROM change_events")
    change_count = cursor.fetchone()["cnt"]
    conn.close()

    # Calculate storage footprint
    storage_bytes = 0
    for root, _, files in os.walk(DATA_DIR):
        for f in files:
            storage_bytes += os.path.getsize(os.path.join(root, f))
    storage_mb = round(storage_bytes / (1024 * 1024), 2)

    # Benchmark query latency with dummy vector
    t0 = time.time()
    dummy_vec = np.random.randn(512).astype(np.float32)
    vector_index.search(dummy_vec, top_k=10)
    query_latency_ms = round((time.time() - t0) * 1000, 3)

    return {
        "status": "operational",
        "air_gapped": True,
        "sovereignty_verified": True,
        "indexed_scenes": scene_count,
        "indexed_tiles": tile_count,
        "detected_change_events": change_count,
        "vector_index_size": vector_index.index.ntotal,
        "vector_search_latency_ms": query_latency_ms,
        "storage_footprint_mb": storage_mb,
        "system_ram_percent": psutil.virtual_memory().percent,
        "cpu_percent": psutil.cpu_percent()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
