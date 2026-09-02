/**
 * GEO-SENTINEL Split-Screen Swipe Inspector & Multi-Temporal Onset Tracker
 * Features real-time curtain swipe comparison, false-color NIR composite toggling,
 * difference heatmap overlay, time-series playback, and statistical onset trajectory charting.
 */

class SwipeInspector {
    constructor() {
        this.currentScenario = "scene_urban_river";
        this.scenarioDates = [];
        this.t1SceneId = "";
        this.t2SceneId = "";
        this.activeTileId = "scene_urban_river_1_tile_r1_c1";
        this.currentVisualMode = "swipe";
        this.isPlaying = false;
        this.playbackTimer = null;
        this.chartInstance = null;
        this.init();
    }

    init() {
        this.setupSwipeDivider();
        this.bindEvents();
        this.loadScenarioOptions();
    }

    setupSwipeDivider() {
        const container = document.getElementById('swipe-container');
        const divider = document.getElementById('swipe-divider');
        const clippedLayer = document.getElementById('layer-after-clipped');

        if (!container || !divider || !clippedLayer) return;

        let isDragging = false;

        const updateSwipePosition = (clientX) => {
            const rect = container.getBoundingClientRect();
            let x = clientX - rect.left;
            x = Math.max(0, Math.min(x, rect.width));
            const percentage = (x / rect.width) * 100;

            divider.style.left = `${percentage}%`;
            clippedLayer.style.clipPath = `inset(0 0 0 ${percentage}%)`;
        };

        divider.addEventListener('mousedown', (e) => {
            isDragging = true;
            e.preventDefault();
        });

        window.addEventListener('mouseup', () => {
            isDragging = false;
        });

        window.addEventListener('mousemove', (e) => {
            if (isDragging) {
                updateSwipePosition(e.clientX);
            }
        });

        // Touch support
        divider.addEventListener('touchstart', () => { isDragging = true; });
        window.addEventListener('touchend', () => { isDragging = false; });
        window.addEventListener('touchmove', (e) => {
            if (isDragging && e.touches.length > 0) {
                updateSwipePosition(e.touches[0].clientX);
            }
        });
    }

    bindEvents() {
        const scenarioSelect = document.getElementById('scenario-selector');
        const selectT1 = document.getElementById('select-t1-date');
        const selectT2 = document.getElementById('select-t2-date');
        const btnRunChange = document.getElementById('btn-execute-change-analysis');
        const modeButtons = document.querySelectorAll('#visual-mode-toggle .btn-toggle');
        const scrubber = document.getElementById('timeline-scrubber');
        const btnPlay = document.getElementById('btn-play-timeline');
        const btnReset = document.getElementById('btn-reset-timeline');

        // Triage buttons
        const btnConfirm = document.getElementById('btn-triage-confirm');
        const btnReject = document.getElementById('btn-triage-reject');
        const btnFlag = document.getElementById('btn-triage-flag');

        if (scenarioSelect) {
            scenarioSelect.addEventListener('change', (e) => {
                this.currentScenario = e.target.value;
                this.loadScenarioOptions();
            });
        }

        if (selectT1) {
            selectT1.addEventListener('change', () => this.runAnalysis());
        }

        if (selectT2) {
            selectT2.addEventListener('change', () => this.runAnalysis());
        }

        if (btnRunChange) {
            btnRunChange.addEventListener('click', () => this.runAnalysis());
        }

        modeButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                modeButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.setVisualMode(btn.dataset.mode);
            });
        });

        if (scrubber) {
            scrubber.addEventListener('input', (e) => {
                const step = parseInt(e.target.value);
                this.setTimelineStep(step);
            });
        }

        if (btnPlay) {
            btnPlay.addEventListener('click', () => this.togglePlayback());
        }

        if (btnReset) {
            btnReset.addEventListener('click', () => {
                if (scrubber) scrubber.value = 0;
                this.setTimelineStep(0);
            });
        }

        if (btnConfirm) btnConfirm.addEventListener('click', () => this.handleTriage('confirm'));
        if (btnReject) btnReject.addEventListener('click', () => this.handleTriage('reject'));
        if (btnFlag) btnFlag.addEventListener('click', () => this.handleTriage('flag'));
    }

    async loadScenarioOptions() {
        try {
            const res = await fetch('/api/scenes');
            const data = await res.json();
            
            // Filter scenes matching current scenario prefix
            const matchedScenes = data.scenes.filter(s => s.scene_id.startsWith(this.currentScenario));
            this.scenarioDates = matchedScenes;

            const selectT1 = document.getElementById('select-t1-date');
            const selectT2 = document.getElementById('select-t2-date');

            if (!selectT1 || !selectT2) return;

            selectT1.innerHTML = '';
            selectT2.innerHTML = '';

            matchedScenes.forEach((s, idx) => {
                const opt1 = new Option(`${s.acquisition_date} (T${idx+1})`, s.scene_id);
                const opt2 = new Option(`${s.acquisition_date} (T${idx+1})`, s.scene_id);
                selectT1.add(opt1);
                selectT2.add(opt2);
            });

            // Set default baseline T1 and target T4/T3
            if (matchedScenes.length >= 2) {
                selectT1.selectedIndex = 0;
                selectT2.selectedIndex = matchedScenes.length - 1;
            }

            this.setupTimelineMarkers(matchedScenes);
            this.runAnalysis();
        } catch (err) {
            console.error('[SwipeInspector] Error loading scenario:', err);
        }
    }

    setupTimelineMarkers(scenes) {
        const container = document.getElementById('timeline-markers-container');
        const scrubber = document.getElementById('timeline-scrubber');
        if (!container || !scrubber) return;

        scrubber.max = Math.max(0, scenes.length - 1);
        container.innerHTML = '';

        scenes.forEach((s, idx) => {
            const span = document.createElement('span');
            span.textContent = `T${idx+1}: ${s.acquisition_date}`;
            if (idx === 1) span.className = 'onset-marker';
            container.appendChild(span);
        });
    }

    async runAnalysis() {
        const selectT1 = document.getElementById('select-t1-date');
        const selectT2 = document.getElementById('select-t2-date');
        if (!selectT1 || !selectT2 || !selectT1.value || !selectT2.value) return;

        this.t1SceneId = selectT1.value;
        this.t2SceneId = selectT2.value;

        // Choose center tile (row 1, col 1) for selected scenario
        this.activeTileId = `${this.t1SceneId}_tile_r1_c1`;

        try {
            const payload = {
                tile_id: this.activeTileId,
                scene_t1_id: this.t1SceneId,
                scene_t2_id: this.t2SceneId
            };

            const res = await fetch('/api/change/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            this.renderChangeResults(data);
            this.loadTimelineOnsetGraph();
        } catch (err) {
            console.error('[SwipeInspector] Change analysis error:', err);
        }
    }

    renderChangeResults(data) {
        const imgBefore = document.getElementById('img-before');
        const imgAfter = document.getElementById('img-after');
        const imgHeatmap = document.getElementById('img-heatmap-overlay');
        const lblT1 = document.getElementById('lbl-t1-date');
        const lblT2 = document.getElementById('lbl-t2-date');

        if (imgBefore) imgBefore.src = data.tile_t1_preview;
        if (imgAfter) imgAfter.src = data.tile_t2_preview;
        if (imgHeatmap) imgHeatmap.src = data.diff_heatmap_path;

        if (lblT1) lblT1.textContent = `${data.date_t1} (${data.scene_t1_id})`;
        if (lblT2) lblT2.textContent = `${data.date_t2} (${data.scene_t2_id})`;

        // Update diagnosis cards
        const diagType = document.getElementById('diag-change-type');
        const diagSev = document.getElementById('diag-severity');
        const diagConf = document.getElementById('diag-confidence');
        const diagEarliest = document.getElementById('diag-earliest-date');
        const diagQuality = document.getElementById('diag-quality-factor');

        if (diagType) diagType.textContent = `${data.change_type} (${data.subtype})`;
        if (diagSev) {
            diagSev.textContent = data.severity;
            diagSev.className = `severity-badge badge-${data.severity.toLowerCase()}`;
        }
        if (diagConf) diagConf.textContent = `${(data.confidence_score * 100).toFixed(1)}%`;
        if (diagQuality) diagQuality.textContent = `Q1: ${(data.quality_score_t1*100).toFixed(0)}% | Q2: ${(data.quality_score_t2*100).toFixed(0)}%`;
    }

    async loadTimelineOnsetGraph() {
        try {
            const res = await fetch(`/api/change/timeline?scenario_prefix=${this.currentScenario}&row_idx=1&col_idx=1`);
            const data = await res.json();

            const diagEarliest = document.getElementById('diag-earliest-date');
            if (diagEarliest) diagEarliest.textContent = data.earliest_observation_date;

            this.renderOnsetChart(data.timeline, data.earliest_observation_date);
        } catch (err) {
            console.error('[SwipeInspector] Timeline graph error:', err);
        }
    }

    renderOnsetChart(timeline, earliestDate) {
        const ctx = document.getElementById('onset-chart');
        if (!ctx) return;

        if (this.chartInstance) {
            this.chartInstance.destroy();
        }

        const labels = timeline.map(t => t.date);
        const dataMetrics = timeline.map(t => t.change_metric);
        const pointColors = timeline.map(t => t.date === earliestDate ? '#f59e0b' : (t.is_usable ? '#38bdf8' : '#ef4444'));
        const pointRadii = timeline.map(t => t.date === earliestDate ? 8 : (t.is_usable ? 5 : 4));

        this.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Change Anomaly Signal Magnitude (3-Sigma)',
                    data: dataMetrics,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: pointColors,
                    pointRadius: pointRadii,
                    pointBorderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 10 } },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    y: {
                        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 10 } },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    }
                }
            }
        });
    }

    setVisualMode(mode) {
        this.currentVisualMode = mode;
        const imgHeatmap = document.getElementById('layer-overlay-heatmap');
        const clippedLayer = document.getElementById('layer-after-clipped');
        const divider = document.getElementById('swipe-divider');

        if (mode === "diff") {
            if (imgHeatmap) imgHeatmap.style.display = 'block';
            if (clippedLayer) clippedLayer.style.clipPath = 'none';
            if (divider) divider.style.display = 'none';
        } else {
            if (imgHeatmap) imgHeatmap.style.display = 'none';
            if (divider) divider.style.display = 'block';
            if (clippedLayer) clippedLayer.style.clipPath = 'inset(0 0 0 50%)';
        }
    }

    setTimelineStep(stepIdx) {
        if (!this.scenarioDates || stepIdx >= this.scenarioDates.length) return;
        const targetScene = this.scenarioDates[stepIdx];
        
        const selectT2 = document.getElementById('select-t2-date');
        const stepLabel = document.getElementById('timeline-step-label');

        if (selectT2) selectT2.value = targetScene.scene_id;
        if (stepLabel) stepLabel.textContent = `Obs ${stepIdx + 1} of ${this.scenarioDates.length} (${targetScene.acquisition_date})`;

        this.runAnalysis();
    }

    togglePlayback() {
        const btnPlay = document.getElementById('btn-play-timeline');
        const scrubber = document.getElementById('timeline-scrubber');

        if (this.isPlaying) {
            clearInterval(this.playbackTimer);
            this.isPlaying = false;
            if (btnPlay) btnPlay.innerHTML = '<i class="fa-solid fa-play"></i>';
        } else {
            this.isPlaying = true;
            if (btnPlay) btnPlay.innerHTML = '<i class="fa-solid fa-pause"></i>';

            let currentStep = parseInt(scrubber.value);
            this.playbackTimer = setInterval(() => {
                currentStep = (currentStep + 1) % this.scenarioDates.length;
                scrubber.value = currentStep;
                this.setTimelineStep(currentStep);
            }, 1200);
        }
    }

    async handleTriage(action) {
        const notes = document.getElementById('analyst-notes-input').value;
        const changeId = `chg_${this.t1SceneId}_${this.t2SceneId}_1_1`;

        try {
            const res = await fetch('/api/change/triage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    change_id: changeId,
                    action: action,
                    notes: notes,
                    analyst_id: "Analyst_Alpha"
                })
            });
            const data = await res.json();
            alert(`Triage action '${action.toUpperCase()}' recorded into audit trail with ID ${data.review_id || 'OK'}`);
            // Refresh queue count
            if (window.app && window.app.reviewQueue) {
                window.app.reviewQueue.loadQueue();
            }
        } catch (err) {
            console.error('[SwipeInspector] Triage error:', err);
        }
    }
}

window.SwipeInspector = SwipeInspector;
