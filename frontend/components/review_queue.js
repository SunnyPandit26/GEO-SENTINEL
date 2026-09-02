/**
 * GEO-SENTINEL Analyst Review Queue Component
 * Prioritized review queue with active learning feedback loop,
 * status filtering, and one-click triage actions.
 */

class ReviewQueue {
    constructor() {
        this.queueItems = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadQueue();
    }

    bindEvents() {
        const filterStatus = document.getElementById('queue-filter-status');
        const filterSeverity = document.getElementById('queue-filter-severity');

        if (filterStatus) {
            filterStatus.addEventListener('change', () => this.loadQueue());
        }

        if (filterSeverity) {
            filterSeverity.addEventListener('change', () => this.loadQueue());
        }
    }

    async loadQueue() {
        const filterStatus = document.getElementById('queue-filter-status')?.value || '';
        const filterSeverity = document.getElementById('queue-filter-severity')?.value || '';

        try {
            let url = '/api/change/queue?';
            if (filterStatus) url += `status=${filterStatus}&`;
            if (filterSeverity) url += `severity=${filterSeverity}&`;

            const res = await fetch(url);
            const data = await res.json();
            this.queueItems = data.queue || [];

            // Update badge counter in header
            const badgeEl = document.getElementById('badge-queue-count');
            if (badgeEl) {
                const unreviewedCount = this.queueItems.filter(i => i.triage_status === 'unreviewed').length;
                badgeEl.textContent = unreviewedCount;
            }

            this.renderTable();
        } catch (err) {
            console.error('[ReviewQueue] Error loading queue:', err);
        }
    }

    renderTable() {
        const tbody = document.getElementById('queue-table-body');
        if (!tbody) return;

        if (this.queueItems.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align:center; padding:30px; color:#64748b;">
                        <i class="fa-solid fa-check-double" style="font-size:24px; margin-bottom:8px; display:block;"></i>
                        No pending change items matching current filter criteria.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = '';

        this.queueItems.forEach(item => {
            const tr = document.createElement('tr');
            
            const severityClass = item.severity === 'High' ? 'badge-high' : (item.severity === 'Medium' ? 'badge-warning' : 'badge-info');
            const statusColor = item.triage_status === 'confirmed' ? '#22c55e' : (item.triage_status === 'rejected' ? '#ef4444' : '#f59e0b');

            tr.innerHTML = `
                <td><code>${item.change_id}</code></td>
                <td>
                    <img src="${item.diff_heatmap_path}" alt="Heatmap" style="width:50px; height:50px; object-fit:cover; border-radius:4px; border:1px solid rgba(56,189,248,0.3);" />
                </td>
                <td>
                    <strong>${item.change_type}</strong>
                    <div style="font-size:11px; color:#94a3b8;">${item.scene_t1_id} &rarr; ${item.scene_t2_id}</div>
                </td>
                <td><span class="badge ${severityClass}">${item.severity}</span></td>
                <td><strong>${(item.confidence_score * 100).toFixed(1)}%</strong></td>
                <td><span class="accent-text" style="color:#f59e0b; font-family:var(--font-mono);">${item.earliest_observation_date}</span></td>
                <td><code>${item.center_lat.toFixed(3)}, ${item.center_lon.toFixed(3)}</code></td>
                <td>
                    <span style="color:${statusColor}; font-weight:700; text-transform:uppercase; font-size:11px;">
                        <i class="fa-solid fa-circle" style="font-size:8px;"></i> ${item.triage_status}
                    </span>
                </td>
                <td>
                    <div style="display:flex; gap:4px;">
                        <button class="btn btn-success btn-sm" onclick="window.app.reviewQueue.triage('${item.change_id}', 'confirm')" title="Confirm Valid Change"><i class="fa-solid fa-check"></i></button>
                        <button class="btn btn-danger btn-sm" onclick="window.app.reviewQueue.triage('${item.change_id}', 'reject')" title="Reject False Alarm"><i class="fa-solid fa-xmark"></i></button>
                        <button class="btn btn-outline btn-sm" onclick="window.app.inspectTile('${item.tile_id}')" title="Inspect in Swipe"><i class="fa-solid fa-eye"></i></button>
                    </div>
                </td>
            `;

            tbody.appendChild(tr);
        });
    }

    async triage(changeId, action) {
        try {
            const res = await fetch('/api/change/triage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    change_id: changeId,
                    action: action,
                    analyst_id: "Analyst_Alpha",
                    notes: `Triaged via Review Queue as ${action}`
                })
            });

            const data = await res.json();
            
            // Update active learning indicator
            const weightsEl = document.getElementById('live-active-learning-weights');
            if (weightsEl && data.active_learning_weights) {
                const w = data.active_learning_weights;
                weightsEl.innerHTML = `
                    <span>Semantic: <strong>${(w.semantic*100).toFixed(0)}%</strong></span>
                    <span>Quality QA: <strong>${(w.quality*100).toFixed(0)}%</strong></span>
                    <span>Spatial: <strong>${(w.spatial*100).toFixed(0)}%</strong></span>
                `;
            }

            this.loadQueue();
        } catch (err) {
            console.error('[ReviewQueue] Triage action error:', err);
        }
    }
}

window.ReviewQueue = ReviewQueue;
