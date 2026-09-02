/**
 * GEO-SENTINEL Cluster & Site Discovery Explorer Component
 * Visualizes 2D latent semantic embedding projections, cluster exemplars,
 * and executes one-click discovery of comparable locations across the regional AOI.
 */

class ClusterExplorer {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.clusters = [];
        this.points = [];
        this.selectedTileId = null;
        this.hoveredPoint = null;
        this.init();
    }

    init() {
        this.canvas = document.getElementById('cluster-scatter-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');

        this.setupCanvas();
        this.bindEvents();
        this.loadClusterData();
    }

    setupCanvas() {
        const resize = () => {
            const rect = this.canvas.parentElement.getBoundingClientRect();
            this.canvas.width = rect.width;
            this.canvas.height = Math.max(450, rect.height - 40);
            this.drawScatter();
        };
        window.addEventListener('resize', resize);
        setTimeout(resize, 100);
    }

    bindEvents() {
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
    }

    async loadClusterData() {
        try {
            const res = await fetch('/api/clusters');
            const data = await res.json();
            this.clusters = data.clusters || [];
            this.points = data.points || [];

            this.renderLegend();
            this.renderExemplars();
            this.drawScatter();
        } catch (err) {
            console.error('[ClusterExplorer] Error loading clusters:', err);
        }
    }

    renderLegend() {
        const container = document.getElementById('cluster-legend-list');
        if (!container) return;
        container.innerHTML = '';

        this.clusters.forEach(c => {
            const badge = document.createElement('span');
            badge.className = 'badge';
            badge.style.border = `1px solid ${c.color}`;
            badge.style.color = c.color;
            badge.style.background = `${c.color}15`;
            badge.textContent = `${c.label} (${c.count})`;
            container.appendChild(badge);
        });
    }

    renderExemplars() {
        const container = document.getElementById('cluster-exemplars-list');
        if (!container) return;
        container.innerHTML = '';

        this.clusters.forEach(c => {
            const card = document.createElement('div');
            card.className = 'exemplar-card';
            card.innerHTML = `
                <img src="${c.exemplar_preview}" alt="Exemplar" class="exemplar-thumb" />
                <div style="font-size:11px; font-weight:600; color:${c.color};">${c.label}</div>
                <div style="font-size:10px; color:#94a3b8;">${c.count} Regional Sites</div>
            `;
            card.addEventListener('click', () => {
                this.selectedTileId = c.exemplar_tile_id;
                this.findSimilarSites(c.exemplar_tile_id);
            });
            container.appendChild(card);
        });
    }

    drawScatter() {
        if (!this.ctx || !this.canvas) return;
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Draw grid
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
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
            const color = colorMap[p.cluster_id] || '#38bdf8';
            const isSelected = p.tile_id === this.selectedTileId;

            ctx.beginPath();
            ctx.arc(cx, cy, isSelected ? 8 : 4.5, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();

            if (isSelected) {
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2;
                ctx.stroke();
            }
        });
    }

    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const w = this.canvas.width;
        const h = this.canvas.height;
        const padding = 40;
        const toCanvasX = (val) => padding + ((val + 100) / 200) * (w - 2 * padding);
        const toCanvasY = (val) => padding + ((val + 100) / 200) * (h - 2 * padding);

        let closest = null;
        let minDist = 12;

        this.points.forEach(p => {
            const cx = toCanvasX(p.proj_x);
            const cy = toCanvasY(p.proj_y);
            const dist = Math.hypot(mouseX - cx, mouseY - cy);
            if (dist < minDist) {
                minDist = dist;
                closest = p;
            }
        });

        const tooltip = document.getElementById('scatter-tooltip');
        if (closest && tooltip) {
            tooltip.style.display = 'block';
            tooltip.style.left = `${e.clientX + 12}px`;
            tooltip.style.top = `${e.clientY + 12}px`;
            tooltip.innerHTML = `
                <div style="font-size:11px; font-family:sans-serif; background:#0d1222; border:1px solid #38bdf8; padding:8px; border-radius:4px; color:#fff;">
                    <strong>${closest.tile_id}</strong><br/>
                    <span>Cluster: ${closest.cluster_id}</span><br/>
                    <span>Lat: ${closest.center_lat.toFixed(4)} | Lon: ${closest.center_lon.toFixed(4)}</span><br/>
                    <img src="${closest.preview_path}" style="width:60px; height:60px; object-fit:cover; margin-top:4px;" />
                </div>
            `;
        } else if (tooltip) {
            tooltip.style.display = 'none';
        }
    }

    handleClick(e) {
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
            if (dist < 12) {
                this.selectedTileId = p.tile_id;
                this.drawScatter();
                this.findSimilarSites(p.tile_id);
            }
        });
    }

    async findSimilarSites(tileId) {
        const resultsContainer = document.getElementById('similar-sites-results');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = '<div style="color:#38bdf8; font-size:11px;"><i class="fa-solid fa-spinner fa-spin"></i> Retrieving counterpart sites across AOI...</div>';

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
            const card = document.createElement('div');
            card.className = 'similar-tile-card';
            card.innerHTML = `
                <img src="${s.rgb_preview_path}" alt="Similar Site" />
                <div style="font-size:10px; font-weight:600; color:#38bdf8; margin-top:2px;">${(s.similarity_score * 100).toFixed(1)}% Sim</div>
                <div style="font-size:9px; color:#94a3b8;">${s.tile_id}</div>
            `;
            card.addEventListener('click', () => {
                if (window.app && window.app.mapView) {
                    window.app.mapView.highlightTile(s);
                }
            });
            container.appendChild(card);
        });
    }
}

window.ClusterExplorer = ClusterExplorer;
