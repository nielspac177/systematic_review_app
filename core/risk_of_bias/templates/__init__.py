"""Built-in Risk of Bias tool templates.

This package contains the standard templates for various RoB assessment tools:
- RoB 2: Cochrane Risk of Bias 2 for RCTs
- ROBINS-I: Risk of Bias in Non-randomized Studies of Interventions
- Newcastle-Ottawa Scale: For cohort, case-control, and cross-sectional studies
- QUADAS-2: Quality Assessment of Diagnostic Accuracy Studies
- JBI: Joanna Briggs Institute Critical Appraisal tools
"""

from .rob2 import get_rob2_template
from .robins_i import get_robins_i_template
from .newcastle_ottawa import (
    get_nos_cohort_template,
    get_nos_case_control_template,
    get_nos_cross_sectional_template,
)
from .quadas2 import get_quadas2_template
from .jbi import (
    get_jbi_rct_template,
    get_jbi_cohort_template,
    get_jbi_qualitative_template,
)

__all__ = [
    "get_rob2_template",
    "get_robins_i_template",
    "get_nos_cohort_template",
    "get_nos_case_control_template",
    "get_nos_cross_sectional_template",
    "get_quadas2_template",
    "get_jbi_rct_template",
    "get_jbi_cohort_template",
    "get_jbi_qualitative_template",
]
