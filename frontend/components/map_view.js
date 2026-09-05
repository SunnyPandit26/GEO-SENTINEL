/**
 * GEO-SENTINEL Tactical Map Component
 * Interactive Leaflet geospatial map with satellite tile image overlays,
 * change vector polygons, and AOI bounding box filtering.
 */

class TacticalMapView {
    constructor() {
        this.map = null;
        this.tileLayerGroup = null;
        this.changeLayerGroup = null;
        this.imageOverlaysGroup = null;
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

        // High-definition Satellite & Tactical Street Map Base Layers (Zero API Key)
        const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: '&copy; Esri, Maxar, Earthstar Geographics, CNES/Airbus DS',
            maxZoom: 19
        });

        const osmStandard = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19
        });

        // Default to Satellite Imagery
        esriSatellite.addTo(this.map);

        // Layer Switcher Control
        const baseMaps = {
            "🛰️ Satellite Imagery": esriSatellite,
            "🗺️ Tactical Street Map": osmStandard
        };
        L.control.layers(baseMaps, null, { position: 'topright' }).addTo(this.map);

        this.imageOverlaysGroup = L.layerGroup().addTo(this.map);
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
                if (e.target.checked) {
                    this.tileLayerGroup.addTo(this.map);
                    this.imageOverlaysGroup.addTo(this.map);
                } else {
                    this.map.removeLayer(this.tileLayerGroup);
                    this.map.removeLayer(this.imageOverlaysGroup);
                }
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
            const res = await fetch('/api/tiles?limit=40');
            const data = await res.json();
            this.renderTileFootprints(data.tiles);
        } catch (err) {
            console.error('[MapView] Error loading tiles:', err);
        }
    }

    renderTileFootprints(tiles) {
        this.tileLayerGroup.clearLayers();
        this.imageOverlaysGroup.clearLayers();

        if (!tiles || tiles.length === 0) return;

        tiles.forEach(tile => {
            const bounds = [
                [tile.bbox_min_lat, tile.bbox_min_lon],
                [tile.bbox_max_lat, tile.bbox_max_lon]
            ];

            // 1. Overlay actual georeferenced satellite tile image on map
            if (tile.rgb_preview_path) {
                const overlay = L.imageOverlay(tile.rgb_preview_path, bounds, {
                    opacity: 0.92,
                    interactive: true
                });
                this.imageOverlaysGroup.addLayer(overlay);
            }

            // 2. Render crisp tactical perimeter bounding box
            const rect = L.rectangle(bounds, {
                color: '#2563eb',
                weight: 2,
                fillColor: '#2563eb',
                fillOpacity: 0.08
            });

            // Extract readable category
            let category = "Urban Construction & Riverfront";
            if (tile.scene_id.includes("forest")) category = "Forest Canopy & Deforestation";
            else if (tile.scene_id.includes("water")) category = "Water Reservoir & Inundation";
            else if (tile.scene_id.includes("airfield")) category = "Airfield Logistics & Runway";

            const popupContent = `
                <div style="color:#0f172a; font-size:12px; font-family:'Inter',sans-serif; min-width:180px; padding:2px;">
                    <div style="font-weight:700; font-size:13px; color:#2563eb; margin-bottom:4px;">${category}</div>
                    <div style="font-size:11px; color:#475569; margin-bottom:6px;">
                        <strong>Tile:</strong> ${tile.tile_id}<br/>
                        <strong>Date:</strong> ${tile.acquisition_date || '2025'}<br/>
                        <strong>Sensor:</strong> ${tile.sensor_name || 'Sentinel-2 MSI'}<br/>
                        <strong>Coordinates:</strong> ${tile.center_lat.toFixed(4)}, ${tile.center_lon.toFixed(4)}
                    </div>
                    <img src="${tile.rgb_preview_path}" style="width:100%; height:90px; object-fit:cover; border-radius:6px; border:1px solid #e2e8f0; margin-bottom:8px; display:block;"/>
                    <button onclick="window.app.inspectTile('${tile.tile_id}')" style="background:#2563eb; color:#ffffff; border:none; padding:7px 12px; border-radius:6px; font-weight:600; font-size:11px; cursor:pointer; width:100%; display:flex; align-items:center; justify-content:center; gap:6px;">
                        <i class="fa-solid fa-code-compare"></i> Inspect in Swipe View
                    </button>
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
        if (!tile) return;

        let minLat, minLon, maxLat, maxLon;
        if (tile.bbox && Array.isArray(tile.bbox) && tile.bbox.length === 4 && tile.bbox[0] !== undefined && tile.bbox[0] !== null) {
            minLat = tile.bbox[0];
            minLon = tile.bbox[1];
            maxLat = tile.bbox[2];
            maxLon = tile.bbox[3];
        } else if (tile.bbox_min_lat !== undefined && tile.bbox_min_lat !== null) {
            minLat = tile.bbox_min_lat;
            minLon = tile.bbox_min_lon;
            maxLat = tile.bbox_max_lat;
            maxLon = tile.bbox_max_lon;
        } else {
            const lat = tile.center_lat || 28.6139;
            const lon = tile.center_lon || 77.2090;
            const d = 0.005;
            minLat = lat - d;
            minLon = lon - d;
            maxLat = lat + d;
            maxLon = lon + d;
        }

        const centerLat = tile.center_lat || (minLat + maxLat) / 2;
        const centerLon = tile.center_lon || (minLon + maxLon) / 2;
        const bounds = [[minLat, minLon], [maxLat, maxLon]];

        // Smooth flight animation to satellite tile footprint
        this.map.flyTo([centerLat, centerLon], 15, { duration: 0.7 });

        // Ensure high-definition satellite overlay exists
        const imgPath = tile.preview_path || tile.rgb_preview_path;
        if (imgPath) {
            const overlay = L.imageOverlay(imgPath, bounds, { opacity: 0.95 }).addTo(this.imageOverlaysGroup);
        }

        // Remove previous highlight rectangle if any
        if (this.currentHighlightLayer) {
            this.map.removeLayer(this.currentHighlightLayer);
        }

        // Tactical bounding box with glowing blue pulse
        const highlightRect = L.rectangle(bounds, {
            color: '#2563eb',
            weight: 4,
            fillColor: '#3b82f6',
            fillOpacity: 0.35,
            dashArray: '6, 6',
            className: 'tactical-highlight-pulse'
        }).addTo(this.map);

        this.currentHighlightLayer = highlightRect;

        // Extract readable category
        let category = "Urban Construction & Riverfront";
        if (tile.tile_id && tile.tile_id.includes("forest")) category = "Forest Canopy & Deforestation";
        else if (tile.tile_id && tile.tile_id.includes("water")) category = "Water Bodies & Inundation";
        else if (tile.tile_id && tile.tile_id.includes("airfield")) category = "Airfield Logistics & Runway";

        const popupContent = `
            <div style="color:#0f172a; font-size:12px; font-family:'Inter',sans-serif; min-width:200px; padding:2px;">
                <div style="font-weight:700; font-size:13px; color:#2563eb; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                    <i class="fa-solid fa-location-crosshairs"></i> ${category}
                </div>
                <div style="font-size:11px; color:#475569; margin-bottom:6px;">
                    <strong>Tile ID:</strong> ${tile.tile_id}<br/>
                    <strong>Acquisition Date:</strong> ${tile.acquisition_date || '2025-02-10'}<br/>
                    <strong>Sensor Platform:</strong> ${tile.sensor_name || 'Sentinel-2 MSI'}<br/>
                    <strong>Center Coords:</strong> ${centerLat.toFixed(4)}, ${centerLon.toFixed(4)}
                </div>
                ${imgPath ? `<img src="${imgPath}" style="width:100%; height:90px; object-fit:cover; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:8px; display:block;"/>` : ''}
                <button onclick="window.app.inspectTile('${tile.tile_id}')" style="background:#2563eb; color:#ffffff; border:none; padding:7px 12px; border-radius:6px; font-weight:600; font-size:11px; cursor:pointer; width:100%; display:flex; align-items:center; justify-content:center; gap:6px;">
                    <i class="fa-solid fa-code-compare"></i> Inspect in Swipe View
                </button>
            </div>
        `;

        highlightRect.bindPopup(popupContent).openPopup();
    }

    renderChangePolygons(geojson) {
        this.changeLayerGroup.clearLayers();
        if (!geojson || !geojson.features) return;

        L.geoJSON(geojson, {
            style: {
                color: '#dc2626',
                weight: 2.5,
                fillColor: '#ef4444',
                fillOpacity: 0.45
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties || {};
                layer.bindPopup(`
                    <div style="font-size:12px; color:#0f172a; font-family:'Inter',sans-serif;">
                        <strong style="color:#dc2626;">🚨 Detected Change Vector</strong><br/>
                        <strong>Type:</strong> ${props.type || 'Structural Change'}<br/>
                        <strong>Severity:</strong> ${props.severity || 'High'}<br/>
                        <strong>Confidence:</strong> ${props.confidence ? (props.confidence*100).toFixed(1) + '%' : '92.4%'}
                    </div>
                `);
            }
        }).addTo(this.changeLayerGroup);
    }
}

window.TacticalMapView = TacticalMapView;
