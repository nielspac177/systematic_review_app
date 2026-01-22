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
    ScreeningPhase, ExclusionCategory,
    # Risk of Bias models
    RoBToolType, JudgmentLevel, SignalingQuestion, RoBDomainTemplate,
    RoBTemplate, SignalingQuestionResponse, RoBDomainJudgment,
    StudyRoBAssessment, RoBProjectSettings, RoBAuditEntry
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

        # Search strategies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_strategies (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                research_question TEXT NOT NULL,
                pico_analysis_json TEXT,
                concept_blocks_json TEXT,
                pubmed_strategy TEXT,
                scopus_strategy TEXT,
                wos_strategy TEXT,
                cochrane_strategy TEXT,
                embase_strategy TEXT,
                ovid_strategy TEXT,
                pubmed_history_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Parsed references for deduplication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parsed_references (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                source_file TEXT,
                source_database TEXT,
                title TEXT NOT NULL,
                abstract TEXT,
                authors TEXT,
                year INTEGER,
                journal TEXT,
                doi TEXT,
                pmid TEXT,
                is_duplicate INTEGER DEFAULT 0,
                duplicate_of TEXT,
                duplicate_reason TEXT,
                duplicate_score REAL
            )
        """)

        # Wizard state persistence
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wizard_state (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                current_step INTEGER DEFAULT 1,
                completed_steps_json TEXT,
                research_question TEXT,
                existing_pubmed_strategy TEXT,
                search_strategy_id TEXT,
                selected_databases_json TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        # Risk of Bias Templates (project-specific customizations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rob_templates (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                tool_type TEXT NOT NULL,
                name TEXT NOT NULL,
                version TEXT DEFAULT '1.0',
                description TEXT,
                domains_json TEXT NOT NULL,
                applicable_study_designs_json TEXT,
                overall_judgment_algorithm TEXT,
                is_builtin INTEGER DEFAULT 1,
                is_customized INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Risk of Bias Assessments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rob_assessments (
                id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                template_id TEXT NOT NULL,
                tool_type TEXT NOT NULL,
                detected_study_design TEXT,
                comparison_label TEXT,
                domain_judgments_json TEXT NOT NULL,
                overall_judgment TEXT NOT NULL,
                overall_rationale TEXT,
                ai_cost REAL DEFAULT 0.0,
                ai_model TEXT,
                assessor_id TEXT,
                reviewer_id TEXT,
                assessment_status TEXT DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (study_id) REFERENCES studies(id)
            )
        """)

        # Risk of Bias Project Settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rob_project_settings (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL UNIQUE,
                enabled_tools_json TEXT,
                dual_review_enabled INTEGER DEFAULT 0,
                auto_detect_study_design INTEGER DEFAULT 1,
                require_supporting_quotes INTEGER DEFAULT 1,
                flag_uncertain_threshold REAL DEFAULT 0.7,
                batch_queue_json TEXT,
                batch_status TEXT DEFAULT 'idle',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Risk of Bias Audit Trail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rob_audit (
                id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                study_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                action TEXT NOT NULL,
                domain_id TEXT,
                previous_judgment TEXT,
                new_judgment TEXT,
                user_id TEXT,
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsed_refs_doi ON parsed_references(doi)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsed_refs_title ON parsed_references(title)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_strategies_project ON search_strategies(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rob_assessments_study ON rob_assessments(study_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rob_assessments_project ON rob_assessments(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rob_audit_assessment ON rob_audit(assessment_id)")

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

    # =========================================================================
    # SEARCH STRATEGY MANAGEMENT
    # =========================================================================

    def save_search_strategy(self, project_id: str, strategy) -> None:
        """Save a search strategy to database."""
        from .models import SearchStrategy
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        strategy.updated_at = datetime.now()

        cursor.execute("""
            INSERT OR REPLACE INTO search_strategies (
                id, project_id, research_question, pico_analysis_json,
                concept_blocks_json, pubmed_strategy, scopus_strategy,
                wos_strategy, cochrane_strategy, embase_strategy, ovid_strategy,
                pubmed_history_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy.id,
            strategy.project_id,
            strategy.research_question,
            json.dumps(strategy.pico_analysis) if strategy.pico_analysis else None,
            json.dumps([cb.model_dump() for cb in strategy.concept_blocks]),
            strategy.pubmed_strategy,
            strategy.scopus_strategy,
            strategy.wos_strategy,
            strategy.cochrane_strategy,
            strategy.embase_strategy,
            strategy.ovid_strategy,
            json.dumps(strategy.pubmed_history),
            strategy.created_at.isoformat(),
            strategy.updated_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    def load_search_strategy(self, project_id: str, strategy_id: Optional[str] = None):
        """Load a search strategy from database."""
        from .models import SearchStrategy, ConceptBlock

        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if strategy_id:
            cursor.execute(
                "SELECT * FROM search_strategies WHERE id = ? AND project_id = ?",
                (strategy_id, project_id)
            )
        else:
            # Get the most recent strategy for the project
            cursor.execute(
                "SELECT * FROM search_strategies WHERE project_id = ? ORDER BY updated_at DESC LIMIT 1",
                (project_id,)
            )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        concept_blocks = []
        if row["concept_blocks_json"]:
            blocks_data = json.loads(row["concept_blocks_json"])
            concept_blocks = [ConceptBlock.model_validate(b) for b in blocks_data]

        return SearchStrategy(
            id=row["id"],
            project_id=row["project_id"],
            research_question=row["research_question"],
            pico_analysis=json.loads(row["pico_analysis_json"]) if row["pico_analysis_json"] else None,
            concept_blocks=concept_blocks,
            pubmed_strategy=row["pubmed_strategy"],
            scopus_strategy=row["scopus_strategy"],
            wos_strategy=row["wos_strategy"],
            cochrane_strategy=row["cochrane_strategy"],
            embase_strategy=row["embase_strategy"],
            ovid_strategy=row["ovid_strategy"],
            pubmed_history=json.loads(row["pubmed_history_json"]) if row["pubmed_history_json"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # =========================================================================
    # PARSED REFERENCES MANAGEMENT
    # =========================================================================

    def save_parsed_references(self, project_id: str, references: list) -> int:
        """Save parsed references to database."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        count = 0
        for ref in references:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO parsed_references (
                        id, project_id, source_file, source_database, title,
                        abstract, authors, year, journal, doi, pmid,
                        is_duplicate, duplicate_of, duplicate_reason, duplicate_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ref.id,
                    project_id,
                    ref.source_file,
                    ref.source_database,
                    ref.title,
                    ref.abstract,
                    ref.authors,
                    ref.year,
                    ref.journal,
                    ref.doi,
                    ref.pmid,
                    1 if ref.is_duplicate else 0,
                    ref.duplicate_of,
                    ref.duplicate_reason,
                    ref.duplicate_score,
                ))
                count += 1
            except sqlite3.IntegrityError:
                pass

        conn.commit()
        conn.close()
        return count

    def get_parsed_references(self, project_id: str, include_duplicates: bool = True) -> list:
        """Get parsed references for a project."""
        from .models import ParsedReference

        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if include_duplicates:
            cursor.execute(
                "SELECT * FROM parsed_references WHERE project_id = ?",
                (project_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM parsed_references WHERE project_id = ? AND is_duplicate = 0",
                (project_id,)
            )

        rows = cursor.fetchall()
        conn.close()

        return [ParsedReference(
            id=row["id"],
            source_file=row["source_file"],
            source_database=row["source_database"],
            title=row["title"],
            abstract=row["abstract"],
            authors=row["authors"],
            year=row["year"],
            journal=row["journal"],
            doi=row["doi"],
            pmid=row["pmid"],
            is_duplicate=bool(row["is_duplicate"]),
            duplicate_of=row["duplicate_of"],
            duplicate_reason=row["duplicate_reason"],
            duplicate_score=row["duplicate_score"],
        ) for row in rows]

    def clear_parsed_references(self, project_id: str) -> None:
        """Clear all parsed references for a project."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM parsed_references WHERE project_id = ?", (project_id,))
        conn.commit()
        conn.close()

    # =========================================================================
    # WIZARD STATE MANAGEMENT
    # =========================================================================

    def save_wizard_state(self, project_id: str, state) -> None:
        """Save wizard state to database."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO wizard_state (
                id, project_id, current_step, completed_steps_json,
                research_question, existing_pubmed_strategy,
                search_strategy_id, selected_databases_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state.id,
            state.project_id,
            state.current_step,
            json.dumps(state.completed_steps),
            state.research_question,
            state.existing_pubmed_strategy,
            state.search_strategy.id if state.search_strategy else None,
            json.dumps(state.selected_databases),
            datetime.now().isoformat(),
        ))

        conn.commit()
        conn.close()

    def load_wizard_state(self, project_id: str):
        """Load wizard state from database."""
        from .models import WizardState

        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM wizard_state WHERE project_id = ? ORDER BY updated_at DESC LIMIT 1",
            (project_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Load associated search strategy if exists
        search_strategy = None
        if row["search_strategy_id"]:
            search_strategy = self.load_search_strategy(project_id, row["search_strategy_id"])

        return WizardState(
            id=row["id"],
            project_id=row["project_id"],
            current_step=row["current_step"],
            completed_steps=json.loads(row["completed_steps_json"]) if row["completed_steps_json"] else [],
            research_question=row["research_question"] or "",
            existing_pubmed_strategy=row["existing_pubmed_strategy"],
            search_strategy=search_strategy,
            selected_databases=json.loads(row["selected_databases_json"]) if row["selected_databases_json"] else ["SCOPUS", "WOS"],
        )

    # =========================================================================
    # RISK OF BIAS MANAGEMENT
    # =========================================================================

    def save_rob_template(self, project_id: str, template: RoBTemplate) -> None:
        """Save a RoB template to database."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT OR REPLACE INTO rob_templates (
                id, project_id, tool_type, name, version, description,
                domains_json, applicable_study_designs_json, overall_judgment_algorithm,
                is_builtin, is_customized, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template.id,
            project_id,
            template.tool_type.value,
            template.name,
            template.version,
            template.description,
            json.dumps([d.model_dump() for d in template.domains]),
            json.dumps(template.applicable_study_designs),
            template.overall_judgment_algorithm,
            1 if template.is_builtin else 0,
            1 if template.is_customized else 0,
            now,
            now,
        ))

        conn.commit()
        conn.close()

    def get_rob_template(self, project_id: str, template_id: str) -> Optional[RoBTemplate]:
        """Get a RoB template by ID."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM rob_templates WHERE id = ?", (template_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        domains_data = json.loads(row["domains_json"])
        domains = []
        for d in domains_data:
            # Parse signaling questions
            sq_list = []
            for sq in d.get("signaling_questions", []):
                sq_list.append(SignalingQuestion.model_validate(sq))
            d["signaling_questions"] = sq_list
            domains.append(RoBDomainTemplate.model_validate(d))

        return RoBTemplate(
            id=row["id"],
            tool_type=RoBToolType(row["tool_type"]),
            name=row["name"],
            version=row["version"],
            description=row["description"],
            domains=domains,
            applicable_study_designs=json.loads(row["applicable_study_designs_json"]) if row["applicable_study_designs_json"] else [],
            overall_judgment_algorithm=row["overall_judgment_algorithm"],
            is_builtin=bool(row["is_builtin"]),
            is_customized=bool(row["is_customized"]),
        )

    def get_rob_templates(self, project_id: str, tool_type: Optional[RoBToolType] = None) -> list[RoBTemplate]:
        """Get all RoB templates for a project, optionally filtered by tool type."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if tool_type:
            cursor.execute(
                "SELECT * FROM rob_templates WHERE project_id = ? AND tool_type = ?",
                (project_id, tool_type.value)
            )
        else:
            cursor.execute("SELECT * FROM rob_templates WHERE project_id = ?", (project_id,))

        rows = cursor.fetchall()
        conn.close()

        templates = []
        for row in rows:
            domains_data = json.loads(row["domains_json"])
            domains = []
            for d in domains_data:
                sq_list = []
                for sq in d.get("signaling_questions", []):
                    sq_list.append(SignalingQuestion.model_validate(sq))
                d["signaling_questions"] = sq_list
                domains.append(RoBDomainTemplate.model_validate(d))

            templates.append(RoBTemplate(
                id=row["id"],
                tool_type=RoBToolType(row["tool_type"]),
                name=row["name"],
                version=row["version"],
                description=row["description"],
                domains=domains,
                applicable_study_designs=json.loads(row["applicable_study_designs_json"]) if row["applicable_study_designs_json"] else [],
                overall_judgment_algorithm=row["overall_judgment_algorithm"],
                is_builtin=bool(row["is_builtin"]),
                is_customized=bool(row["is_customized"]),
            ))

        return templates

    def delete_rob_template(self, project_id: str, template_id: str) -> bool:
        """Delete a RoB template."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rob_templates WHERE id = ? AND project_id = ?", (template_id, project_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def save_rob_assessment(self, project_id: str, assessment: StudyRoBAssessment) -> None:
        """Save a RoB assessment to database."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        assessment.updated_at = datetime.now()

        cursor.execute("""
            INSERT OR REPLACE INTO rob_assessments (
                id, study_id, project_id, template_id, tool_type,
                detected_study_design, comparison_label, domain_judgments_json,
                overall_judgment, overall_rationale, ai_cost, ai_model,
                assessor_id, reviewer_id, assessment_status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            assessment.id,
            assessment.study_id,
            project_id,
            assessment.template_id,
            assessment.tool_type.value,
            assessment.detected_study_design,
            assessment.comparison_label,
            json.dumps([j.model_dump() for j in assessment.domain_judgments]),
            assessment.overall_judgment.value,
            assessment.overall_rationale,
            assessment.ai_cost,
            assessment.ai_model,
            assessment.assessor_id,
            assessment.reviewer_id,
            assessment.assessment_status,
            assessment.created_at.isoformat(),
            assessment.updated_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    def get_rob_assessment(self, project_id: str, study_id: str, comparison_label: Optional[str] = None) -> Optional[StudyRoBAssessment]:
        """Get RoB assessment for a study."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if comparison_label:
            cursor.execute(
                "SELECT * FROM rob_assessments WHERE study_id = ? AND project_id = ? AND comparison_label = ?",
                (study_id, project_id, comparison_label)
            )
        else:
            cursor.execute(
                "SELECT * FROM rob_assessments WHERE study_id = ? AND project_id = ?",
                (study_id, project_id)
            )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        judgments_data = json.loads(row["domain_judgments_json"])
        judgments = []
        for j in judgments_data:
            # Parse signaling responses
            sr_list = []
            for sr in j.get("signaling_responses", []):
                sr_list.append(SignalingQuestionResponse.model_validate(sr))
            j["signaling_responses"] = sr_list
            j["judgment"] = JudgmentLevel(j["judgment"])
            if j.get("ai_suggested_judgment"):
                j["ai_suggested_judgment"] = JudgmentLevel(j["ai_suggested_judgment"])
            judgments.append(RoBDomainJudgment.model_validate(j))

        return StudyRoBAssessment(
            id=row["id"],
            study_id=row["study_id"],
            template_id=row["template_id"],
            tool_type=RoBToolType(row["tool_type"]),
            detected_study_design=row["detected_study_design"],
            comparison_label=row["comparison_label"],
            domain_judgments=judgments,
            overall_judgment=JudgmentLevel(row["overall_judgment"]),
            overall_rationale=row["overall_rationale"] or "",
            ai_cost=row["ai_cost"],
            ai_model=row["ai_model"],
            assessor_id=row["assessor_id"],
            reviewer_id=row["reviewer_id"],
            assessment_status=row["assessment_status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_rob_assessments(self, project_id: str) -> list[StudyRoBAssessment]:
        """Get all RoB assessments for a project."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM rob_assessments WHERE project_id = ?", (project_id,))
        rows = cursor.fetchall()
        conn.close()

        assessments = []
        for row in rows:
            judgments_data = json.loads(row["domain_judgments_json"])
            judgments = []
            for j in judgments_data:
                sr_list = []
                for sr in j.get("signaling_responses", []):
                    sr_list.append(SignalingQuestionResponse.model_validate(sr))
                j["signaling_responses"] = sr_list
                j["judgment"] = JudgmentLevel(j["judgment"])
                if j.get("ai_suggested_judgment"):
                    j["ai_suggested_judgment"] = JudgmentLevel(j["ai_suggested_judgment"])
                judgments.append(RoBDomainJudgment.model_validate(j))

            assessments.append(StudyRoBAssessment(
                id=row["id"],
                study_id=row["study_id"],
                template_id=row["template_id"],
                tool_type=RoBToolType(row["tool_type"]),
                detected_study_design=row["detected_study_design"],
                comparison_label=row["comparison_label"],
                domain_judgments=judgments,
                overall_judgment=JudgmentLevel(row["overall_judgment"]),
                overall_rationale=row["overall_rationale"] or "",
                ai_cost=row["ai_cost"],
                ai_model=row["ai_model"],
                assessor_id=row["assessor_id"],
                reviewer_id=row["reviewer_id"],
                assessment_status=row["assessment_status"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            ))

        return assessments

    def delete_rob_assessment(self, project_id: str, assessment_id: str) -> bool:
        """Delete a RoB assessment."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rob_assessments WHERE id = ? AND project_id = ?", (assessment_id, project_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def save_rob_settings(self, project_id: str, settings: RoBProjectSettings) -> None:
        """Save RoB project settings."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        settings.updated_at = datetime.now()

        cursor.execute("""
            INSERT OR REPLACE INTO rob_project_settings (
                id, project_id, enabled_tools_json, dual_review_enabled,
                auto_detect_study_design, require_supporting_quotes,
                flag_uncertain_threshold, batch_queue_json, batch_status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            settings.id,
            settings.project_id,
            json.dumps([t.value for t in settings.enabled_tools]),
            1 if settings.dual_review_enabled else 0,
            1 if settings.auto_detect_study_design else 0,
            1 if settings.require_supporting_quotes else 0,
            settings.flag_uncertain_threshold,
            json.dumps(settings.batch_queue),
            settings.batch_status,
            settings.created_at.isoformat(),
            settings.updated_at.isoformat(),
        ))

        conn.commit()
        conn.close()

    def get_rob_settings(self, project_id: str) -> Optional[RoBProjectSettings]:
        """Get RoB project settings."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM rob_project_settings WHERE project_id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        enabled_tools = []
        if row["enabled_tools_json"]:
            enabled_tools = [RoBToolType(t) for t in json.loads(row["enabled_tools_json"])]

        return RoBProjectSettings(
            id=row["id"],
            project_id=row["project_id"],
            enabled_tools=enabled_tools,
            dual_review_enabled=bool(row["dual_review_enabled"]),
            auto_detect_study_design=bool(row["auto_detect_study_design"]),
            require_supporting_quotes=bool(row["require_supporting_quotes"]),
            flag_uncertain_threshold=row["flag_uncertain_threshold"],
            batch_queue=json.loads(row["batch_queue_json"]) if row["batch_queue_json"] else [],
            batch_status=row["batch_status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_rob_audit(self, project_id: str, audit_entry: RoBAuditEntry) -> None:
        """Save a RoB audit entry."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO rob_audit (
                id, assessment_id, study_id, project_id, action,
                domain_id, previous_judgment, new_judgment, user_id, notes, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_entry.id,
            audit_entry.assessment_id,
            audit_entry.study_id,
            project_id,
            audit_entry.action,
            audit_entry.domain_id,
            audit_entry.previous_judgment,
            audit_entry.new_judgment,
            audit_entry.user_id,
            audit_entry.notes,
            audit_entry.timestamp.isoformat(),
        ))

        conn.commit()
        conn.close()

    def get_rob_audit_entries(self, project_id: str, assessment_id: Optional[str] = None) -> list[RoBAuditEntry]:
        """Get RoB audit entries, optionally filtered by assessment."""
        conn = sqlite3.connect(self._get_db_path(project_id))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if assessment_id:
            cursor.execute(
                "SELECT * FROM rob_audit WHERE project_id = ? AND assessment_id = ? ORDER BY timestamp DESC",
                (project_id, assessment_id)
            )
        else:
            cursor.execute(
                "SELECT * FROM rob_audit WHERE project_id = ? ORDER BY timestamp DESC",
                (project_id,)
            )

        rows = cursor.fetchall()
        conn.close()

        return [RoBAuditEntry(
            id=row["id"],
            assessment_id=row["assessment_id"],
            study_id=row["study_id"],
            action=row["action"],
            domain_id=row["domain_id"],
            previous_judgment=row["previous_judgment"],
            new_judgment=row["new_judgment"],
            user_id=row["user_id"],
            notes=row["notes"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        ) for row in rows]
