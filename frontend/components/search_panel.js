/**
 * GEO-SENTINEL Search Panel Component
 * Natural language semantic query studio, image-to-image exemplar search, and hybrid ranking.
 */

class SearchPanel {
    constructor(mapView) {
        this.mapView = mapView;
        this.activeExemplarBase64 = null;
        this.init();
    }

    init() {
        this.bindEvents();
        // Trigger initial search
        setTimeout(() => this.executeSemanticSearch(), 300);
    }

    bindEvents() {
        const queryInput = document.getElementById('semantic-query-input');
        const btnSearch = document.getElementById('btn-execute-search');
        const btnRunMain = document.getElementById('btn-run-search-main');
        const presetSelect = document.getElementById('query-presets');
        const qualitySlider = document.getElementById('min-quality-slider');
        const qualityDisplay = document.getElementById('quality-val-display');
        const dropzone = document.getElementById('visual-search-dropzone');
        const fileInput = document.getElementById('visual-file-input');
        const btnClearExemplar = document.getElementById('btn-clear-exemplar');

        if (queryInput) {
            queryInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.executeSemanticSearch();
            });
        }

        if (btnSearch) {
            btnSearch.addEventListener('click', () => this.executeSemanticSearch());
        }

        if (btnRunMain) {
            btnRunMain.addEventListener('click', () => this.executeSemanticSearch());
        }

        if (presetSelect) {
            presetSelect.addEventListener('change', (e) => {
                if (e.target.value) {
                    queryInput.value = e.target.value;
                    this.executeSemanticSearch();
                }
            });
        }

        if (qualitySlider && qualityDisplay) {
            qualitySlider.addEventListener('input', (e) => {
                qualityDisplay.textContent = `${e.target.value}%`;
            });
        }

        // Image Dropzone
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
                    this.handleExemplarFile(e.dataTransfer.files[0]);
                }
            });

            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleExemplarFile(e.target.files[0]);
                }
            });
        }

        if (btnClearExemplar) {
            btnClearExemplar.addEventListener('click', () => {
                this.activeExemplarBase64 = null;
                document.getElementById('exemplar-preview-container').classList.add('preview-hidden');
                document.getElementById('visual-search-dropzone').style.display = 'block';
            });
        }
    }

    handleExemplarFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            this.activeExemplarBase64 = e.target.result;
            document.getElementById('exemplar-preview-img').src = this.activeExemplarBase64;
            document.getElementById('exemplar-preview-container').classList.remove('preview-hidden');
            document.getElementById('visual-search-dropzone').style.display = 'none';
            this.executeVisualSearch();
        };
        reader.readAsDataURL(file);
    }

    async executeSemanticSearch() {
        const query = document.getElementById('semantic-query-input').value.trim();
        const dateStart = document.getElementById('date-start').value;
        const dateEnd = document.getElementById('date-end').value;
        const sensorFilter = document.getElementById('sensor-filter').value;
        const minQuality = parseFloat(document.getElementById('min-quality-slider').value) / 100.0;

        if (!query && !this.activeExemplarBase64) return;

        if (this.activeExemplarBase64) {
            return this.executeVisualSearch();
        }

        try {
            const resultsContainer = document.getElementById('search-results-list');
            resultsContainer.innerHTML = '<div class="telemetry-bar"><i class="fa-solid fa-spinner fa-spin"></i> Executing FAISS semantic retrieval...</div>';

            const payload = {
                query: query,
                top_k: 20,
                date_start: dateStart || null,
                date_end: dateEnd || null,
                sensor_filter: sensorFilter || null,
                min_quality: minQuality,
                weights: { semantic: 0.70, quality: 0.15, spatial: 0.15 }
            };

            const res = await fetch('/api/search/semantic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            this.renderResults(data);
        } catch (err) {
            console.error('[SearchPanel] Search error:', err);
        }
    }

    async executeVisualSearch() {
        try {
            const resultsContainer = document.getElementById('search-results-list');
            resultsContainer.innerHTML = '<div class="telemetry-bar"><i class="fa-solid fa-spinner fa-spin"></i> Executing image-to-image similarity search...</div>';

            const payload = {
                image_base64: this.activeExemplarBase64,
                top_k: 20
            };

            const res = await fetch('/api/search/visual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            this.renderResults(data);
        } catch (err) {
            console.error('[SearchPanel] Visual search error:', err);
        }
    }

    renderResults(data) {
        const resultsContainer = document.getElementById('search-results-list');
        const badgeCount = document.getElementById('results-count-badge');
        const latencyDisplay = document.getElementById('search-latency-display');

        if (badgeCount) badgeCount.textContent = `${data.results_count} matches`;
        if (latencyDisplay) latencyDisplay.textContent = `${data.latency_ms} ms`;

        if (!data.results || data.results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation empty-icon"></i>
                    <p>No matching satellite tiles found with the given filters.</p>
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = '';

        data.results.forEach((item, idx) => {
            const card = document.createElement('div');
            card.className = 'result-card';
            card.innerHTML = `
                <img src="${item.rgb_preview_path}" alt="Tile Preview" class="result-thumb" />
                <div class="result-info">
                    <h4>#${idx + 1} ${item.tile_id}</h4>
                    <div class="result-meta">
                        <span><i class="fa-solid fa-calendar"></i> ${item.acquisition_date}</span>
                        <span><i class="fa-solid fa-satellite"></i> ${item.sensor_name}</span>
                        <span><i class="fa-solid fa-location-dot"></i> ${item.center_lat.toFixed(3)}, ${item.center_lon.toFixed(3)}</span>
                    </div>
                    <div class="score-badge">
                        <i class="fa-solid fa-chart-simple"></i> Match: ${(item.composite_score * 100).toFixed(1)}%
                    </div>
                </div>
            `;

            card.addEventListener('click', () => {
                this.mapView.highlightTile(item);
            });

            resultsContainer.appendChild(card);
        });

        // Highlight top match on map
        if (data.results.length > 0) {
            this.mapView.highlightTile(data.results[0]);
        }
    }
}

window.SearchPanel = SearchPanel;
