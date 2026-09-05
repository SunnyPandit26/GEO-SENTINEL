/**
 * GEO-SENTINEL Master Application Controller
 * Coordinates tab navigation, cross-component event dispatching, and intelligence reporting.
 */

class GeoSentinelApp {
    constructor() {
        this.mapView = null;
        this.searchPanel = null;
        this.swipeInspector = null;
        this.clusterExplorer = null;
        this.reviewQueue = null;
        this.systemMonitor = null;

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        this.setupNavigation();
        this.setupReportModal();

        // Initialize child components
        this.mapView = new TacticalMapView();
        this.searchPanel = new SearchPanel(this.mapView);
        this.swipeInspector = new SwipeInspector();
        this.clusterExplorer = new ClusterExplorer();
        this.reviewQueue = new ReviewQueue();
        this.systemMonitor = new SystemMonitor();

        console.log('[GeoSentinelApp] Fully initialized sovereign intelligence workstation.');
    }

    setupNavigation() {
        const tabs = document.querySelectorAll('.tactical-nav .nav-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
            });
        });
    }

    switchTab(tabId) {
        const tabs = document.querySelectorAll('.tactical-nav .nav-tab');
        const views = document.querySelectorAll('.main-content .view-panel');

        tabs.forEach(tab => {
            if (tab.dataset.tab === tabId) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        views.forEach(view => {
            if (view.id === tabId) {
                view.classList.add('active');
            } else {
                view.classList.remove('active');
            }
        });

        // Trigger map / canvas resize when switching views
        if (tabId === 'search-view' && this.mapView && this.mapView.map) {
            setTimeout(() => this.mapView.map.invalidateSize(), 150);
        } else if (tabId === 'discovery-view' && this.clusterExplorer) {
            setTimeout(() => this.clusterExplorer.drawScatter(), 150);
        }
    }

    inspectTile(tileId) {
        // Switch to swipe view and load corresponding scenario
        this.switchTab('swipe-view');

        // Extract scenario prefix from tile ID
        const parts = tileId.split('_tile_');
        const sceneId = parts[0];
        
        let scenarioPrefix = "scene_urban_river";
        if (sceneId.includes("forest")) scenarioPrefix = "scene_forest_clearance";
        else if (sceneId.includes("water")) scenarioPrefix = "scene_water_inundation";
        else if (sceneId.includes("airfield")) scenarioPrefix = "scene_airfield_transport";

        const scenarioSelect = document.getElementById('scenario-selector');
        if (scenarioSelect) {
            scenarioSelect.value = scenarioPrefix;
            if (this.swipeInspector) {
                this.swipeInspector.currentScenario = scenarioPrefix;
                this.swipeInspector.loadScenarioOptions();
            }
        }
    }

    navigateToMapAndHighlight(tile) {
        if (!tile) return;

        // 1. Switch to Semantic Retrieval (search-view) tab
        this.switchTab('search-view');

        // 2. Refresh map layout and highlight tile
        setTimeout(() => {
            if (this.mapView && this.mapView.map) {
                this.mapView.map.invalidateSize();
                this.mapView.highlightTile(tile);
            }

            // 3. Populate inspected tile card in right results panel
            const resultsContainer = document.getElementById('search-results-list');
            const badgeCount = document.getElementById('results-count-badge');
            if (badgeCount) badgeCount.textContent = `1 inspected site`;

            if (resultsContainer) {
                let categoryTag = "Urban Construction & Riverfront";
                let tagColor = "#2563eb";
                if (tile.tile_id && tile.tile_id.includes("forest")) { categoryTag = "🌲 Forest Canopy / Woodland"; tagColor = "#16a34a"; }
                else if (tile.tile_id && tile.tile_id.includes("water")) { categoryTag = "🌊 Water Bodies & Inundation"; tagColor = "#0284c7"; }
                else if (tile.tile_id && tile.tile_id.includes("airfield")) { categoryTag = "✈️ Airfield Runway & Logistics"; tagColor = "#7c3aed"; }

                const imgPath = tile.preview_path || tile.rgb_preview_path;

                resultsContainer.innerHTML = `
                    <div class="result-card-item active" style="border: 2px solid #2563eb; background: #eff6ff;">
                        ${imgPath ? `<img src="${imgPath}" alt="Tile Preview" class="result-thumb" />` : ''}
                        <div class="result-info">
                            <div class="result-title-row">
                                <strong>⭐ ${tile.tile_id}</strong>
                            </div>
                            <div style="font-size:11px; font-weight:700; color:${tagColor}; margin:2px 0;">
                                ${categoryTag}
                            </div>
                            <div class="result-meta-list">
                                <span><i class="fa-solid fa-calendar"></i> ${tile.acquisition_date || '2025-02-10'} | ${tile.sensor_name || 'Sentinel-2 MSI'}</span>
                                <span><i class="fa-solid fa-location-dot"></i> ${(tile.center_lat || 28.6139).toFixed(4)}, ${(tile.center_lon || 77.2090).toFixed(4)}</span>
                            </div>
                            <div style="display:flex; align-items:center; justify-content:space-between; margin-top:8px;">
                                <span class="match-score-badge" style="background:#dbeafe; color:#1d4ed8;">
                                    <i class="fa-solid fa-crosshairs"></i> AOI Highlight Active
                                </span>
                                <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); window.app.inspectTile('${tile.tile_id}')" style="font-size:10px; padding:3px 8px;">
                                    <i class="fa-solid fa-code-compare"></i> Inspect in Swipe
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            }
        }, 120);
    }

    setupReportModal() {
        const btnExport = document.getElementById('btn-export-report');
        const modal = document.getElementById('export-report-modal');
        const btnClose = document.getElementById('btn-close-modal');
        const reportContent = document.getElementById('modal-report-content');
        const btnDownload = document.getElementById('btn-download-pdf-report');

        if (btnExport && modal) {
            btnExport.addEventListener('click', async () => {
                modal.style.display = 'flex';
                reportContent.innerHTML = '<div style="color:#38bdf8;"><i class="fa-solid fa-spinner fa-spin"></i> Generating cryptographic intelligence report...</div>';

                try {
                    const res = await fetch('/api/export/report?aoi=Regional%20AOI%20Sector%20Alpha');
                    const data = await res.json();
                    
                    // Simple Markdown-to-HTML formatter
                    let html = data.markdown_content
                        .replace(/^# (.*$)/gim, '<h1 style="color:#38bdf8; font-size:18px; margin-bottom:8px;">$1</h1>')
                        .replace(/^## (.*$)/gim, '<h2 style="color:#f8fafc; font-size:15px; margin-top:16px; margin-bottom:8px;">$1</h2>')
                        .replace(/^### (.*$)/gim, '<h3 style="color:#94a3b8; font-size:13px; margin-top:12px; margin-bottom:6px;">$1</h3>')
                        .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
                        .replace(/`(.*?)`/gim, '<code style="background:#141c33; color:#38bdf8; padding:2px 6px; border-radius:3px;">$1</code>')
                        .replace(/\n/gim, '<br/>');

                    reportContent.innerHTML = html;

                    if (btnDownload) {
                        btnDownload.onclick = () => {
                            const blob = new Blob([data.markdown_content], { type: 'text/markdown' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `GEO_SENTINEL_INTELLIGENCE_REPORT_${Date.now()}.md`;
                            a.click();
                        };
                    }
                } catch (err) {
                    console.error('Error generating report:', err);
                }
            });
        }

        if (btnClose && modal) {
            btnClose.addEventListener('click', () => { modal.style.display = 'none'; });
        }
    }
}

window.app = new GeoSentinelApp();
