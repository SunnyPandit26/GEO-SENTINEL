/**
 * GEO-SENTINEL System Telemetry & Incremental Ingestion Component
 * Live hardware and vector index metrics, incremental GeoTIFF upload,
 * and STAC item cryptographic provenance viewer.
 */

class SystemMonitor {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadMetrics();
        this.loadSampleSTAC();
    }

    bindEvents() {
        const form = document.getElementById('incremental-ingest-form');
        const dropzone = document.getElementById('ingest-dropzone');
        const fileInput = document.getElementById('ingest-file-input');
        const filenameDisplay = document.getElementById('ingest-filename-display');

        if (dropzone && fileInput) {
            dropzone.addEventListener('click', () => fileInput.click());
            dropzone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropzone.classList.add('dragover');
            });
            dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
            dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropzone.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    fileInput.files = e.dataTransfer.files;
                    if (filenameDisplay) filenameDisplay.textContent = `Selected: ${e.dataTransfer.files[0].name}`;
                }
            });

            fileInput.addEventListener('change', () => {
                if (fileInput.files.length > 0 && filenameDisplay) {
                    filenameDisplay.textContent = `Selected: ${fileInput.files[0].name}`;
                }
            });
        }

        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleIncrementalIngest();
            });
        }
    }

    async loadMetrics() {
        try {
            const res = await fetch('/api/metrics/benchmark');
            const data = await res.json();

            const scenesEl = document.getElementById('metric-scenes-count');
            const tilesEl = document.getElementById('metric-tiles-count');
            const latencyEl = document.getElementById('metric-vector-latency');
            const storageEl = document.getElementById('metric-storage-footprint');

            if (scenesEl) scenesEl.textContent = data.indexed_scenes;
            if (tilesEl) tilesEl.textContent = data.indexed_tiles;
            if (latencyEl) latencyEl.textContent = `${data.vector_search_latency_ms} ms`;
            if (storageEl) storageEl.textContent = `${data.storage_footprint_mb} MB`;
        } catch (err) {
            console.error('[SystemMonitor] Error loading metrics:', err);
        }
    }

    async loadSampleSTAC() {
        try {
            const res = await fetch('/api/provenance/scene_urban_river_1_tile_r0_c0');
            const data = await res.json();

            const stacPreview = document.getElementById('stac-json-preview');
            if (stacPreview) {
                stacPreview.textContent = JSON.stringify(data, null, 2);
            }
        } catch (err) {
            console.error('[SystemMonitor] Error loading STAC sample:', err);
        }
    }

    async handleIncrementalIngest() {
        const fileInput = document.getElementById('ingest-file-input');
        const sceneId = document.getElementById('ingest-scene-id').value.trim();
        const acqDate = document.getElementById('ingest-acq-date').value;
        const sensor = document.getElementById('ingest-sensor').value;

        if (!fileInput.files.length || !sceneId || !acqDate) {
            alert('Please complete all ingestion fields and select a valid GeoTIFF file.');
            return;
        }

        const progressBox = document.getElementById('ingest-progress-container');
        const progressFill = document.getElementById('ingest-progress-fill');
        const statusText = document.getElementById('ingest-status-text');

        if (progressBox) progressBox.style.display = 'block';
        if (progressFill) progressFill.style.width = '40%';
        if (statusText) statusText.textContent = 'Parsing GeoTIFF coordinates and extracting 512-dim embeddings...';

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('scene_id', sceneId);
        formData.append('acquisition_date', acqDate);
        formData.append('sensor_name', sensor);

        try {
            const res = await fetch('/api/ingest', {
                method: 'POST',
                body: formData
            });

            const result = await res.json();

            if (progressFill) progressFill.style.width = '100%';
            if (statusText) statusText.textContent = `Ingestion Complete! Ingested ${result.tiles_ingested} tiles in ${result.elapsed_seconds}s (${result.throughput_tiles_per_sec} tiles/sec). Total indexed: ${result.total_indexed_tiles}`;

            this.loadMetrics();
        } catch (err) {
            console.error('[SystemMonitor] Ingestion error:', err);
            if (statusText) statusText.textContent = 'Error during incremental ingestion.';
        }
    }
}

window.SystemMonitor = SystemMonitor;
