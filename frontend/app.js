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
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
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
        });
    }

    setupNavigation() {
        const tabs = document.querySelectorAll('.tactical-nav .nav-tab');
        const views = document.querySelectorAll('.main-content .view-panel');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetViewId = tab.dataset.tab;

                tabs.forEach(t => t.classList.remove('active'));
                views.forEach(v => v.classList.remove('active'));

                tab.classList.add('active');
                const targetView = document.getElementById(targetViewId);
                if (targetView) targetView.classList.add('active');

                // Trigger map / canvas resize when switching views
                if (targetViewId === 'search-view' && this.mapView && this.mapView.map) {
                    setTimeout(() => this.mapView.map.invalidateSize(), 200);
                } else if (targetViewId === 'discovery-view' && this.clusterExplorer) {
                    setTimeout(() => this.clusterExplorer.drawScatter(), 200);
                }
            });
        });
    }

    inspectTile(tileId) {
        // Switch to swipe view and load corresponding scenario
        const swipeTab = document.querySelector('[data-tab="swipe-view"]');
        if (swipeTab) swipeTab.click();

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
            this.swipeInspector.currentScenario = scenarioPrefix;
            this.swipeInspector.loadScenarioOptions();
        }
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
