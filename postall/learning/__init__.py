"""
RLHF Self-Learning System

Integrated from James Writing Workflow to enable continuous improvement.
The system learns from user feedback and engagement metrics to evolve content generation rules.

Components:
- RLHFManager: Core RLHF logic and rule management
- RuleLibrary: Storage and scoring of content rules
- FeedbackCollector: Collect feedback from Telegram and engagement metrics
"""

from .rlhf_manager import RLHFManager
from .rule_library import RuleLibrary, ContentRule
from .feedback_collector import FeedbackCollector

__all__ = [
    'RLHFManager',
    'RuleLibrary',
    'ContentRule',
    'FeedbackCollector'
]
