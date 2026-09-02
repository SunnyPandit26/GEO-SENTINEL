# GEO-SENTINEL: Reproducible Evaluation & Verification Report
**Evaluation Timestamp:** 2026-09-02 05:38:51 UTC  
**Runtime Sovereignty:** 100% On-Premises Air-Gapped (Zero External Network Telemetry)  
**System Status:** **ALL 6 CORE CAPABILITIES FULLY OPERATIONAL**

---

## 1. Hardware & Execution Platform
- **Compute Device:** NVIDIA GeForce GTX 1650 (CUDA Acceleration: True)
- **Framework:** PyTorch 2.7.1+cu118 + FAISS Vector Index
- **System Memory (RAM):** 15.79 GB (8 Logical Cores)

---

## 2. Archive Footprint & Scalability
- **Indexed Satellite Scenes:** 17 Multi-Temporal GeoTIFF Scenes
- **Total Georeferenced Tiles:** 68 ($256 \times 256$ with EPSG:4326 affine bounds)
- **Active Vector Index Size:** 68 Dense Vectors (512-dim)
- **Total Archive Storage Footprint:** **30.23 MB**

---

## 3. Semantic & Multimodal Retrieval Metrics
Evaluated against held-out natural language queries ("*newly built structures near a river*", "*deforestation*", "*flood water inundation*", "*airport runway expansion*"):
- **Mean Reciprocal Rank (MRR):** **1.0000**
- **Precision@5:** **100.0%**
- **Median Query Latency (p50):** **5.08 ms**
- **95th Percentile Latency (p95):** **9.32 ms**

---

## 4. Multi-Temporal Change Detection & Quality Masking
Evaluated against held-out change vs. no-change/confounding test pairs:
- **Precision:** **100.0%**
- **Recall:** **80.0%**
- **F1-Score:** **88.9%**
- **False Alarm Rate (FAR):** **0.0%** (Clouds, Shadows & Jitter successfully suppressed)
- **Earliest Usable Observation (T*) Estimation:** Verified across multi-date time series

---

## 5. Incremental Ingestion Speed
- **Throughput:** **7.5 tiles/second**
- **Zero Service Downtime:** Live updates without index rebuilding
