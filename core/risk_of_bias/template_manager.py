"""Template management for Risk of Bias tools.

Manages built-in and custom RoB templates, including loading, customization,
and persistence of project-specific template modifications.
"""

import json
from typing import Optional
from copy import deepcopy

from ..storage.models import RoBTemplate, RoBToolType, RoBDomainTemplate, SignalingQuestion
from .templates import (
    get_rob2_template,
    get_robins_i_template,
    get_nos_cohort_template,
    get_nos_case_control_template,
    get_nos_cross_sectional_template,
    get_quadas2_template,
    get_jbi_rct_template,
    get_jbi_cohort_template,
    get_jbi_qualitative_template,
)


class RoBTemplateManager:
    """Manage RoB templates including built-ins and customizations."""

    # Map tool types to their template factory functions
    BUILTIN_TEMPLATES = {
        RoBToolType.ROB_2: get_rob2_template,
        RoBToolType.ROBINS_I: get_robins_i_template,
        RoBToolType.NEWCASTLE_OTTAWA_COHORT: get_nos_cohort_template,
        RoBToolType.NEWCASTLE_OTTAWA_CASE_CONTROL: get_nos_case_control_template,
        RoBToolType.NEWCASTLE_OTTAWA_CROSS_SECTIONAL: get_nos_cross_sectional_template,
        RoBToolType.QUADAS_2: get_quadas2_template,
        RoBToolType.JBI_RCT: get_jbi_rct_template,
        RoBToolType.JBI_COHORT: get_jbi_cohort_template,
        RoBToolType.JBI_QUALITATIVE: get_jbi_qualitative_template,
    }

    # Display names for templates
    TOOL_DISPLAY_NAMES = {
        RoBToolType.ROB_2: "Cochrane RoB 2 (RCTs)",
        RoBToolType.ROBINS_I: "ROBINS-I (Non-randomized studies)",
        RoBToolType.NEWCASTLE_OTTAWA_COHORT: "Newcastle-Ottawa Scale (Cohort)",
        RoBToolType.NEWCASTLE_OTTAWA_CASE_CONTROL: "Newcastle-Ottawa Scale (Case-Control)",
        RoBToolType.NEWCASTLE_OTTAWA_CROSS_SECTIONAL: "Newcastle-Ottawa Scale (Cross-Sectional)",
        RoBToolType.QUADAS_2: "QUADAS-2 (Diagnostic accuracy)",
        RoBToolType.JBI_RCT: "JBI Critical Appraisal (RCTs)",
        RoBToolType.JBI_COHORT: "JBI Critical Appraisal (Cohort)",
        RoBToolType.JBI_QUALITATIVE: "JBI Critical Appraisal (Qualitative)",
        RoBToolType.CUSTOM: "Custom Template",
    }

    # Recommended tools by study design
    RECOMMENDED_BY_DESIGN = {
        "RCT": [RoBToolType.ROB_2, RoBToolType.JBI_RCT],
        "Cohort": [RoBToolType.NEWCASTLE_OTTAWA_COHORT, RoBToolType.JBI_COHORT, RoBToolType.ROBINS_I],
        "Case-control": [RoBToolType.NEWCASTLE_OTTAWA_CASE_CONTROL],
        "Cross-sectional": [RoBToolType.NEWCASTLE_OTTAWA_CROSS_SECTIONAL],
        "Non-randomized interventional": [RoBToolType.ROBINS_I],
        "Diagnostic accuracy": [RoBToolType.QUADAS_2],
        "Qualitative": [RoBToolType.JBI_QUALITATIVE],
    }

    def __init__(self, session_manager=None, project_id: Optional[str] = None):
        """
        Initialize template manager.

        Args:
            session_manager: Optional session manager for persistence
            project_id: Optional project ID for project-specific templates
        """
        self.session_manager = session_manager
        self.project_id = project_id
        self._template_cache = {}

    def get_builtin_template(self, tool_type: RoBToolType) -> Optional[RoBTemplate]:
        """
        Get a built-in template by tool type.

        Args:
            tool_type: The RoB tool type

        Returns:
            RoBTemplate or None if not found
        """
        if tool_type in self.BUILTIN_TEMPLATES:
            return self.BUILTIN_TEMPLATES[tool_type]()
        return None

    def get_template(self, tool_type: RoBToolType) -> Optional[RoBTemplate]:
        """
        Get template for a tool type, checking for customizations first.

        Args:
            tool_type: The RoB tool type

        Returns:
            RoBTemplate (customized if available, otherwise built-in)
        """
        # Check cache first
        cache_key = f"{self.project_id}_{tool_type.value}"
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]

        # Check for project customization
        if self.session_manager and self.project_id:
            templates = self.session_manager.get_rob_templates(self.project_id, tool_type)
            if templates:
                # Return most recent customization
                template = templates[0]
                self._template_cache[cache_key] = template
                return template

        # Fall back to built-in
        template = self.get_builtin_template(tool_type)
        if template:
            self._template_cache[cache_key] = template
        return template

    def list_available_templates(self) -> list[dict]:
        """
        List all available templates with metadata.

        Returns:
            List of template info dictionaries
        """
        templates = []

        for tool_type, factory in self.BUILTIN_TEMPLATES.items():
            template = factory()
            is_customized = False

            # Check if customized
            if self.session_manager and self.project_id:
                customs = self.session_manager.get_rob_templates(self.project_id, tool_type)
                if customs:
                    template = customs[0]
                    is_customized = True

            templates.append({
                "tool_type": tool_type,
                "display_name": self.TOOL_DISPLAY_NAMES.get(tool_type, template.name),
                "name": template.name,
                "description": template.description,
                "num_domains": len(template.domains),
                "applicable_designs": template.applicable_study_designs,
                "is_customized": is_customized,
                "version": template.version,
            })

        return templates

    def get_templates_for_design(self, study_design: str) -> list[RoBToolType]:
        """
        Get recommended templates for a study design.

        Args:
            study_design: The study design string

        Returns:
            List of recommended RoBToolTypes
        """
        # Normalize study design
        design_lower = study_design.lower()

        if "rct" in design_lower or "randomized" in design_lower or "randomised" in design_lower:
            return self.RECOMMENDED_BY_DESIGN.get("RCT", [])
        elif "cohort" in design_lower:
            return self.RECOMMENDED_BY_DESIGN.get("Cohort", [])
        elif "case-control" in design_lower or "case control" in design_lower:
            return self.RECOMMENDED_BY_DESIGN.get("Case-control", [])
        elif "cross-sectional" in design_lower or "cross sectional" in design_lower:
            return self.RECOMMENDED_BY_DESIGN.get("Cross-sectional", [])
        elif "diagnostic" in design_lower:
            return self.RECOMMENDED_BY_DESIGN.get("Diagnostic accuracy", [])
        elif "qualitative" in design_lower:
            return self.RECOMMENDED_BY_DESIGN.get("Qualitative", [])
        elif "non-randomized" in design_lower or "quasi" in design_lower:
            return self.RECOMMENDED_BY_DESIGN.get("Non-randomized interventional", [])

        # Default to cohort tools for unknown designs
        return [RoBToolType.NEWCASTLE_OTTAWA_COHORT]

    def customize_template(
        self,
        base_tool_type: RoBToolType,
        modifications: dict
    ) -> RoBTemplate:
        """
        Create a customized version of a template.

        Args:
            base_tool_type: The base tool type to customize
            modifications: Dict with modifications to apply

        Returns:
            Customized RoBTemplate
        """
        # Get base template
        base = self.get_builtin_template(base_tool_type)
        if not base:
            raise ValueError(f"Unknown tool type: {base_tool_type}")

        # Deep copy to avoid modifying original
        customized = deepcopy(base)
        customized.is_customized = True

        # Apply modifications
        if "name" in modifications:
            customized.name = modifications["name"]

        if "description" in modifications:
            customized.description = modifications["description"]

        if "domains" in modifications:
            # Modify existing domains or add new ones
            for domain_mod in modifications["domains"]:
                domain_id = domain_mod.get("id")
                if domain_id:
                    # Find and modify existing domain
                    for domain in customized.domains:
                        if domain.id == domain_id:
                            if "name" in domain_mod:
                                domain.name = domain_mod["name"]
                            if "short_name" in domain_mod:
                                domain.short_name = domain_mod["short_name"]
                            if "description" in domain_mod:
                                domain.description = domain_mod["description"]
                            if "signaling_questions" in domain_mod:
                                # Replace signaling questions
                                domain.signaling_questions = [
                                    SignalingQuestion(**sq) if isinstance(sq, dict) else sq
                                    for sq in domain_mod["signaling_questions"]
                                ]
                            if "judgment_guidance" in domain_mod:
                                domain.judgment_guidance = domain_mod["judgment_guidance"]
                            break
                else:
                    # Add new domain
                    new_domain = RoBDomainTemplate(**domain_mod)
                    customized.domains.append(new_domain)

        if "remove_domains" in modifications:
            # Remove specified domains
            domain_ids_to_remove = set(modifications["remove_domains"])
            customized.domains = [
                d for d in customized.domains
                if d.id not in domain_ids_to_remove
            ]

        # Save if we have persistence
        if self.session_manager and self.project_id:
            self.session_manager.save_rob_template(self.project_id, customized)
            # Clear cache
            cache_key = f"{self.project_id}_{base_tool_type.value}"
            if cache_key in self._template_cache:
                del self._template_cache[cache_key]

        return customized

    def reset_to_default(self, tool_type: RoBToolType) -> RoBTemplate:
        """
        Remove customizations and reset to built-in template.

        Args:
            tool_type: The tool type to reset

        Returns:
            The built-in template
        """
        # Delete customizations
        if self.session_manager and self.project_id:
            templates = self.session_manager.get_rob_templates(self.project_id, tool_type)
            for template in templates:
                self.session_manager.delete_rob_template(self.project_id, template.id)

        # Clear cache
        cache_key = f"{self.project_id}_{tool_type.value}"
        if cache_key in self._template_cache:
            del self._template_cache[cache_key]

        return self.get_builtin_template(tool_type)

    def export_template(self, tool_type: RoBToolType) -> str:
        """
        Export a template to JSON for sharing.

        Args:
            tool_type: The tool type to export

        Returns:
            JSON string representation
        """
        template = self.get_template(tool_type)
        if not template:
            raise ValueError(f"Template not found: {tool_type}")

        return template.model_dump_json(indent=2)

    def import_template(self, json_str: str) -> RoBTemplate:
        """
        Import a template from JSON.

        Args:
            json_str: JSON string representation

        Returns:
            Imported RoBTemplate
        """
        data = json.loads(json_str)

        # Validate and create template
        template = RoBTemplate.model_validate(data)
        template.is_customized = True
        template.is_builtin = False

        # Save if we have persistence
        if self.session_manager and self.project_id:
            self.session_manager.save_rob_template(self.project_id, template)

        return template

    def get_domain_summary(self, tool_type: RoBToolType) -> list[dict]:
        """
        Get a summary of domains for a template.

        Args:
            tool_type: The tool type

        Returns:
            List of domain summaries
        """
        template = self.get_template(tool_type)
        if not template:
            return []

        return [
            {
                "id": domain.id,
                "name": domain.name,
                "short_name": domain.short_name,
                "description": domain.description,
                "num_questions": len(domain.signaling_questions),
                "display_order": domain.display_order,
            }
            for domain in sorted(template.domains, key=lambda d: d.display_order)
        ]
