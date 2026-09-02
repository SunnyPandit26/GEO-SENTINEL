"""
GEO-SENTINEL Realistic Multi-Temporal Multi-Spectral GeoTIFF Dataset Generator
Generates georeferenced 4-band (Red, Green, Blue, NIR) GeoTIFF satellite scenes across 4 realistic scenarios,
4 chronological time steps (T1..T4), sensor metadata, and atmospheric/seasonal variations to validate
semantic search, change detection, false-alarm rejection, and earliest observation estimation.
"""

import os
import rasterio
from rasterio.transform import from_bounds
import numpy as np
import cv2

SCENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenes")
os.makedirs(SCENES_DIR, exist_ok=True)


def create_base_canvas(width=512, height=512):
    """Creates base background texture (soil, grassland, terrain noise)."""
    np.random.seed(42)
    # Perlin-like fractal terrain noise
    base = np.zeros((height, width), dtype=np.float32)
    for scale, weight in [(64, 0.5), (32, 0.25), (16, 0.15), (8, 0.1)]:
        noise = cv2.resize(np.random.randn(height // scale, width // scale).astype(np.float32), (width, height))
        base += noise * weight
    
    # Normalize to [0.3, 0.7]
    base = (base - base.min()) / (base.max() - base.min() + 1e-6)
    return base


def save_geotiff(filename, rgb_bands, nir_band, bounds, crs="EPSG:4326"):
    """
    Saves a 4-band GeoTIFF with affine transform and georeferencing.
    bounds = (min_lon, min_lat, max_lon, max_lat)
    """
    filepath = os.path.join(SCENES_DIR, filename)
    min_lon, min_lat, max_lon, max_lat = bounds
    height, width = rgb_bands.shape[1], rgb_bands.shape[2]

    transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)

    with rasterio.open(
        filepath,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=4,
        dtype='uint8',
        crs=crs,
        transform=transform
    ) as dst:
        dst.write(rgb_bands[0], 1)  # Red
        dst.write(rgb_bands[1], 2)  # Green
        dst.write(rgb_bands[2], 3)  # Blue
        dst.write(nir_band, 4)      # NIR

    print(f"Generated GeoTIFF: {filepath} ({width}x{height}, 4 bands)")
    return filepath


def generate_scenario_1_urban_construction():
    """
    Scenario 1: Riverfront Urban Construction & Building Expansion
    Location: Riverfront Zone Alpha (Lat: 28.6139, Lon: 77.2090)
    """
    bounds = (77.2000, 28.6050, 77.2200, 28.6250)
    width, height = 512, 512
    terrain = create_base_canvas(width, height)

    # Time steps: T1 (Jan), T2 (Apr), T3 (Aug), T4 (Nov)
    dates = ["2025-01-10", "2025-04-15", "2025-08-20", "2025-11-25"]

    for step, date_str in enumerate(dates):
        # 1. Base terrain (vegetation and soil)
        r = (terrain * 120 + 40).astype(np.uint8)
        g = (terrain * 170 + 60).astype(np.uint8)
        b = (terrain * 90 + 30).astype(np.uint8)
        nir = (terrain * 210 + 40).astype(np.uint8)

        # 2. Draw curved River
        pts = np.array([[50, 0], [120, 150], [200, 300], [240, 512], [290, 512], [250, 300], [170, 150], [100, 0]], np.int32)
        cv2.fillPoly(r, [pts], 35)
        cv2.fillPoly(g, [pts], 80)
        cv2.fillPoly(b, [pts], 160)
        cv2.fillPoly(nir, [pts], 20)  # Water absorbs NIR strongly

        # 3. Evolution of Riverfront Construction Site (East of river, x: 300-450, y: 150-350)
        site_box = (310, 160, 460, 360)
        x1, y1, x2, y2 = site_box

        if step == 0:
            # T1: Natural vegetation & open green meadow
            pass
        elif step == 1:
            # T2 (Onset T*): Earthwork clearance, ground leveling, yellow bare soil
            r[y1:y2, x1:x2] = 190
            g[y1:y2, x1:x2] = 165
            b[y1:y2, x1:x2] = 110
            nir[y1:y2, x1:x2] = 130
        elif step == 2:
            # T3: Foundation trenches, concrete pads, access roads
            r[y1:y2, x1:x2] = 160
            g[y1:y2, x1:x2] = 150
            b[y1:y2, x1:x2] = 145
            nir[y1:y2, x1:x2] = 120
            # Concrete rectangles
            for bx, by in [(330, 180), (400, 180), (330, 260), (400, 260)]:
                cv2.rectangle(r, (bx, by), (bx + 50, by + 60), 220, -1)
                cv2.rectangle(g, (bx, by), (bx + 50, by + 60), 220, -1)
                cv2.rectangle(b, (bx, by), (bx + 50, by + 60), 225, -1)
                cv2.rectangle(nir, (bx, by), (bx + 50, by + 60), 160, -1)
        elif step == 3:
            # T4: Fully erected high-density residential towers, asphalt parking, vehicles
            r[y1:y2, x1:x2] = 120
            g[y1:y2, x1:x2] = 120
            b[y1:y2, x1:x2] = 130
            nir[y1:y2, x1:x2] = 110
            # Buildings with shadows
            for bx, by in [(330, 180), (400, 180), (330, 260), (400, 260)]:
                # Shadow
                cv2.rectangle(r, (bx + 8, by + 8), (bx + 58, by + 68), 30, -1)
                cv2.rectangle(g, (bx + 8, by + 8), (bx + 58, by + 68), 30, -1)
                cv2.rectangle(b, (bx + 8, by + 8), (bx + 58, by + 68), 40, -1)
                # Roof
                cv2.rectangle(r, (bx, by), (bx + 50, by + 60), 240, -1)
                cv2.rectangle(g, (bx, by), (bx + 50, by + 60), 235, -1)
                cv2.rectangle(b, (bx, by), (bx + 50, by + 60), 245, -1)
                cv2.rectangle(nir, (bx, by), (bx + 50, by + 60), 180, -1)
            # Paved access road connecting to bridge
            cv2.line(r, (250, 260), (330, 260), 70, 8)
            cv2.line(g, (250, 260), (330, 260), 70, 8)
            cv2.line(b, (250, 260), (330, 260), 75, 8)
            cv2.line(nir, (250, 260), (330, 260), 60, 8)

        # Inject minor sensor noise
        noise = np.random.normal(0, 3, (height, width)).astype(np.int16)
        r = np.clip(r.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        g = np.clip(g.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        b = np.clip(b.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        rgb_stack = np.stack([r, g, b], axis=0)
        filename = f"scene_urban_river_{step+1}_{date_str}.tif"
        save_geotiff(filename, rgb_stack, nir, bounds)


def generate_scenario_2_deforestation():
    """
    Scenario 2: Forest Clearance & Deforestation
    Location: Sector Forest Bravo (Lat: -3.4653, Lon: -62.2159)
    """
    bounds = (-62.2250, -3.4750, -62.2050, -3.4550)
    width, height = 512, 512
    dates = ["2025-02-05", "2025-05-18", "2025-08-12", "2025-10-30"]

    for step, date_str in enumerate(dates):
        # Deep dense rainforest canopy
        r = np.random.randint(25, 45, (height, width), dtype=np.uint8)
        g = np.random.randint(90, 140, (height, width), dtype=np.uint8)
        b = np.random.randint(20, 40, (height, width), dtype=np.uint8)
        nir = np.random.randint(190, 245, (height, width), dtype=np.uint8)

        # Clearance polygon evolution (Center: x 180-360, y 150-380)
        if step >= 1:
            # T2: Fishbone logging roads
            cv2.line(r, (50, 250), (450, 250), 160, 6)
            cv2.line(g, (50, 250), (450, 250), 140, 6)
            cv2.line(b, (50, 250), (450, 250), 100, 6)
            cv2.line(nir, (50, 250), (450, 250), 110, 6)
        if step >= 2:
            # T3 (Onset T*): Large rectangular clear-cut zone
            cv2.rectangle(r, (160, 140), (380, 360), 185, -1)
            cv2.rectangle(g, (160, 140), (380, 360), 150, -1)
            cv2.rectangle(b, (160, 140), (380, 360), 105, -1)
            cv2.rectangle(nir, (160, 140), (380, 360), 85, -1)  # Drastic drop in NIR!
        if step >= 3:
            # T4: Fully converted agricultural fields with furrows
            cv2.rectangle(r, (150, 130), (400, 380), 200, -1)
            cv2.rectangle(g, (150, 130), (400, 380), 170, -1)
            cv2.rectangle(b, (150, 130), (400, 380), 115, -1)
            cv2.rectangle(nir, (150, 130), (400, 380), 95, -1)

        # Inject minor cloud in step 1 (T2) to test QA false-alarm suppression
        if step == 1:
            # Small cloud puff at top right
            cv2.circle(r, (420, 70), 45, 240, -1)
            cv2.circle(g, (420, 70), 45, 245, -1)
            cv2.circle(b, (420, 70), 45, 255, -1)
            cv2.circle(nir, (420, 70), 45, 230, -1)

        rgb_stack = np.stack([r, g, b], axis=0)
        filename = f"scene_forest_clearance_{step+1}_{date_str}.tif"
        save_geotiff(filename, rgb_stack, nir, bounds)


def generate_scenario_3_water_flood():
    """
    Scenario 3: Reservoir Water Extent & River Inundation
    Location: Sector River Charlie (Lat: 25.3176, Lon: 82.9739)
    """
    bounds = (82.9650, 25.3050, 82.9850, 25.3250)
    width, height = 512, 512
    dates = ["2025-03-01", "2025-06-15", "2025-07-28", "2025-10-10"]

    for step, date_str in enumerate(dates):
        # Agricultural floodplain terrain
        r = np.random.randint(140, 180, (height, width), dtype=np.uint8)
        g = np.random.randint(160, 200, (height, width), dtype=np.uint8)
        b = np.random.randint(90, 120, (height, width), dtype=np.uint8)
        nir = np.random.randint(170, 220, (height, width), dtype=np.uint8)

        # River path
        pts_normal = np.array([[200, 0], [210, 200], [220, 350], [230, 512], [270, 512], [260, 350], [250, 200], [240, 0]], np.int32)
        pts_flood = np.array([[120, 0], [110, 200], [90, 350], [100, 512], [410, 512], [390, 350], [380, 200], [350, 0]], np.int32)

        water_pts = pts_normal if (step == 0 or step == 3) else pts_flood

        cv2.fillPoly(r, [water_pts], 40)
        cv2.fillPoly(g, [water_pts], 90)
        cv2.fillPoly(b, [water_pts], 175)
        cv2.fillPoly(nir, [water_pts], 25)

        rgb_stack = np.stack([r, g, b], axis=0)
        filename = f"scene_water_inundation_{step+1}_{date_str}.tif"
        save_geotiff(filename, rgb_stack, nir, bounds)


def generate_scenario_4_airport_transport():
    """
    Scenario 4: Airport Runway & Logistics Transport Expansion
    Location: Sector Airfield Delta (Lat: 12.9716, Lon: 77.5946)
    """
    bounds = (77.5850, 12.9600, 77.6050, 12.9800)
    width, height = 512, 512
    dates = ["2025-01-05", "2025-04-22", "2025-07-19", "2025-11-15"]

    for step, date_str in enumerate(dates):
        # Arid flat airfield terrain
        r = np.random.randint(160, 195, (height, width), dtype=np.uint8)
        g = np.random.randint(155, 185, (height, width), dtype=np.uint8)
        b = np.random.randint(130, 160, (height, width), dtype=np.uint8)
        nir = np.random.randint(140, 170, (height, width), dtype=np.uint8)

        # Primary Runway 1 (Always present)
        cv2.line(r, (80, 50), (80, 460), 60, 24)
        cv2.line(g, (80, 50), (80, 460), 60, 24)
        cv2.line(b, (80, 50), (80, 460), 65, 24)
        cv2.line(nir, (80, 50), (80, 460), 50, 24)

        # Secondary Runway 2 Expansion (x: 280, y: 50-460)
        if step >= 1:
            # T2: Ground leveling
            cv2.line(r, (280, 50), (280, 460), 190, 30)
            cv2.line(g, (280, 50), (280, 460), 180, 30)
            cv2.line(b, (280, 50), (280, 460), 140, 30)
        if step >= 2:
            # T3 (Onset T*): Paved asphalt runway & taxiways
            cv2.line(r, (280, 50), (280, 460), 60, 24)
            cv2.line(g, (280, 50), (280, 460), 60, 24)
            cv2.line(b, (280, 50), (280, 460), 65, 24)
            cv2.line(nir, (280, 50), (280, 460), 50, 24)
            # Connecting taxiway
            cv2.line(r, (80, 250), (280, 250), 60, 14)
            cv2.line(g, (80, 250), (280, 250), 60, 14)
            cv2.line(b, (80, 250), (280, 250), 65, 14)
            cv2.line(nir, (80, 250), (280, 250), 50, 14)
        if step >= 3:
            # T4: Aircraft parked on apron and logistics warehouses (x: 360-460, y: 150-350)
            cv2.line(r, (280, 50), (280, 460), 60, 24)
            cv2.line(g, (280, 50), (280, 460), 60, 24)
            cv2.line(b, (280, 50), (280, 460), 65, 24)
            cv2.line(nir, (280, 50), (280, 460), 50, 24)
            # Aircraft symbols (small white crosses)
            for ax, ay in [(180, 220), (180, 280), (330, 200), (330, 260), (330, 320)]:
                cv2.drawMarker(r, (ax, ay), 250, cv2.MARKER_CROSS, 20, 4)
                cv2.drawMarker(g, (ax, ay), 250, cv2.MARKER_CROSS, 20, 4)
                cv2.drawMarker(b, (ax, ay), 255, cv2.MARKER_CROSS, 20, 4)
                cv2.drawMarker(nir, (ax, ay), 230, cv2.MARKER_CROSS, 20, 4)

        rgb_stack = np.stack([r, g, b], axis=0)
        filename = f"scene_airfield_transport_{step+1}_{date_str}.tif"
        save_geotiff(filename, rgb_stack, nir, bounds)


def generate_all_scenes():
    print("Generating GEO-SENTINEL Multi-Temporal Multi-Spectral GeoTIFF Dataset...")
    generate_scenario_1_urban_construction()
    generate_scenario_2_deforestation()
    generate_scenario_3_water_flood()
    generate_scenario_4_airport_transport()
    print("Successfully generated all 16 multi-temporal scenes!")


if __name__ == "__main__":
    generate_all_scenes()
