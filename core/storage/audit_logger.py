"""Audit logging for systematic review LLM operations."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
import csv

from .models import AuditEntry


class AuditLogger:
    """Log all LLM calls for transparency and reproducibility."""

    def __init__(self, db_path: Path | str):
        """
        Initialize audit logger.

        Args:
            db_path: Path to the project's SQLite database
        """
        self.db_path = Path(db_path)
        self.entries: list[AuditEntry] = []

    def log_llm_call(
        self,
        project_id: str,
        operation: str,
        prompt: str,
        response: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        model: str,
        study_id: Optional[str] = None,
        decision: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> AuditEntry:
        """
        Log an LLM call with all details.

        Args:
            project_id: Project identifier
            operation: Type of operation (e.g., 'title_abstract_screening')
            prompt: The prompt sent to the LLM
            response: The LLM's response
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Cost of the call in USD
            model: Model used
            study_id: Optional study identifier
            decision: Optional decision made
            confidence: Optional confidence score

        Returns:
            The created AuditEntry
        """
        entry = AuditEntry(
            project_id=project_id,
            study_id=study_id,
            operation=operation,
            prompt=prompt,
            response=response,
            decision=decision,
            confidence=confidence,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            model=model,
        )

        # Save to memory
        self.entries.append(entry)

        # Save to database
        self._save_entry(entry)

        return entry

    def _save_entry(self, entry: AuditEntry) -> None:
        """Save an entry to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO audit_log (
                id, project_id, study_id, operation, prompt, response,
                decision, confidence, input_tokens, output_tokens,
                cost, model, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id,
            entry.project_id,
            entry.study_id,
            entry.operation,
            entry.prompt,
            entry.response,
            entry.decision,
            entry.confidence,
            entry.input_tokens,
            entry.output_tokens,
            entry.cost,
            entry.model,
            entry.timestamp.isoformat(),
        ))

        conn.commit()
        conn.close()

    def get_entries(
        self,
        project_id: Optional[str] = None,
        study_id: Optional[str] = None,
        operation: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[AuditEntry]:
        """
        Retrieve audit entries with optional filters.

        Args:
            project_id: Filter by project
            study_id: Filter by study
            operation: Filter by operation type
            limit: Maximum number of entries to return

        Returns:
            List of matching AuditEntry objects
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        if study_id:
            query += " AND study_id = ?"
            params.append(study_id)

        if operation:
            query += " AND operation = ?"
            params.append(operation)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        entries = []
        for row in rows:
            entries.append(AuditEntry(
                id=row["id"],
                project_id=row["project_id"],
                study_id=row["study_id"],
                operation=row["operation"],
                prompt=row["prompt"],
                response=row["response"],
                decision=row["decision"],
                confidence=row["confidence"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                cost=row["cost"],
                model=row["model"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            ))

        return entries

    def export_audit_trail(
        self,
        output_path: str | Path,
        project_id: Optional[str] = None,
        format: str = "json"
    ) -> str:
        """
        Export audit trail to a file.

        Args:
            output_path: Path to output file
            project_id: Optional project filter
            format: Export format ('json' or 'csv')

        Returns:
            Path to exported file
        """
        output_path = Path(output_path)
        entries = self.get_entries(project_id=project_id)

        if format == "json":
            return self._export_json(entries, output_path)
        elif format == "csv":
            return self._export_csv(entries, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_json(self, entries: list[AuditEntry], output_path: Path) -> str:
        """Export entries to JSON file."""
        data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_entries": len(entries),
            "total_cost": sum(e.cost for e in entries),
            "entries": [
                {
                    "id": e.id,
                    "project_id": e.project_id,
                    "study_id": e.study_id,
                    "operation": e.operation,
                    "prompt": e.prompt,
                    "response": e.response,
                    "decision": e.decision,
                    "confidence": e.confidence,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "cost": e.cost,
                    "model": e.model,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in entries
            ]
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return str(output_path)

    def _export_csv(self, entries: list[AuditEntry], output_path: Path) -> str:
        """Export entries to CSV file."""
        fieldnames = [
            "id", "project_id", "study_id", "operation", "decision",
            "confidence", "input_tokens", "output_tokens", "cost",
            "model", "timestamp", "prompt_preview", "response_preview"
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for e in entries:
                writer.writerow({
                    "id": e.id,
                    "project_id": e.project_id,
                    "study_id": e.study_id,
                    "operation": e.operation,
                    "decision": e.decision,
                    "confidence": e.confidence,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "cost": e.cost,
                    "model": e.model,
                    "timestamp": e.timestamp.isoformat(),
                    "prompt_preview": e.prompt[:200] + "..." if len(e.prompt) > 200 else e.prompt,
                    "response_preview": e.response[:200] + "..." if len(e.response) > 200 else e.response,
                })

        return str(output_path)

    def get_summary(self, project_id: Optional[str] = None) -> dict:
        """
        Get summary statistics for audit log.

        Args:
            project_id: Optional project filter

        Returns:
            Dictionary with summary statistics
        """
        entries = self.get_entries(project_id=project_id)

        summary = {
            "total_calls": len(entries),
            "total_cost": sum(e.cost for e in entries),
            "total_input_tokens": sum(e.input_tokens for e in entries),
            "total_output_tokens": sum(e.output_tokens for e in entries),
            "by_operation": {},
            "by_model": {},
        }

        for entry in entries:
            # By operation
            if entry.operation not in summary["by_operation"]:
                summary["by_operation"][entry.operation] = {
                    "count": 0,
                    "cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            summary["by_operation"][entry.operation]["count"] += 1
            summary["by_operation"][entry.operation]["cost"] += entry.cost
            summary["by_operation"][entry.operation]["input_tokens"] += entry.input_tokens
            summary["by_operation"][entry.operation]["output_tokens"] += entry.output_tokens

            # By model
            if entry.model not in summary["by_model"]:
                summary["by_model"][entry.model] = {
                    "count": 0,
                    "cost": 0.0,
                }
            summary["by_model"][entry.model]["count"] += 1
            summary["by_model"][entry.model]["cost"] += entry.cost

        return summary

    def clear(self, project_id: Optional[str] = None) -> int:
        """
        Clear audit log entries.

        Args:
            project_id: Optional project filter (if None, clears all)

        Returns:
            Number of entries deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if project_id:
            cursor.execute("DELETE FROM audit_log WHERE project_id = ?", (project_id,))
        else:
            cursor.execute("DELETE FROM audit_log")

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        # Also clear in-memory entries
        if project_id:
            self.entries = [e for e in self.entries if e.project_id != project_id]
        else:
            self.entries.clear()

        return deleted
