"""
Communication Tactics - Sharing Driver Layer (分享驱动层)

AIDA model, framing, narrative transportation, social currency
"""

from typing import Dict


class CommunicationTactics:
    """Communication tactics for viral sharing."""

    AIDA_MODEL = {
        'attention': 'Hook that captures attention instantly',
        'interest': 'Build interest through curiosity or value',
        'desire': 'Create desire through transformation or social proof',
        'action': 'Clear CTA for next step'
    }

    SOCIAL_CURRENCY_TYPES = [
        'Insight (洞察)',      # New perspective
        'Attitude (态度)',     # Express values
        'Information (资讯)',  # Useful data
        'Utility (实用)',      # Practical value
        'Emotion (情感)',      # Emotional connection
        'Identity (身份)'      # Status marker
    ]

    @classmethod
    def build_strategy(cls, platform: str) -> Dict[str, str]:
        """Build communication strategy for platform."""
        return {
            'aida': cls.AIDA_MODEL,
            'social_currency': cls.SOCIAL_CURRENCY_TYPES,
            'platform': platform
        }

    @classmethod
    def format_for_prompt(cls, language: str = "zh") -> str:
        """Format tactics as prompt instructions."""
        output = []
        output.append("=== AIDA模型 ===" if language == "zh" else "=== AIDA Model ===")
        for stage, desc in cls.AIDA_MODEL.items():
            output.append(f"- {stage.upper()}: {desc}")

        output.append("\n=== 社交货币 ===" if language == "zh" else "\n=== Social Currency ===")
        for currency in cls.SOCIAL_CURRENCY_TYPES:
            output.append(f"- {currency}")

        return "\n".join(output)
