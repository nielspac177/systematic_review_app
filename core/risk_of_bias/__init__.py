"""Risk of Bias assessment module for systematic reviews.

This module provides comprehensive Risk of Bias assessment capabilities
supporting multiple tools (RoB 2, ROBINS-I, NOS, QUADAS-2, JBI) with
AI-assisted assessments and human verification workflows.
"""

from .assessor import RoBAssessor
from .template_manager import RoBTemplateManager
from .study_design_detector import StudyDesignDetector
from .visualization import TrafficLightPlot, create_summary_table

__all__ = [
    "RoBAssessor",
    "RoBTemplateManager",
    "StudyDesignDetector",
    "TrafficLightPlot",
    "create_summary_table",
]
