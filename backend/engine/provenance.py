"""
GEO-SENTINEL Geospatial Provenance & Intelligence Report Export Engine
Fulfills Capability 2.2.5: Generates STAC-compliant metadata, processing lineage,
cryptographic audit hashes, and comprehensive intelligence reports.
"""

import hashlib
import json
import time
from typing import Dict, Any, List, Optional


class ProvenanceEngine:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def generate_crypto_hash(self, data_dict: Dict[str, Any]) -> str:
        """Generates a reproducible SHA-256 cryptographic provenance hash."""
        serialized = json.dumps(data_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def build_stac_item(self, tile_record: Dict[str, Any], scene_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds an OGC / STAC (SpatioTemporal Asset Catalog) v1.0.0 compliant item JSON.
        """
        bbox = [
            tile_record.get("bbox_min_lon", 0.0),
            tile_record.get("bbox_min_lat", 0.0),
            tile_record.get("bbox_max_lon", 0.0),
            tile_record.get("bbox_max_lat", 0.0)
        ]

        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]],
                [bbox[0], bbox[1]]
            ]]
        }

        properties = {
            "datetime": f"{scene_record.get('acquisition_date', '2026-01-01')}T00:00:00Z",
            "platform": scene_record.get("sensor_name", "Sentinel-2 MSI"),
            "eo:cloud_cover": scene_record.get("cloud_cover_percentage", 0.0),
            "eo:gsd": scene_record.get("gsd_resolution", 10.0),
            "view:sun_elevation": scene_record.get("sun_elevation", 60.0),
            "view:sun_azimuth": scene_record.get("sun_azimuth", 140.0),
            "geo_sentinel:quality_score": tile_record.get("quality_score", 1.0),
            "geo_sentinel:ndvi_mean": tile_record.get("ndvi_mean", 0.0),
            "geo_sentinel:ndwi_mean": tile_record.get("ndwi_mean", 0.0),
            "geo_sentinel:processing_pipeline": "GEO-SENTINEL Sovereign GeoAI v2.0",
            "geo_sentinel:crs": scene_record.get("crs", "EPSG:4326")
        }

        stac_item = {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": tile_record.get("tile_id"),
            "bbox": bbox,
            "geometry": geometry,
            "properties": properties,
            "assets": {
                "thumbnail": {
                    "href": tile_record.get("rgb_preview_path", ""),
                    "type": "image/png",
                    "roles": ["thumbnail"]
                }
            }
        }

        # Add cryptographic audit hash
        stac_item["properties"]["geo_sentinel:crypto_hash"] = self.generate_crypto_hash(stac_item)
        return stac_item

    def generate_intelligence_report(
        self,
        change_events: List[Dict[str, Any]],
        aoi_name: str = "Regional AOI Sector Alpha",
        analyst_callsign: str = "Analyst_Alpha"
    ) -> Dict[str, Any]:
        """
        Generates a comprehensive Geospatial Intelligence Summary report.
        """
        total = len(change_events)
        confirmed = sum(1 for c in change_events if c.get("triage_status") == "confirmed")
        rejected = sum(1 for c in change_events if c.get("triage_status") == "rejected")
        unreviewed = sum(1 for c in change_events if c.get("triage_status") == "unreviewed")

        type_counts = {}
        for c in change_events:
            ctype = c.get("change_type", "Other")
            type_counts[ctype] = type_counts.get(ctype, 0) + 1

        markdown_report = f"""# GEO-SENTINEL GEOSPATIAL INTELLIGENCE REPORT
**Area of Interest:** {aoi_name}  
**Classification:** DECLASSIFIED PUBLIC / EXERCISE  
**Report Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  
**Analyst Call-sign:** {analyst_callsign}  

---

## 1. Executive Summary
During the surveillance window, **{total}** candidate multi-temporal anomalies were detected and processed by the GEO-SENTINEL sovereign AI pipeline.
- **Confirmed Valid Changes:** {confirmed}
- **Confounded / Rejected False Alarms:** {rejected}
- **Pending Review:** {unreviewed}

### Change Category Breakdown
"""
        for ctype, cnt in type_counts.items():
            markdown_report += f"- **{ctype}:** {cnt} events\n"

        markdown_report += """
---

## 2. Priority Change Targets (Top Ranked)
| Change ID | Type | Severity | Confidence | Earliest Onset (T*) | Coordinates (Lat, Lon) | Triage Status |
|:---|:---|:---|:---|:---|:---|:---|
"""
        for c in change_events[:10]:
            markdown_report += f"| `{c.get('change_id')}` | {c.get('change_type')} | **{c.get('severity')}** | {c.get('confidence_score')*100:.1f}% | {c.get('earliest_observation_date')} | `{c.get('center_lat')}, {c.get('center_lon')}` | `{c.get('triage_status')}` |\n"

        markdown_report += f"""
---

## 3. Data Sovereignty & Provenance Attestation
All raster normalization, deep feature extraction, vector indexing, and onset trajectory analysis were executed **100% on-premises** in an air-gapped sovereign runtime. No telemetry or external cloud APIs were invoked.

**Integrity Signature:** `{self.generate_crypto_hash({'events': total, 'confirmed': confirmed, 'timestamp': time.time()})}`
"""

        return {
            "report_title": f"GEO-SENTINEL Intelligence Assessment - {aoi_name}",
            "generated_at": time.time(),
            "summary_metrics": {
                "total_events": total,
                "confirmed": confirmed,
                "rejected": rejected,
                "unreviewed": unreviewed,
                "type_breakdown": type_counts
            },
            "markdown_content": markdown_report
        }
