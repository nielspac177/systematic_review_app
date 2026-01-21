"""Session and project management for systematic review application."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
import shutil

from .models import (
    Project, Study, ScreeningDecision, ExtractionField,
    StudyExtraction, PRISMACounts, ReviewCriteria, InclusionCriteria,
    ScreeningPhase, ExclusionCategory
)
from ..llm.cost_tracker import CostTracker


class SessionManager:
    """Manage systematic review projects and their data."""

    def __init__(self, base_path: Path | str):
        """
        Initialize session manager.

        Args:
            base_path: Base directory for storing all projects
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_project_path(self, project_id: str) -> Path:
        """Get the directory path for a project."""
        return self.base_path / project_id

    def _get_db_path(self, project_id: str) -> Path:
        """Get the database path for a project."""
        return self._get_project_path(project_id) / "project.db"

    def _init_database(self, project_id: str) -> None:
        """Initialize SQLite database for a project."""
        db_path = self._get_db_path(project_id)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                research_question TEXT NOT NULL,
                review_type TEXT DEFAULT 'standard',
                criteria_json TEXT,
                llm_provider TEXT,
                llm_model TEXT,
                budget_limit REAL,
                storage_path TEXT NOT NULL,
                extraction_fields_json TEXT,
                prisma_counts_json TEXT,
                current_phase TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Studies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS studies (
                id TEXT PRIMARY KEY,
                pmid TEXT,
                doi TEXT,
                title TEXT NOT NULL,
                abstract TEXT,
                authors TEXT,
                year INTEGER,
                journal TEXT,
                pdf_path TEXT,
                pdf_text TEXT,
                source_database TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Screening decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screening_decisions (
                id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                reason_category TEXT NOT NULL,
                confidence REAL NOT NULL,
                criteria_evaluation_json TEXT,
                created_at TEXT NOT NULL,
                feedback_reviewed INTEGER DEFAULT 0,
                feedback_reconsider INTEGER,
                feedback_rationale TEXT,
                feedback_new_confidence REAL,
                feedback_final_decision TEXT,
                FOREIGN KEY (study_id) REFERENCES studies(id)
            )
        """)

        # Extractions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extractions (
                id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                extractions_json TEXT NOT NULL,
                extraction_quality_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (study_id) REFERENCES studies(id)
            )
        """)

        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                study_id TEXT,
                operation TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                decision TEXT,
                confidence REAL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost REAL NOT NULL,
                model TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        # Cost tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cost_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost REAL NOT NULL,
                study_id TEXT,
                model TEXT,
                notes TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_studies_pmid ON studies(pmid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_studies_doi ON studies(doi)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_study ON screening_decisions(study_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_phase ON screening_decisions(phase)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_extractions_study ON extractions(study_id)")

        conn.commit()
        conn.close()

    def create_project(
        self,
        name: str,
        research_question: str,
        storage_path: Optional[str] = None,
        review_type: str = "standard"
    ) -> Project:
        """
        Create a new systematic review project.

        Args:
            name: Project name
            research_question: The research question
            storage_path: Optional custom storage path
            review_type: Type of review (standard, rapid, scoping)

        Returns:
            Created Project object
        """
        project = Project(
            name=name,
            research_question=research_question,
            storage_path=storage_path or str(self.base_path),
            review_type=review_type,
        )

        # Create project directory
        project_path = self._get_project_path(project.id)
        project_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (project_path / "pdfs").mkdir(exist_ok=True)
        (project_path / "exports").mkdir(exist_ok=True)

        # Initialize database
        self._init_database(project.id)

        # Save project metadata
        self._save_project(project)

        return project

    def _save_project(self, project: Project) -> None:
        """Save project metadata to database."""
        conn = sqlite3.connect(self._get_db_path(project.id))
        cursor = conn.cursor()

        project.updated_at = datetime.now()

        cursor.execute("""
            INSERT OR REPLACE INTO project (
                id, name, research_question, review_type, criteria_json,
                llm_provider, llm_model, budget_limit, storage_path,
                extraction_fields_json, prisma_counts_json, current_phase,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project.id,
            project.name,
            project.research_question,
            project.review_type.value if hasattr(project.review_type, 'value') else project.review_type,
            project.criteria.model_dump_json() if project.criteria else None,
            project.llm_provider,
            project.llm_model,
            project.budget_limit,
            project.storage_path,
            json.dumps([f.model_dump() for f in project.extraction_fields]),
            project.prisma_counts.model_dump_json(),
            project.current_phase,
            project.created_at.isoformat(),
            project.updated_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    def load_project(self, project_id: str) -> Optional[Project]:
        """
        Load a project by ID.

        Args:
            project_id: Project identifier

        Returns:
            Project object or None if not found
        """
        db_path = self._get_db_path(project_id)
        if not db_path.exists():
            return None

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM project WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Parse JSON fields
        criteria = None
        if row["criteria_json"]:
            criteria = ReviewCriteria.model_validate_json(row["criteria_json"])

        extraction_fields = []
        if row["extraction_fields_json"]:
            fields_data = json.loads(row["extraction_fields_json"])
            extraction_fields = [ExtractionField.model_validate(f) for f in fields_data]

        prisma_counts = PRISMACounts()
        if row["prisma_counts_json"]:
            prisma_counts = PRISMACounts.model_validate_json(row["prisma_counts_json"])

        return Project(
            id=row["id"],
            name=row["name"],
            research_question=row["research_question"],
            review_type=row["review_type"],
            criteria=criteria,
            llm_provider=row["llm_provider"],
            llm_model=row["llm_model"],
            budget_limit=row["budget_limit"],
            storage_path=row["storage_path"],
            extraction_fields=extraction_fields,
            prisma_counts=prisma_counts,
            current_phase=row["current_phase"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_project(self, project: Project) -> None:
        """Save/update a project."""
        self._save_project(project)

    def list_projects(self) -> list[dict]:
        """
        List all projects with basic metadata.

        Returns:
            List of project metadata dictionaries
        """
        projects = []

        for project_dir in self.base_path.iterdir():
            if project_dir.is_dir():
                db_path = project_dir / "project.db"
                if db_path.exists():
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id, name, research_question, review_type, "
                            "created_at, updated_at, current_phase FROM project"
                        )
                        row = cursor.fetchone()
                        conn.close()

                        if row:
                            projects.append({
                                "id": row["id"],
                                "name": row["name"],
                                "research_question": row["research_question"],
                                "review_type": row["review_type"],
                                "created_at": row["created_at"],
                                "updated_at": row["updated_at"],
                                "current_phase": row["current_phase"],
                            })
                    except Exception:
                        pass  # Skip corrupted projects

        # Sort by updated_at descending
        projects.sort(key=lambda p: p["updated_at"], reverse=True)
        return projects

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project and all its data.

        Args:
            project_id: Project identifier

        Returns:
            True if deleted, False if not found
        """
        project_path = self._get_project_path(project_id)
        if project_path.exists():
            shutil.rmtree(project_path)
            return True
        return False

    # =========================================================================
    # STUDY MANAGEMENT
    # =========================================================================

    def add_studies(self, project_id: str, studies: list[Study]) -> int:
        """
        Add studies to a project.

        Args:
            project_id: Project identifier
            studies: List of Study objects

        Returns:
            Number of studies added
        """
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        count = 0
        for study in studies:
            try:
                cursor.execute("""
                    INSERT INTO studies (
                        id, pmid, doi, title, abstract, authors, year,
                        journal, pdf_path, pdf_text, source_database, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    study.id,
                    study.pmid,
                    study.doi,
                    study.title,
                    study.abstract,
                    study.authors,
                    study.year,
                    study.journal,
                    study.pdf_path,
                    study.pdf_text,
                    study.source_database,
                    study.created_at.isoformat(),
                ))
                count += 1
            except sqlite3.IntegrityError:
                pass  # Skip duplicates

        conn.commit()
        conn.close()
        return count

    def get_studies(self, project_id: str) -> list[Study]:
        """Get all studies for a project."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM studies")
        rows = cursor.fetchall()
        conn.close()

        studies = []
        for row in rows:
            studies.append(Study(
                id=row["id"],
                pmid=row["pmid"],
                doi=row["doi"],
                title=row["title"],
                abstract=row["abstract"],
                authors=row["authors"],
                year=row["year"],
                journal=row["journal"],
                pdf_path=row["pdf_path"],
                pdf_text=row["pdf_text"],
                source_database=row["source_database"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ))

        return studies

    def get_study(self, project_id: str, study_id: str) -> Optional[Study]:
        """Get a single study by ID."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM studies WHERE id = ?", (study_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return Study(
            id=row["id"],
            pmid=row["pmid"],
            doi=row["doi"],
            title=row["title"],
            abstract=row["abstract"],
            authors=row["authors"],
            year=row["year"],
            journal=row["journal"],
            pdf_path=row["pdf_path"],
            pdf_text=row["pdf_text"],
            source_database=row["source_database"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def update_study(self, project_id: str, study: Study) -> None:
        """Update a study."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE studies SET
                pmid = ?, doi = ?, title = ?, abstract = ?, authors = ?,
                year = ?, journal = ?, pdf_path = ?, pdf_text = ?, source_database = ?
            WHERE id = ?
        """, (
            study.pmid, study.doi, study.title, study.abstract, study.authors,
            study.year, study.journal, study.pdf_path, study.pdf_text,
            study.source_database, study.id
        ))

        conn.commit()
        conn.close()

    # =========================================================================
    # SCREENING DECISIONS
    # =========================================================================

    def save_screening_decision(
        self, project_id: str, decision: ScreeningDecision
    ) -> None:
        """Save a screening decision."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO screening_decisions (
                id, study_id, phase, decision, reason, reason_category,
                confidence, criteria_evaluation_json, created_at,
                feedback_reviewed, feedback_reconsider, feedback_rationale,
                feedback_new_confidence, feedback_final_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision.id,
            decision.study_id,
            decision.phase.value if hasattr(decision.phase, 'value') else decision.phase,
            decision.decision,
            decision.reason,
            decision.reason_category.value if hasattr(decision.reason_category, 'value') else decision.reason_category,
            decision.confidence,
            json.dumps(decision.criteria_evaluation) if decision.criteria_evaluation else None,
            decision.created_at.isoformat(),
            1 if decision.feedback_reviewed else 0,
            1 if decision.feedback_reconsider else (0 if decision.feedback_reconsider is False else None),
            decision.feedback_rationale,
            decision.feedback_new_confidence,
            decision.feedback_final_decision,
        ))

        conn.commit()
        conn.close()

    def get_screening_decisions(
        self,
        project_id: str,
        phase: Optional[ScreeningPhase] = None,
        study_id: Optional[str] = None
    ) -> list[ScreeningDecision]:
        """Get screening decisions with optional filters."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM screening_decisions WHERE 1=1"
        params = []

        if phase:
            query += " AND phase = ?"
            params.append(phase.value if hasattr(phase, 'value') else phase)

        if study_id:
            query += " AND study_id = ?"
            params.append(study_id)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        decisions = []
        for row in rows:
            decisions.append(ScreeningDecision(
                id=row["id"],
                study_id=row["study_id"],
                phase=ScreeningPhase(row["phase"]),
                decision=row["decision"],
                reason=row["reason"],
                reason_category=ExclusionCategory(row["reason_category"]),
                confidence=row["confidence"],
                criteria_evaluation=json.loads(row["criteria_evaluation_json"]) if row["criteria_evaluation_json"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                feedback_reviewed=bool(row["feedback_reviewed"]),
                feedback_reconsider=bool(row["feedback_reconsider"]) if row["feedback_reconsider"] is not None else None,
                feedback_rationale=row["feedback_rationale"],
                feedback_new_confidence=row["feedback_new_confidence"],
                feedback_final_decision=row["feedback_final_decision"],
            ))

        return decisions

    def get_low_confidence_exclusions(
        self, project_id: str, threshold: float = 0.8
    ) -> list[ScreeningDecision]:
        """Get excluded studies with confidence below threshold."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM screening_decisions
            WHERE decision = 'excluded'
            AND confidence < ?
            AND feedback_reviewed = 0
        """, (threshold,))

        rows = cursor.fetchall()
        conn.close()

        return [ScreeningDecision(
            id=row["id"],
            study_id=row["study_id"],
            phase=ScreeningPhase(row["phase"]),
            decision=row["decision"],
            reason=row["reason"],
            reason_category=ExclusionCategory(row["reason_category"]),
            confidence=row["confidence"],
            criteria_evaluation=json.loads(row["criteria_evaluation_json"]) if row["criteria_evaluation_json"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            feedback_reviewed=bool(row["feedback_reviewed"]),
        ) for row in rows]

    # =========================================================================
    # DATA EXTRACTION
    # =========================================================================

    def save_extraction(self, project_id: str, extraction: StudyExtraction) -> None:
        """Save study extraction data."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        extraction.updated_at = datetime.now()

        # Serialize extractions
        extractions_dict = {
            k: v.model_dump() for k, v in extraction.extractions.items()
        }

        cursor.execute("""
            INSERT OR REPLACE INTO extractions (
                id, study_id, extractions_json, extraction_quality_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            extraction.id,
            extraction.study_id,
            json.dumps(extractions_dict),
            json.dumps(extraction.extraction_quality) if extraction.extraction_quality else None,
            extraction.created_at.isoformat(),
            extraction.updated_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    def get_extractions(self, project_id: str) -> list[StudyExtraction]:
        """Get all extractions for a project."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM extractions")
        rows = cursor.fetchall()
        conn.close()

        from .models import ExtractedValue

        extractions = []
        for row in rows:
            extractions_dict = json.loads(row["extractions_json"])
            parsed_extractions = {
                k: ExtractedValue.model_validate(v) for k, v in extractions_dict.items()
            }

            extractions.append(StudyExtraction(
                id=row["id"],
                study_id=row["study_id"],
                extractions=parsed_extractions,
                extraction_quality=json.loads(row["extraction_quality_json"]) if row["extraction_quality_json"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            ))

        return extractions

    # =========================================================================
    # COST TRACKING
    # =========================================================================

    def save_cost_tracker(self, project_id: str, cost_tracker: CostTracker) -> None:
        """Save cost tracker state to database."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        # Clear existing entries
        cursor.execute("DELETE FROM cost_tracking WHERE project_id = ?", (project_id,))

        # Insert all entries
        for entry in cost_tracker.entries:
            cursor.execute("""
                INSERT INTO cost_tracking (
                    project_id, operation, input_tokens, output_tokens,
                    cost, study_id, model, notes, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id,
                entry.operation.value,
                entry.input_tokens,
                entry.output_tokens,
                entry.cost,
                entry.study_id,
                entry.model,
                entry.notes,
                entry.timestamp.isoformat(),
            ))

        conn.commit()
        conn.close()

    def load_cost_tracker(self, project_id: str) -> CostTracker:
        """Load cost tracker state from database."""
        project = self.load_project(project_id)
        tracker = CostTracker(budget_limit=project.budget_limit if project else None)

        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM cost_tracking WHERE project_id = ? ORDER BY timestamp",
            (project_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        from ..llm.cost_tracker import CostEntry, OperationType

        for row in rows:
            entry = CostEntry(
                operation=OperationType(row["operation"]),
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                cost=row["cost"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                study_id=row["study_id"],
                model=row["model"] or "",
                notes=row["notes"] or "",
            )
            tracker.entries.append(entry)

        return tracker
