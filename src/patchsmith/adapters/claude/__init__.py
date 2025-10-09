"""Claude AI adapter modules."""

from patchsmith.adapters.claude.agent import BaseAgent, AgentError
from patchsmith.adapters.claude.autonomous_fix_agent import AutonomousFixAgent
from patchsmith.adapters.claude.custom_query_generator_agent import CustomQueryGeneratorAgent
from patchsmith.adapters.claude.detailed_security_analysis_agent import (
    DetailedSecurityAnalysisAgent,
)
from patchsmith.adapters.claude.fix_generator_agent import FixGeneratorAgent
from patchsmith.adapters.claude.language_detection_agent import LanguageDetectionAgent
from patchsmith.adapters.claude.query_generator_agent import QueryGeneratorAgent
from patchsmith.adapters.claude.report_generator_agent import ReportGeneratorAgent
from patchsmith.adapters.claude.triage_agent import TriageAgent

__all__ = [
    "AgentError",
    "AutonomousFixAgent",
    "BaseAgent",
    "CustomQueryGeneratorAgent",
    "DetailedSecurityAnalysisAgent",
    "FixGeneratorAgent",
    "LanguageDetectionAgent",
    "QueryGeneratorAgent",
    "ReportGeneratorAgent",
    "TriageAgent",
]
