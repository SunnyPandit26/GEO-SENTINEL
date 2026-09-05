"""
GEO-SENTINEL Ultra-High-Contrast Multi-Temporal Multi-Spectral GeoTIFF Dataset Generator
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
    base = np.zeros((height, width), dtype=np.float32)
    for scale, weight in [(64, 0.5), (32, 0.25), (16, 0.15), (8, 0.1)]:
        noise = cv2.resize(np.random.randn(height // scale, width // scale).astype(np.float32), (width, height))
        base += noise * weight
    
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

    dates = ["2025-01-10", "2025-04-15", "2025-08-20", "2025-11-25"]

    for step, date_str in enumerate(dates):
        # 1. Base terrain (lush vegetation)
        r = (terrain * 50 + 35).astype(np.uint8)
        g = (terrain * 120 + 100).astype(np.uint8)
        b = (terrain * 40 + 30).astype(np.uint8)
        nir = (terrain * 180 + 70).astype(np.uint8)

        # 2. Draw curved River
        pts = np.array([[60, 0], [130, 150], [210, 300], [250, 512], [310, 512], [270, 300], [190, 150], [120, 0]], np.int32)
        cv2.fillPoly(r, [pts], 20)
        cv2.fillPoly(g, [pts], 75)
        cv2.fillPoly(b, [pts], 175)
        cv2.fillPoly(nir, [pts], 15)  # Water absorbs NIR

        if step == 0:
            # T1: Pristine green meadows, natural forest patches
            cv2.circle(r, (380, 260), 60, 30, -1)
            cv2.circle(g, (380, 260), 60, 150, -1)
            cv2.circle(b, (380, 260), 60, 35, -1)
            cv2.circle(nir, (380, 260), 60, 230, -1)
        elif step == 1:
            # T2 (Onset T*): Massive earthwork clearance, yellow-orange bare soil (x: 240-490, y: 100-450)
            cv2.rectangle(r, (240, 100), (490, 450), 210, -1)
            cv2.rectangle(g, (240, 100), (490, 450), 160, -1)
            cv2.rectangle(b, (240, 100), (490, 450), 90, -1)
            cv2.rectangle(nir, (240, 100), (490, 450), 95, -1)
            # Access dirt tracks
            cv2.line(r, (180, 250), (490, 250), 180, 8)
            cv2.line(g, (180, 250), (490, 250), 130, 8)
            cv2.line(b, (180, 250), (490, 250), 70, 8)
        elif step == 2:
            # T3: Foundation trenches, concrete pads, crane works
            cv2.rectangle(r, (240, 100), (490, 450), 175, -1)
            cv2.rectangle(g, (240, 100), (490, 450), 165, -1)
            cv2.rectangle(b, (240, 100), (490, 450), 155, -1)
            cv2.rectangle(nir, (240, 100), (490, 450), 110, -1)
            for bx, by in [(260, 130), (370, 130), (260, 280), (370, 280)]:
                cv2.rectangle(r, (bx, by), (bx + 85, by + 95), 225, -1)
                cv2.rectangle(g, (bx, by), (bx + 85, by + 95), 225, -1)
                cv2.rectangle(b, (bx, by), (bx + 85, by + 95), 235, -1)
                cv2.rectangle(nir, (bx, by), (bx + 85, by + 95), 140, -1)
        elif step == 3:
            # T4: Fully erected high-rise towers with red/white roofs, black asphalt roads, cars & bridge
            cv2.rectangle(r, (240, 100), (490, 450), 60, -1)
            cv2.rectangle(g, (240, 100), (490, 450), 60, -1)
            cv2.rectangle(b, (240, 100), (490, 450), 65, -1)
            cv2.rectangle(nir, (240, 100), (490, 450), 55, -1)
            # Towers with drop shadows and distinct roofs
            for bx, by in [(260, 130), (370, 130), (260, 280), (370, 280)]:
                # Shadow
                cv2.rectangle(r, (bx + 10, by + 10), (bx + 95, by + 105), 20, -1)
                cv2.rectangle(g, (bx + 10, by + 10), (bx + 95, by + 105), 20, -1)
                cv2.rectangle(b, (bx + 10, by + 10), (bx + 95, by + 105), 25, -1)
                # Roof
                roof_color = (235, 75, 75) if bx == 260 else (245, 245, 250)
                cv2.rectangle(r, (bx, by), (bx + 85, by + 95), roof_color[0], -1)
                cv2.rectangle(g, (bx, by), (bx + 85, by + 95), roof_color[1], -1)
                cv2.rectangle(b, (bx, by), (bx + 85, by + 95), roof_color[2], -1)
                cv2.rectangle(nir, (bx, by), (bx + 85, by + 95), 180, -1)
            # Bridge across river
            cv2.line(r, (150, 250), (300, 250), 190, 14)
            cv2.line(g, (150, 250), (300, 250), 190, 14)
            cv2.line(b, (150, 250), (300, 250), 200, 14)
            cv2.line(nir, (150, 250), (300, 250), 160, 14)

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
        # Deep emerald rainforest canopy
        r = np.random.randint(18, 38, (height, width), dtype=np.uint8)
        g = np.random.randint(95, 145, (height, width), dtype=np.uint8)
        b = np.random.randint(20, 42, (height, width), dtype=np.uint8)
        nir = np.random.randint(200, 250, (height, width), dtype=np.uint8)

        if step == 0:
            # T1: 100% Dense Pristine Forest Canopy
            pass
        elif step == 1:
            # T2: Fishbone logging roads cutting across
            for ly in [120, 200, 280, 360, 440]:
                cv2.line(r, (30, ly), (480, ly), 190, 8)
                cv2.line(g, (30, ly), (480, ly), 140, 8)
                cv2.line(b, (30, ly), (480, ly), 80, 8)
                cv2.line(nir, (30, ly), (480, ly), 75, 8)
        elif step == 2:
            # T3 (Onset T*): Massive Clear-Cut Deforestation Block (x: 100-420, y: 80-420)
            cv2.rectangle(r, (100, 80), (420, 420), 215, -1)
            cv2.rectangle(g, (100, 80), (420, 420), 160, -1)
            cv2.rectangle(b, (100, 80), (420, 420), 85, -1)
            cv2.rectangle(nir, (100, 80), (420, 420), 65, -1)  # Critical drop in NIR
            # Stumps and tire tracks
            for sx in range(120, 400, 30):
                for sy in range(100, 400, 30):
                    cv2.circle(r, (sx, sy), 4, 80, -1)
                    cv2.circle(g, (sx, sy), 4, 50, -1)
                    cv2.circle(b, (sx, sy), 4, 30, -1)
        elif step == 3:
            # T4: Fully Converted Agricultural & Cattle Land (Sharp geometric pastures)
            cv2.rectangle(r, (70, 50), (450, 460), 225, -1)
            cv2.rectangle(g, (70, 50), (450, 460), 185, -1)
            cv2.rectangle(b, (70, 50), (450, 460), 105, -1)
            cv2.rectangle(nir, (70, 50), (450, 460), 90, -1)
            # Farm division grids
            for line_x in [160, 270, 370]:
                cv2.line(r, (line_x, 50), (line_x, 460), 130, 4)
                cv2.line(g, (line_x, 50), (line_x, 460), 100, 4)
                cv2.line(b, (line_x, 50), (line_x, 460), 50, 4)

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
        # Farmland baseline
        r = np.random.randint(150, 190, (height, width), dtype=np.uint8)
        g = np.random.randint(160, 205, (height, width), dtype=np.uint8)
        b = np.random.randint(85, 115, (height, width), dtype=np.uint8)
        nir = np.random.randint(180, 230, (height, width), dtype=np.uint8)

        if step == 0:
            # T1: Narrow dry-season river channel
            pts = np.array([[220, 0], [230, 200], [240, 350], [250, 512], [280, 512], [270, 350], [260, 200], [250, 0]], np.int32)
            cv2.fillPoly(r, [pts], 30)
            cv2.fillPoly(g, [pts], 80)
            cv2.fillPoly(b, [pts], 170)
            cv2.fillPoly(nir, [pts], 20)
        elif step == 1:
            # T2: Swelling river during early monsoon
            pts = np.array([[180, 0], [170, 200], [160, 350], [170, 512], [340, 512], [330, 350], [320, 200], [310, 0]], np.int32)
            cv2.fillPoly(r, [pts], 25)
            cv2.fillPoly(g, [pts], 75)
            cv2.fillPoly(b, [pts], 180)
            cv2.fillPoly(nir, [pts], 15)
        elif step == 2:
            # T3 (Onset T*): Catastrophic flood inundation (Engulfs 80% of entire scene!)
            flood_pts = np.array([[40, 0], [30, 180], [20, 360], [30, 512], [480, 512], [470, 360], [460, 180], [450, 0]], np.int32)
            cv2.fillPoly(r, [flood_pts], 20)
            cv2.fillPoly(g, [flood_pts], 65)
            cv2.fillPoly(b, [flood_pts], 195)
            cv2.fillPoly(nir, [flood_pts], 10)
        elif step == 3:
            # T4: Receding flood mud, saturated sediment & destroyed cropland
            mud_pts = np.array([[120, 0], [110, 200], [100, 350], [110, 512], [390, 512], [380, 350], [370, 200], [360, 0]], np.int32)
            cv2.fillPoly(r, [mud_pts], 120)
            cv2.fillPoly(g, [mud_pts], 110)
            cv2.fillPoly(b, [mud_pts], 70)
            cv2.fillPoly(nir, [mud_pts], 60)

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
        # Arid flat ground
        r = np.random.randint(185, 215, (height, width), dtype=np.uint8)
        g = np.random.randint(175, 205, (height, width), dtype=np.uint8)
        b = np.random.randint(145, 175, (height, width), dtype=np.uint8)
        nir = np.random.randint(130, 160, (height, width), dtype=np.uint8)

        if step == 0:
            # T1: Empty barren ground with single runway on left
            cv2.line(r, (80, 40), (80, 470), 50, 26)
            cv2.line(g, (80, 40), (80, 470), 50, 26)
            cv2.line(b, (80, 40), (80, 470), 55, 26)
            cv2.line(nir, (80, 40), (80, 470), 40, 26)
        elif step == 1:
            # T2: Ground leveling & excavation for secondary parallel runway
            cv2.line(r, (80, 40), (80, 470), 50, 26)
            cv2.line(g, (80, 40), (80, 470), 50, 26)
            cv2.line(b, (80, 40), (80, 470), 55, 26)
            cv2.line(nir, (80, 40), (80, 470), 40, 26)
            # Excavation corridor
            cv2.line(r, (280, 40), (280, 470), 225, 36)
            cv2.line(g, (280, 40), (280, 470), 160, 36)
            cv2.line(b, (280, 40), (280, 470), 80, 36)
        elif step == 2:
            # T3 (Onset T*): Brand new black asphalt parallel runway + taxiway connections
            for rx in [80, 280]:
                cv2.line(r, (rx, 40), (rx, 470), 30, 28)
                cv2.line(g, (rx, 40), (rx, 470), 30, 28)
                cv2.line(b, (rx, 40), (rx, 470), 35, 28)
                cv2.line(nir, (rx, 40), (rx, 470), 25, 28)
                # White centerline stripes
                for my in range(60, 460, 40):
                    cv2.line(r, (rx, my), (rx, my + 20), 255, 4)
                    cv2.line(g, (rx, my), (rx, my + 20), 255, 4)
                    cv2.line(b, (rx, my), (rx, my + 20), 255, 4)
            # Taxiway
            cv2.line(r, (80, 250), (280, 250), 30, 16)
            cv2.line(g, (80, 250), (280, 250), 30, 16)
            cv2.line(b, (80, 250), (280, 250), 35, 16)
        elif step == 3:
            # T4: Fully operational airbase with white hangars, apron & transport planes
            for rx in [80, 280]:
                cv2.line(r, (rx, 40), (rx, 470), 30, 28)
                cv2.line(g, (rx, 40), (rx, 470), 30, 28)
                cv2.line(b, (rx, 40), (rx, 470), 35, 28)
                cv2.line(nir, (rx, 40), (rx, 470), 25, 28)
                for my in range(60, 460, 40):
                    cv2.line(r, (rx, my), (rx, my + 20), 255, 4)
                    cv2.line(g, (rx, my), (rx, my + 20), 255, 4)
                    cv2.line(b, (rx, my), (rx, my + 20), 255, 4)
            # Apron & Hangars (x: 340-480, y: 120-380)
            cv2.rectangle(r, (340, 120), (480, 380), 50, -1)
            cv2.rectangle(g, (340, 120), (480, 380), 50, -1)
            cv2.rectangle(b, (340, 120), (480, 380), 55, -1)
            # Hangars (White rectangles with blue trim)
            for hx, hy in [(360, 140), (420, 140), (360, 280), (420, 280)]:
                cv2.rectangle(r, (hx, hy), (hx + 45, hy + 55), 245, -1)
                cv2.rectangle(g, (hx, hy), (hx + 45, hy + 55), 245, -1)
                cv2.rectangle(b, (hx, hy), (hx + 45, hy + 55), 255, -1)
            # Transport Aircraft (white airplane crosses on apron)
            for ax, ay in [(180, 210), (180, 290), (380, 220), (440, 220)]:
                cv2.drawMarker(r, (ax, ay), 255, cv2.MARKER_CROSS, 26, 5)
                cv2.drawMarker(g, (ax, ay), 255, cv2.MARKER_CROSS, 26, 5)
                cv2.drawMarker(b, (ax, ay), 255, cv2.MARKER_CROSS, 26, 5)
                cv2.drawMarker(nir, (ax, ay), 240, cv2.MARKER_CROSS, 26, 5)

        rgb_stack = np.stack([r, g, b], axis=0)
        filename = f"scene_airfield_transport_{step+1}_{date_str}.tif"
        save_geotiff(filename, rgb_stack, nir, bounds)


def generate_all_scenes():
    print("Generating High-Contrast GEO-SENTINEL Multi-Temporal Multi-Spectral GeoTIFF Dataset...")
    generate_scenario_1_urban_construction()
    generate_scenario_2_deforestation()
    generate_scenario_3_water_flood()
    generate_scenario_4_airport_transport()
    print("Successfully generated all 16 multi-temporal scenes!")


if __name__ == "__main__":
    generate_all_scenes()
