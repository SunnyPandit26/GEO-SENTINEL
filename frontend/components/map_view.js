/**
 * GEO-SENTINEL Tactical Map Component
 * Interactive Leaflet geospatial map for satellite tile footprints,
 * change vector polygons, and AOI bounding box filtering.
 */

class TacticalMapView {
    constructor() {
        this.map = null;
        this.tileLayerGroup = null;
        this.changeLayerGroup = null;
        this.aoiLayerGroup = null;
        this.currentAOI = null;
        this.init();
    }

    init() {
        // Initialize Leaflet map centered over Riverfront / Delhi AOI
        this.map = L.map('tactical-map', {
            center: [28.6139, 77.2090],
            zoom: 14,
            zoomControl: true
        });

        // High-contrast dark tactical base tiles
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; CartoDB &copy; OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(this.map);

        this.tileLayerGroup = L.layerGroup().addTo(this.map);
        this.changeLayerGroup = L.layerGroup().addTo(this.map);
        this.aoiLayerGroup = L.layerGroup().addTo(this.map);

        // Track cursor coordinates
        this.map.on('mousemove', (e) => {
            const coordsEl = document.getElementById('map-cursor-coords');
            if (coordsEl) {
                coordsEl.textContent = `Lat: ${e.latlng.lat.toFixed(4)} | Lon: ${e.latlng.lng.toFixed(4)} | Zoom: ${this.map.getZoom()}`;
            }
        });

        this.setupLayerToggles();
        this.loadInitialTiles();
    }

    setupLayerToggles() {
        const toggleTiles = document.getElementById('layer-toggle-tiles');
        const toggleChanges = document.getElementById('layer-toggle-changes');

        if (toggleTiles) {
            toggleTiles.addEventListener('change', (e) => {
                if (e.target.checked) this.tileLayerGroup.addTo(this.map);
                else this.map.removeLayer(this.tileLayerGroup);
            });
        }

        if (toggleChanges) {
            toggleChanges.addEventListener('change', (e) => {
                if (e.target.checked) this.changeLayerGroup.addTo(this.map);
                else this.map.removeLayer(this.changeLayerGroup);
            });
        }
    }

    async loadInitialTiles() {
        try {
            const res = await fetch('/api/tiles?limit=30');
            const data = await res.json();
            this.renderTileFootprints(data.tiles);
        } catch (err) {
            console.error('[MapView] Error loading tiles:', err);
        }
    }

    renderTileFootprints(tiles) {
        this.tileLayerGroup.clearLayers();

        tiles.forEach(tile => {
            const bounds = [
                [tile.bbox_min_lat, tile.bbox_min_lon],
                [tile.bbox_max_lat, tile.bbox_max_lon]
            ];

            // Render bounding rectangle
            const rect = L.rectangle(bounds, {
                color: '#38bdf8',
                weight: 1.5,
                fillColor: '#0369a1',
                fillOpacity: 0.15
            });

            const popupContent = `
                <div style="color:#000; font-size:12px; font-family:sans-serif;">
                    <strong>Tile ID:</strong> ${tile.tile_id}<br/>
                    <strong>Scene:</strong> ${tile.scene_id}<br/>
                    <strong>Quality Score:</strong> ${(tile.quality_score * 100).toFixed(1)}%<br/>
                    <strong>NDVI:</strong> ${tile.ndvi_mean || 'N/A'}<br/>
                    <img src="${tile.rgb_preview_path}" style="width:100px; height:100px; object-fit:cover; margin-top:6px; border-radius:4px;"/><br/>
                    <button onclick="window.app.inspectTile('${tile.tile_id}')" style="background:#0284c7; color:#fff; border:none; padding:4px 8px; border-radius:3px; margin-top:6px; cursor:pointer; width:100%;">Inspect in Swipe</button>
                </div>
            `;
            rect.bindPopup(popupContent);
            this.tileLayerGroup.addLayer(rect);
        });

        if (tiles.length > 0) {
            const first = tiles[0];
            this.map.panTo([first.center_lat, first.center_lon]);
        }
    }

    highlightTile(tile) {
        if (!tile || !tile.center_lat) return;
        this.map.flyTo([tile.center_lat, tile.center_lon], 15, { duration: 1.0 });

        const bounds = [
            [tile.bbox[0], tile.bbox[1]],
            [tile.bbox[2], tile.bbox[3]]
        ];

        const highlightRect = L.rectangle(bounds, {
            color: '#f59e0b',
            weight: 3,
            fillColor: '#f59e0b',
            fillOpacity: 0.35
        }).addTo(this.map);

        setTimeout(() => {
            this.map.removeLayer(highlightRect);
        }, 3500);
    }

    renderChangePolygons(geojson) {
        this.changeLayerGroup.clearLayers();
        if (!geojson || !geojson.features) return;

        L.geoJSON(geojson, {
            style: {
                color: '#ef4444',
                weight: 2,
                fillColor: '#ef4444',
                fillOpacity: 0.45
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties || {};
                layer.bindPopup(`
                    <div style="color:#000; font-size:12px;">
                        <strong>Change:</strong> ${props.change_type || 'Anomaly'}<br/>
                        <strong>Subtype:</strong> ${props.subtype || 'N/A'}<br/>
                        <strong>Area:</strong> ${props.area_pixels || 0} px
                    </div>
                `);
            }
        }).addTo(this.changeLayerGroup);
    }
}

window.TacticalMapView = TacticalMapView;
