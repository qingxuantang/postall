"""
Philosophy Weapons - Cognitive Hijacking Layer (认知劫持层)

8 philosophical mechanisms to make content impossible to ignore.
Based on major philosophers: Husserl, Heidegger, Nietzsche, Foucault, Levinas, Wittgenstein, Stoicism, Jung
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from enum import Enum


class PhilosophyMechanism(str, Enum):
    """8 cognitive hijacking mechanisms."""
    HUSSERL_INTENTIONALITY = "husserl_intentionality"      # 意向性 - Direct attention
    HEIDEGGER_BEING_DEATH = "heidegger_being_death"        # 向死而生 - Existential urgency
    NIETZSCHE_WILL_POWER = "nietzsche_will_power"          # 权力意志 - Superiority drive
    FOUCAULT_DISCOURSE = "foucault_discourse"              # 话语权力 - Frame replacement
    LEVINAS_THE_OTHER = "levinas_the_other"                # 他者面容 - Identity recognition
    WITTGENSTEIN_LANGUAGE = "wittgenstein_language"        # 语言游戏 - Concept redefinition
    STOICISM_CONTROL = "stoicism_control"                  # 控制二分 - Controllable focus
    JUNG_ARCHETYPE = "jung_archetype"                      # 原型 - Collective unconscious


@dataclass
class PhilosophyFramework:
    """A philosophical framework application."""
    mechanism: PhilosophyMechanism
    philosopher: str
    core_concept: str
    content_application: str
    hook_template: str
    example_cn: str
    example_en: str


class PhilosophyWeapons:
    """Philosophy weapons arsenal for cognitive hijacking."""

    FRAMEWORKS = {
        PhilosophyMechanism.HUSSERL_INTENTIONALITY: PhilosophyFramework(
            mechanism=PhilosophyMechanism.HUSSERL_INTENTIONALITY,
            philosopher="Husserl (胡塞尔)",
            core_concept="Epoché, essence intuition (悬置, 本质直观)",
            content_application="Return to things themselves, suspend preconceptions",
            hook_template="Forget everything you know about {topic}",
            example_cn="忘掉你对{主题}的所有认知",
            example_en="Forget everything you know about {topic}"
        ),

        PhilosophyMechanism.HEIDEGGER_BEING_DEATH: PhilosophyFramework(
            mechanism=PhilosophyMechanism.HEIDEGGER_BEING_DEATH,
            philosopher="Heidegger (海德格尔)",
            core_concept="Being-toward-death, authenticity (向死而生, 本真性)",
            content_application="Create existential urgency through finite time awareness",
            hook_template="You have {time_left} left—what are you doing with it?",
            example_cn="你还剩{时间量}——你在做什么？",
            example_en="You have {time_left} weeks to live—how many left?"
        ),

        PhilosophyMechanism.NIETZSCHE_WILL_POWER: PhilosophyFramework(
            mechanism=PhilosophyMechanism.NIETZSCHE_WILL_POWER,
            philosopher="Nietzsche (尼采)",
            core_concept="Revaluation of values, will to power (价值重估, 权力意志)",
            content_application="Subvert conventional beliefs to trigger refutation impulse",
            hook_template="{virtue} is actually a {weakness} in disguise",
            example_cn="{美德}其实是{弱点}的伪装",
            example_en="Humility is just another form of arrogance"
        ),

        PhilosophyMechanism.FOUCAULT_DISCOURSE: PhilosophyFramework(
            mechanism=PhilosophyMechanism.FOUCAULT_DISCOURSE,
            philosopher="Foucault (福柯)",
            core_concept="Power/knowledge, discipline (权力/知识, 规训)",
            content_application="Reveal hidden control mechanisms to replace reader's framework",
            hook_template="Why {authority} wants you to believe {belief}",
            example_cn="为什么{权威}要你相信{观念}",
            example_en="Why schools never teach you about money"
        ),

        PhilosophyMechanism.LEVINAS_THE_OTHER: PhilosophyFramework(
            mechanism=PhilosophyMechanism.LEVINAS_THE_OTHER,
            philosopher="Levinas (列维纳斯)",
            core_concept="The Other, responsibility (他者, 责任)",
            content_application="Create 'this is me' recognition moment through relational perspective",
            hook_template="What you owe to {other}",
            example_cn="你欠{对象}什么",
            example_en="What you owe to your future self"
        ),

        PhilosophyMechanism.WITTGENSTEIN_LANGUAGE: PhilosophyFramework(
            mechanism=PhilosophyMechanism.WITTGENSTEIN_LANGUAGE,
            philosopher="Wittgenstein (维特根斯坦)",
            core_concept="Language games (语言游戏)",
            content_application="Redefine familiar concepts to shift understanding",
            hook_template="'{concept}' doesn't mean what you think",
            example_cn="「{概念}」不是你想的那个意思",
            example_en="'Success' doesn't mean what you think"
        ),

        PhilosophyMechanism.STOICISM_CONTROL: PhilosophyFramework(
            mechanism=PhilosophyMechanism.STOICISM_CONTROL,
            philosopher="Stoic Philosophy (斯多葛)",
            core_concept="Dichotomy of control (控制二分法)",
            content_application="Shift focus from uncontrollable to controllable elements",
            hook_template="The only thing that matters about {topic} is {controllable}",
            example_cn="关于{话题}，唯一重要的是{可控部分}",
            example_en="The only thing that matters about your career is what you learn"
        ),

        PhilosophyMechanism.JUNG_ARCHETYPE: PhilosophyFramework(
            mechanism=PhilosophyMechanism.JUNG_ARCHETYPE,
            philosopher="Jung (荣格)",
            core_concept="Archetypes, collective unconscious (原型, 集体无意识)",
            content_application="Activate archetypal narratives in reader's unconscious",
            hook_template="Your inner {archetype} is calling—when will you answer?",
            example_cn="你内心的{原型}在召唤——何时回应？",
            example_en="That entrepreneur inside you—when will you start?"
        )
    }

    @classmethod
    def select_mechanisms(cls, topic: str, count: int = 3) -> List[PhilosophyFramework]:
        """
        Select most relevant philosophical mechanisms for a topic.

        Args:
            topic: The content topic
            count: Number of mechanisms to select (default 3)

        Returns:
            List of selected frameworks
        """
        # For now, return top mechanisms (can be enhanced with AI selection later)
        selected = [
            cls.FRAMEWORKS[PhilosophyMechanism.HEIDEGGER_BEING_DEATH],
            cls.FRAMEWORKS[PhilosophyMechanism.NIETZSCHE_WILL_POWER],
            cls.FRAMEWORKS[PhilosophyMechanism.FOUCAULT_DISCOURSE]
        ]
        return selected[:count]

    @classmethod
    def format_instructions(cls, mechanisms: List[PhilosophyFramework], language: str = "zh") -> str:
        """
        Format philosophical mechanisms as AI prompt instructions.

        Args:
            mechanisms: List of frameworks to apply
            language: "zh" for Chinese, "en" for English

        Returns:
            Formatted instruction string
        """
        instructions = []

        for mech in mechanisms:
            if language == "zh":
                instructions.append(f"""
【{mech.philosopher}】{mech.core_concept}
应用: {mech.content_application}
模板: {mech.hook_template}
示例: {mech.example_cn}
""")
            else:
                instructions.append(f"""
【{mech.philosopher}】{mech.core_concept}
Application: {mech.content_application}
Template: {mech.hook_template}
Example: {mech.example_en}
""")

        return "\n".join(instructions)

    @classmethod
    def get_all_mechanisms(cls) -> Dict[PhilosophyMechanism, PhilosophyFramework]:
        """Get all 8 philosophical mechanisms."""
        return cls.FRAMEWORKS
