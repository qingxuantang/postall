"""
Psychology Triggers - Emotional Triggering Layer (情绪触发层)

Jung archetypes, cognitive biases, Maslow hierarchy, emotional triggers
"""

from typing import List, Dict
from dataclasses import dataclass


@dataclass
class PsychologyTrigger:
    """A psychological trigger mechanism."""
    name: str
    category: str
    description: str
    intensity: int  # 1-5 stars
    application: str


class PsychologyTriggers:
    """Psychology triggers arsenal."""

    EMOTION_TRIGGERS = [
        PsychologyTrigger(
            name="Fear (恐惧)",
            category="Emotion",
            description="Threat or danger awareness",
            intensity=5,
            application="The danger of {X} you don't know"
        ),
        PsychologyTrigger(
            name="Curiosity (好奇)",
            category="Emotion",
            description="Gap in knowledge",
            intensity=5,
            application="The truth about {X} is..."
        ),
        PsychologyTrigger(
            name="Anger (愤怒)",
            category="Emotion",
            description="Injustice or betrayal",
            intensity=4,
            application="We've all been fooled by {X}"
        ),
        PsychologyTrigger(
            name="Hope (希望)",
            category="Emotion",
            description="Possibility of better future",
            intensity=4,
            application="It's not too late to {X}"
        )
    ]

    @classmethod
    def get_triggers(cls) -> List[PsychologyTrigger]:
        """Get all psychology triggers."""
        return cls.EMOTION_TRIGGERS

    @classmethod
    def format_for_prompt(cls, language: str = "zh") -> str:
        """Format triggers as prompt instructions."""
        output = []
        for trigger in cls.EMOTION_TRIGGERS:
            stars = "★" * trigger.intensity + "☆" * (5 - trigger.intensity)
            output.append(f"- {trigger.name} ({stars}): {trigger.application}")
        return "\n".join(output)
