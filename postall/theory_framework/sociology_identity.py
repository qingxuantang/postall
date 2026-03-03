"""
Sociology Identity - Identity Alignment Layer (身份认同层)

Social identity, social comparison, symbolic interaction, cultural capital
"""

from typing import Dict, List


class SociologyIdentity:
    """Sociology identity mechanisms."""

    IDENTITY_MECHANISMS = [
        {
            'concept': 'Social Identity (社会认同)',
            'application': '"We" vs "They" group division',
            'example': 'If you\'re a creator type...'
        },
        {
            'concept': 'Social Comparison (社会比较)',
            'application': 'Upward/Downward/Parallel comparison',
            'example': 'Your peers are already X while you...'
        },
        {
            'concept': 'Symbolic Interaction (符号互动)',
            'application': 'Concept naming, redefinition',
            'example': 'Stop being an employee—be an entrepreneur'
        },
        {
            'concept': 'Cultural Capital (文化资本)',
            'application': 'Exclusive insider knowledge',
            'example': 'Only 1% know about X'
        }
    ]

    @classmethod
    def define_identity(cls, audience: Dict[str, any]) -> Dict[str, any]:
        """Define identity strategy for target audience."""
        return {
            'mechanisms': cls.IDENTITY_MECHANISMS,
            'audience': audience
        }

    @classmethod
    def format_for_prompt(cls, language: str = "zh") -> str:
        """Format identity mechanisms as prompt instructions."""
        output = []
        for mech in cls.IDENTITY_MECHANISMS:
            output.append(f"- {mech['concept']}: {mech['application']}")
            output.append(f"  示例: {mech['example']}" if language == "zh" else f"  Example: {mech['example']}")
        return "\n".join(output)
