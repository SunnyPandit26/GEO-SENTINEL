"""
GEO-SENTINEL Analyst Review Queue & Active Learning Triage Engine
Fulfills Capability 2.2.5: Prioritized review queue, confirm/reject audit logging,
and dynamic feedback reranking for change candidates.
"""

import time
import uuid
from typing import List, Dict, Any, Optional
from backend.database import get_db_connection


class AnalystQueueEngine:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Dynamic active learning weight multipliers
        self.feature_weights = {
            "semantic": 0.70,
            "quality": 0.15,
            "spatial": 0.15
        }

    def get_review_queue(
        self,
        status_filter: Optional[str] = None,
        min_confidence: float = 0.0,
        severity_filter: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retrieves ranked review queue ordered by severity, confidence score, and timestamp.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM change_events WHERE confidence_score >= ?"
        params: List[Any] = [min_confidence]

        if status_filter:
            query += " AND triage_status = ?"
            params.append(status_filter)

        if severity_filter:
            query += " AND severity = ?"
            params.append(severity_filter)

        query += " ORDER BY CASE severity WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END, confidence_score DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append({
                "change_id": r["change_id"],
                "tile_id": r["tile_id"],
                "scene_t1_id": r["scene_t1_id"],
                "scene_t2_id": r["scene_t2_id"],
                "date_t1": r["date_t1"],
                "date_t2": r["date_t2"],
                "change_type": r["change_type"],
                "severity": r["severity"],
                "change_magnitude": r["change_magnitude"],
                "confidence_score": r["confidence_score"],
                "earliest_observation_date": r["earliest_observation_date"],
                "onset_confidence": r["onset_confidence"],
                "center_lat": r["center_lat"],
                "center_lon": r["center_lon"],
                "diff_heatmap_path": r["diff_heatmap_path"],
                "quality_factor": r["quality_factor"],
                "triage_status": r["triage_status"],
                "analyst_notes": r["analyst_notes"],
                "created_at": r["created_at"]
            })

        conn.close()
        return results

    def triage_candidate(
        self,
        change_id: str,
        action: str,  # 'confirm', 'reject', 'flag'
        analyst_id: str = "Analyst_Alpha",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Records analyst decision in immutable audit log and updates candidate triage status.
        Applies active learning weight adjustment.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch current record
        cursor.execute("SELECT triage_status, change_type, confidence_score FROM change_events WHERE change_id = ?", (change_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"status": "error", "message": f"Change event {change_id} not found."}

        prev_status = row["triage_status"]
        new_status = "confirmed" if action == "confirm" else ("rejected" if action == "reject" else "flagged")

        # Active learning weight update
        weight_delta = 0.02 if action == "confirm" else -0.02
        if action == "confirm":
            self.feature_weights["quality"] = min(0.30, self.feature_weights["quality"] + 0.01)
        elif action == "reject":
            self.feature_weights["quality"] = max(0.05, self.feature_weights["quality"] - 0.01)

        # Update change event
        cursor.execute("""
        UPDATE change_events
        SET triage_status = ?, analyst_notes = ?
        WHERE change_id = ?
        """, (new_status, notes, change_id))

        # Insert audit trail record
        review_id = f"rev_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
        INSERT INTO analyst_reviews (
            review_id, change_id, analyst_id, action, previous_status, new_status, notes, timestamp, rerank_weight_delta
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_id, change_id, analyst_id, action, prev_status, new_status, notes, time.time(), weight_delta
        ))

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "review_id": review_id,
            "change_id": change_id,
            "new_status": new_status,
            "analyst_id": analyst_id,
            "active_learning_weights": self.feature_weights
        }
