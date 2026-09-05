/**
 * GEO-SENTINEL Cluster & Site Discovery Explorer Component
 * Visualizes 2D latent semantic embedding projections, visual tile galleries,
 * cluster exemplars, and executes one-click discovery across the regional AOI.
 */

window.allClusterTiles = {};

window.locateClusterTile = function(tileId) {
    console.log('[locateClusterTile] locating tile:', tileId);
    let tile = window.allClusterTiles ? window.allClusterTiles[tileId] : null;
    if (!tile && window.app && window.app.clusterExplorer) {
        tile = window.app.clusterExplorer.points.find(x => x.tile_id === tileId);
    }
    if (!tile) {
        tile = { tile_id: tileId, center_lat: 28.6139, center_lon: 77.2090 };
    }
    if (window.app && window.app.navigateToMapAndHighlight) {
        window.app.navigateToMapAndHighlight(tile);
    }
};

class ClusterExplorer {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.clusters = [];
        this.points = [];
        this.tilesById = {};
        this.selectedClusterId = null;
        this.selectedTileId = null;
        this.hoveredPoint = null;
        this.viewMode = 'grid'; // 'grid' | 'scatter'
        this.init();
    }

    init() {
        this.canvas = document.getElementById('cluster-scatter-canvas');
        if (this.canvas) {
            this.ctx = this.canvas.getContext('2d');
        }

        this.setupViewToggles();
        this.setupCanvas();
        this.bindEvents();
        this.loadClusterData();
    }

    setupViewToggles() {
        const btnGrid = document.getElementById('btn-view-mode-grid');
        const btnScatter = document.getElementById('btn-view-mode-scatter');

        if (btnGrid) {
            btnGrid.addEventListener('click', () => this.setViewMode('grid'));
        }
        if (btnScatter) {
            btnScatter.addEventListener('click', () => this.setViewMode('scatter'));
        }
    }

    setViewMode(mode) {
        this.viewMode = mode;
        const btnGrid = document.getElementById('btn-view-mode-grid');
        const btnScatter = document.getElementById('btn-view-mode-scatter');
        const gallery = document.getElementById('cluster-tiles-gallery');
        const scatterWrapper = document.getElementById('cluster-scatter-wrapper');

        if (mode === 'grid') {
            if (btnGrid) { btnGrid.className = 'btn btn-sm btn-primary'; }
            if (btnScatter) { btnScatter.className = 'btn btn-sm btn-outline'; }
            if (gallery) { gallery.style.display = 'grid'; }
            if (scatterWrapper) { scatterWrapper.style.display = 'none'; }
        } else {
            if (btnGrid) { btnGrid.className = 'btn btn-sm btn-outline'; }
            if (btnScatter) { btnScatter.className = 'btn btn-sm btn-primary'; }
            if (gallery) { gallery.style.display = 'none'; }
            if (scatterWrapper) { 
                scatterWrapper.style.display = 'block'; 
                setTimeout(() => {
                    this.setupCanvas();
                    this.drawScatter();
                }, 50);
            }
        }
    }

    setupCanvas() {
        if (!this.canvas) return;
        const resize = () => {
            if (this.canvas.parentElement) {
                const rect = this.canvas.parentElement.getBoundingClientRect();
                this.canvas.width = rect.width || 600;
                this.canvas.height = Math.max(450, (rect.height || 500) - 10);
                this.drawScatter();
            }
        };
        window.addEventListener('resize', resize);
        setTimeout(resize, 100);
    }

    bindEvents() {
        if (this.canvas) {
            this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
            this.canvas.addEventListener('click', (e) => this.handleClick(e));
        }
    }

    async loadClusterData() {
        try {
            const res = await fetch('/api/clusters');
            const data = await res.json();
            this.clusters = data.clusters || [];
            this.points = data.points || [];

            this.tilesById = {};
            this.points.forEach(p => {
                this.tilesById[p.tile_id] = p;
                window.allClusterTiles[p.tile_id] = p;
            });

            this.renderLegend();
            this.renderExemplars();
            this.selectCluster(null); // Show all by default
            this.drawScatter();
        } catch (err) {
            console.error('[ClusterExplorer] Error loading clusters:', err);
        }
    }

    renderLegend() {
        const container = document.getElementById('cluster-legend-list');
        if (!container) return;
        container.innerHTML = '';

        // 1. "All Categories" Pill
        const allPill = document.createElement('div');
        allPill.className = `cluster-pill ${this.selectedClusterId === null ? 'active' : ''}`;
        allPill.id = 'pill-cluster-all';
        allPill.style.border = '1px solid #2563eb';
        if (this.selectedClusterId === null) {
            allPill.style.background = '#2563eb';
            allPill.style.color = '#ffffff';
        } else {
            allPill.style.background = '#ffffff';
            allPill.style.color = '#2563eb';
        }
        allPill.innerHTML = `<span><i class="fa-solid fa-layer-group"></i> All Categories (${this.points.length} sites)</span>`;
        allPill.addEventListener('click', () => this.selectCluster(null));
        container.appendChild(allPill);

        // 2. Individual Cluster Pills
        this.clusters.forEach(c => {
            const pill = document.createElement('div');
            const isSelected = this.selectedClusterId === c.cluster_id;
            pill.className = `cluster-pill ${isSelected ? 'active' : ''}`;
            pill.id = `pill-cluster-${c.cluster_id}`;
            pill.style.border = `1px solid ${c.color}`;
            
            if (isSelected) {
                pill.style.background = c.color;
                pill.style.color = '#ffffff';
            } else {
                pill.style.background = `${c.color}15`;
                pill.style.color = c.color;
            }

            pill.innerHTML = `
                <span style="width:7px; height:7px; border-radius:50%; background:${isSelected ? '#fff' : c.color}; display:inline-block;"></span>
                <span>${c.label} (${c.count} sites)</span>
            `;
            pill.addEventListener('click', () => this.selectCluster(c.cluster_id));
            container.appendChild(pill);
        });
    }

    selectCluster(clusterId) {
        this.selectedClusterId = clusterId;

        // Update Pill Visuals
        const allPill = document.getElementById('pill-cluster-all');
        if (allPill) {
            if (clusterId === null) {
                allPill.className = 'cluster-pill active';
                allPill.style.background = '#2563eb';
                allPill.style.color = '#ffffff';
            } else {
                allPill.className = 'cluster-pill';
                allPill.style.background = '#ffffff';
                allPill.style.color = '#2563eb';
            }
        }

        this.clusters.forEach(c => {
            const pill = document.getElementById(`pill-cluster-${c.cluster_id}`);
            if (pill) {
                const isSel = c.cluster_id === clusterId;
                pill.className = `cluster-pill ${isSel ? 'active' : ''}`;
                if (isSel) {
                    pill.style.background = c.color;
                    pill.style.color = '#ffffff';
                } else {
                    pill.style.background = `${c.color}15`;
                    pill.style.color = c.color;
                }
            }
        });

        // Update Header Title & Count Badge
        const titleHeading = document.getElementById('cluster-active-heading');
        const countBadge = document.getElementById('cluster-tile-count-badge');

        if (clusterId === null) {
            if (titleHeading) titleHeading.textContent = 'All Regional Satellite Archive Footprints';
            if (countBadge) countBadge.textContent = `${this.points.length} Indexed Sites`;
        } else {
            const cluster = this.clusters.find(c => c.cluster_id === clusterId);
            if (cluster) {
                if (titleHeading) titleHeading.textContent = `${cluster.label}`;
                if (countBadge) countBadge.textContent = `${cluster.count} Matching Sites`;
            }
        }

        // Highlight exemplar if matching
        document.querySelectorAll('.exemplar-item').forEach(item => {
            if (item.dataset.clusterId == clusterId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // Render matching tile grid
        this.renderTileGrid(clusterId);
        this.drawScatter();
    }

    renderTileGrid(clusterId) {
        const gallery = document.getElementById('cluster-tiles-gallery');
        if (!gallery) return;

        const filteredPoints = (clusterId === null || clusterId === undefined)
            ? this.points
            : this.points.filter(p => p.cluster_id === clusterId);

        if (filteredPoints.length === 0) {
            gallery.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; padding: 40px 20px; text-align:center;">
                    <i class="fa-solid fa-shapes" style="font-size:32px; color:#94a3b8; margin-bottom:10px;"></i>
                    <p style="color:#64748b; font-size:13px; font-weight:500;">No satellite footprints found for this category.</p>
                </div>
            `;
            return;
        }

        // Map cluster metadata lookup
        const clusterMap = {};
        this.clusters.forEach(c => { clusterMap[c.cluster_id] = c; });

        gallery.innerHTML = '';

        filteredPoints.forEach(p => {
            const cluster = clusterMap[p.cluster_id] || { label: 'Geospatial Site', color: '#2563eb' };
            const isSelected = p.tile_id === this.selectedTileId;

            const card = document.createElement('div');
            card.className = `cluster-tile-box ${isSelected ? 'active' : ''}`;
            card.setAttribute('onclick', `window.locateClusterTile('${p.tile_id}')`);
            card.innerHTML = `
                <div class="tile-box-thumb-wrap">
                    <img src="${p.preview_path || p.rgb_preview_path}" alt="Tile Preview" class="tile-box-img" loading="lazy" />
                    <div class="tile-date-tag">📅 ${p.acquisition_date || '2025-02-10'}</div>
                    <div class="tile-sensor-tag">${p.sensor_name || 'Sentinel-2 MSI'}</div>
                </div>
                <div class="tile-box-body">
                    <div class="tile-cluster-tag" style="color:${cluster.color}; background:${cluster.color}18; border:1px solid ${cluster.color}40;">
                        ${cluster.label}
                    </div>
                    <div class="tile-id-label" title="${p.tile_id}">
                        <strong>${p.tile_id}</strong>
                    </div>
                    <div class="tile-coords-meta">
                        <i class="fa-solid fa-location-dot" style="color:${cluster.color};"></i>
                        <span>Lat: ${(p.center_lat || 28.6139).toFixed(4)} | Lon: ${(p.center_lon || 77.2090).toFixed(4)}</span>
                    </div>
                    <div class="tile-btn-actions">
                        <button class="btn btn-primary btn-sm btn-tile-locate" onclick="event.stopPropagation(); window.locateClusterTile('${p.tile_id}')" title="Switch to Map & Highlight Footprint">
                            <i class="fa-solid fa-location-crosshairs"></i> Locate on Map
                        </button>
                        <button class="btn btn-outline btn-sm btn-tile-swipe" onclick="event.stopPropagation(); window.app.inspectTile('${p.tile_id}')" title="Inspect in Swipe Inspector">
                            <i class="fa-solid fa-code-compare"></i>
                        </button>
                    </div>
                </div>
            `;

            gallery.appendChild(card);
        });
    }

    renderExemplars() {
        const container = document.getElementById('cluster-exemplars-list');
        if (!container) return;
        container.innerHTML = '';

        this.clusters.forEach(c => {
            let icon = "fa-solid fa-tree";
            let dateStr = "2025-02-05";
            if (c.label.includes("Urban")) { icon = "fa-solid fa-city"; dateStr = "2025-01-10"; }
            else if (c.label.includes("Water")) { icon = "fa-solid fa-water"; dateStr = "2025-03-01"; }
            else if (c.label.includes("Runway") || c.label.includes("Airfield")) { icon = "fa-solid fa-plane-departure"; dateStr = "2025-01-05"; }

            const card = document.createElement('div');
            card.className = 'exemplar-item';
            card.dataset.clusterId = c.cluster_id;
            card.innerHTML = `
                <div class="exemplar-img-wrap">
                    <img src="${c.exemplar_preview}" alt="Exemplar" class="exemplar-thumb" />
                    <div class="exemplar-date-tag">📅 ${dateStr}</div>
                </div>
                <div class="exemplar-details">
                    <div style="font-size:12px; font-weight:700; color:${c.color}; display:flex; align-items:center; gap:6px;">
                        <i class="${icon}"></i> ${c.label}
                    </div>
                    <div style="font-size:10px; color:#64748b; margin-top:2px;">
                        <strong>${c.count} Regional Sites</strong> | Sentinel-2
                    </div>
                    <button class="btn btn-outline btn-sm btn-find-matching" style="margin-top:6px; width:100%; font-size:10px; padding:3px 6px;">
                        <i class="fa-solid fa-clone"></i> Find All Matching
                    </button>
                </div>
            `;

            const triggerSelect = () => {
                this.selectedTileId = c.exemplar_tile_id;
                this.selectCluster(c.cluster_id);
                this.findSimilarSites(c.exemplar_tile_id);
            };

            card.addEventListener('click', triggerSelect);

            const btnMatching = card.querySelector('.btn-find-matching');
            if (btnMatching) {
                btnMatching.addEventListener('click', (e) => {
                    e.stopPropagation();
                    triggerSelect();
                });
            }

            container.appendChild(card);
        });
    }

    drawScatter() {
        if (!this.ctx || !this.canvas) return;
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Draw clean slate grid
        ctx.strokeStyle = '#f1f5f9';
        ctx.lineWidth = 1;
        for (let x = 0; x < w; x += 40) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, h);
            ctx.stroke();
        }
        for (let y = 0; y < h; y += 40) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
            ctx.stroke();
        }

        // Color map by cluster ID
        const colorMap = {};
        this.clusters.forEach(c => { colorMap[c.cluster_id] = c.color; });

        // Map [-100, 100] coordinate to canvas (x, y)
        const padding = 40;
        const toCanvasX = (val) => padding + ((val + 100) / 200) * (w - 2 * padding);
        const toCanvasY = (val) => padding + ((val + 100) / 200) * (h - 2 * padding);

        // Draw points
        this.points.forEach(p => {
            const cx = toCanvasX(p.proj_x);
            const cy = toCanvasY(p.proj_y);
            const color = colorMap[p.cluster_id] || '#2563eb';
            const isSelected = p.tile_id === this.selectedTileId;
            const isClusterFiltered = (this.selectedClusterId === null || p.cluster_id === this.selectedClusterId);

            ctx.beginPath();
            ctx.arc(cx, cy, isSelected ? 8 : (isClusterFiltered ? 5 : 3), 0, 2 * Math.PI);
            ctx.fillStyle = isClusterFiltered ? color : `${color}40`;
            ctx.fill();

            if (isSelected) {
                ctx.lineWidth = 2.5;
                ctx.strokeStyle = '#0f172a';
                ctx.stroke();
            }
        });
    }

    handleMouseMove(e) {
        if (!this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const w = this.canvas.width;
        const h = this.canvas.height;
        const padding = 40;
        const toCanvasX = (val) => padding + ((val + 100) / 200) * (w - 2 * padding);
        const toCanvasY = (val) => padding + ((val + 100) / 200) * (h - 2 * padding);

        let closest = null;
        let minDist = 14;

        this.points.forEach(p => {
            const cx = toCanvasX(p.proj_x);
            const cy = toCanvasY(p.proj_y);
            const dist = Math.hypot(mouseX - cx, mouseY - cy);
            if (dist < minDist) {
                minDist = dist;
                closest = { ...p, cx, cy };
            }
        });

        const tooltip = document.getElementById('scatter-tooltip');
        if (closest && tooltip) {
            tooltip.style.display = 'block';
            tooltip.style.left = `${closest.cx + 12}px`;
            tooltip.style.top = `${closest.cy - 12}px`;
            tooltip.innerHTML = `
                <div style="font-family:'Inter',sans-serif; font-size:11px;">
                    <strong>${closest.tile_id}</strong><br/>
                    <span>Cluster: ${closest.cluster_id}</span><br/>
                    <span>Coordinates: ${(closest.center_lat || 28.6139).toFixed(4)}, ${(closest.center_lon || 77.2090).toFixed(4)}</span><br/>
                    <img src="${closest.preview_path || closest.rgb_preview_path}" style="width:70px; height:70px; object-fit:cover; margin-top:4px; border-radius:4px; border:1px solid #cbd5e1;" />
                </div>
            `;
        } else if (tooltip) {
            tooltip.style.display = 'none';
        }
    }

    handleClick(e) {
        if (!this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const w = this.canvas.width;
        const h = this.canvas.height;
        const padding = 40;
        const toCanvasX = (val) => padding + ((val + 100) / 200) * (w - 2 * padding);
        const toCanvasY = (val) => padding + ((val + 100) / 200) * (h - 2 * padding);

        this.points.forEach(p => {
            const cx = toCanvasX(p.proj_x);
            const cy = toCanvasY(p.proj_y);
            const dist = Math.hypot(mouseX - cx, mouseY - cy);
            if (dist < 14) {
                this.selectedTileId = p.tile_id;
                this.drawScatter();
                this.findSimilarSites(p.tile_id);
            }
        });
    }

    async findSimilarSites(tileId) {
        const resultsContainer = document.getElementById('similar-sites-results');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = '<div style="color:#2563eb; font-size:11px; padding:10px;"><i class="fa-solid fa-spinner fa-spin"></i> Retrieving counterpart sites across AOI...</div>';

        try {
            const res = await fetch('/api/clusters/find-similar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tile_id: tileId, top_k: 6 })
            });
            const data = await res.json();
            this.renderSimilarSites(data.similar_sites);
        } catch (err) {
            console.error('[ClusterExplorer] Find similar error:', err);
        }
    }

    renderSimilarSites(sites) {
        const container = document.getElementById('similar-sites-results');
        if (!container) return;

        if (!sites || sites.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No similar counterpart sites found.</p></div>';
            return;
        }

        container.innerHTML = '';
        sites.forEach(s => {
            if (s.tile_id) {
                window.allClusterTiles[s.tile_id] = s;
            }

            const card = document.createElement('div');
            card.className = 'similar-tile-card';
            card.setAttribute('onclick', `window.locateClusterTile('${s.tile_id}')`);
            card.innerHTML = `
                <div style="position:relative; width:100%; height:75px; overflow:hidden; border-radius:4px;">
                    <img src="${s.rgb_preview_path}" alt="Similar Site" style="width:100%; height:100%; object-fit:cover;" />
                    <div style="position:absolute; top:4px; right:4px; background:rgba(15,23,42,0.85); color:#fff; font-size:9px; font-weight:700; padding:1px 5px; border-radius:3px;">
                        ${(s.similarity_score * 100).toFixed(1)}% Sim
                    </div>
                </div>
                <div style="font-size:10px; font-weight:600; color:#0f172a; margin-top:4px; line-height:1.2; word-break:break-all;">
                    ${s.tile_id}
                </div>
                <div style="display:flex; gap:4px; margin-top:6px;">
                    <button class="btn btn-primary btn-sm btn-locate-similar" onclick="event.stopPropagation(); window.locateClusterTile('${s.tile_id}')" style="flex:1; font-size:9px; padding:3px 4px;">
                        <i class="fa-solid fa-location-crosshairs"></i> Map
                    </button>
                    <button class="btn btn-outline btn-sm btn-swipe-similar" onclick="event.stopPropagation(); window.app.inspectTile('${s.tile_id}')" style="font-size:9px; padding:3px 6px;">
                        <i class="fa-solid fa-code-compare"></i>
                    </button>
                </div>
            `;

            container.appendChild(card);
        });
    }
}

window.ClusterExplorer = ClusterExplorer;
