"""
Hook Types - 12 Hook Types for Viral Content

8 Basic Hooks + 4 Advanced Theory-Driven Hooks
From James Writing Workflow
"""

from dataclasses import dataclass
from typing import List
from enum import Enum


class HookCategory(str, Enum):
    """Hook category types."""
    BASIC = "basic"
    ADVANCED_THEORY = "advanced_theory"


@dataclass
class HookType:
    """A content hook type."""
    name: str
    category: HookCategory
    formula: str
    example_cn: str
    example_en: str
    theory_base: str = ""  # For advanced hooks


class HookTypes:
    """12 hook types for viral content creation."""

    BASIC_HOOKS = [
        HookType(
            name="Pain Point",
            category=HookCategory.BASIC,
            formula="Are you still [problem]?",
            example_cn="你还在用时间换钱吗？",
            example_en="Are you still trading time for money?"
        ),
        HookType(
            name="Transformation",
            category=HookCategory.BASIC,
            formula="From [low] to [high]",
            example_cn="从月入3千到年入百万",
            example_en="From $3K/month to $100K/year"
        ),
        HookType(
            name="Counter-intuitive",
            category=HookCategory.BASIC,
            formula="[Belief] is actually wrong",
            example_cn="努力工作不会让你致富",
            example_en="Hard work won't make you rich"
        ),
        HookType(
            name="Reveal",
            category=HookCategory.BASIC,
            formula="The truth about [Topic]...",
            example_cn="关于年入百万的真相...",
            example_en="The truth about making millions"
        ),
        HookType(
            name="Listicle",
            category=HookCategory.BASIC,
            formula="[N] ways to [goal]",
            example_cn="5个年入百万的方法",
            example_en="5 ways to earn $1M"
        ),
        HookType(
            name="Question",
            category=HookCategory.BASIC,
            formula="Why [A] but [B]?",
            example_cn="为什么有人不工作却能赚百万？",
            example_en="Why do some people not work but earn millions?"
        ),
        HookType(
            name="Comparison",
            category=HookCategory.BASIC,
            formula="Average people [A], experts [B]",
            example_cn="穷人思维 vs 富人思维",
            example_en="Poor mindset vs Rich mindset"
        ),
        HookType(
            name="Prediction",
            category=HookCategory.BASIC,
            formula="In [Year], [prediction]",
            example_cn="2026年，这3类人会暴富",
            example_en="In 2026, these 3 types will get rich"
        )
    ]

    ADVANCED_HOOKS = [
        HookType(
            name="Existential Awakening",
            category=HookCategory.ADVANCED_THEORY,
            theory_base="Heidegger (海德格尔)",
            formula="You have [limited time], yet [waste]",
            example_cn="你只有4000周可活——还剩多少？",
            example_en="You have 4000 weeks to live—how many left?"
        ),
        HookType(
            name="Value Subversion",
            category=HookCategory.ADVANCED_THEORY,
            theory_base="Nietzsche (尼采)",
            formula="[Virtue] is actually [weakness disguise]",
            example_cn="谦虚不过是另一种傲慢",
            example_en="Humility is another form of arrogance"
        ),
        HookType(
            name="Power Awareness",
            category=HookCategory.ADVANCED_THEORY,
            theory_base="Foucault (福柯)",
            formula="Why [authority] wants you to believe [X]",
            example_cn="为什么学校从不教你关于钱的知识",
            example_en="Why schools never teach you about money"
        ),
        HookType(
            name="Archetype Activation",
            category=HookCategory.ADVANCED_THEORY,
            theory_base="Jung (荣格)",
            formula="Your inner [archetype] is calling",
            example_cn="你内心的创业者——何时开始？",
            example_en="That entrepreneur inside you—when will you start?"
        )
    ]

    @classmethod
    def get_all_hooks(cls) -> List[HookType]:
        """Get all 12 hook types."""
        return cls.BASIC_HOOKS + cls.ADVANCED_HOOKS

    @classmethod
    def get_basic_hooks(cls) -> List[HookType]:
        """Get 8 basic hooks."""
        return cls.BASIC_HOOKS

    @classmethod
    def get_advanced_hooks(cls) -> List[HookType]:
        """Get 4 advanced theory-driven hooks."""
        return cls.ADVANCED_HOOKS

    @classmethod
    def format_for_prompt(cls, language: str = "zh") -> str:
        """Format all hooks as prompt instructions."""
        output = []

        output.append("=== 基础钩子 (8种) ===" if language == "zh" else "=== Basic Hooks (8 types) ===")
        for hook in cls.BASIC_HOOKS:
            example = hook.example_cn if language == "zh" else hook.example_en
            output.append(f"- {hook.name}: {hook.formula}")
            output.append(f"  示例: {example}" if language == "zh" else f"  Example: {example}")

        output.append("\n=== 高级理论钩子 (4种) ===" if language == "zh" else "\n=== Advanced Theory Hooks (4 types) ===")
        for hook in cls.ADVANCED_HOOKS:
            example = hook.example_cn if language == "zh" else hook.example_en
            output.append(f"- {hook.name} ({hook.theory_base}): {hook.formula}")
            output.append(f"  示例: {example}" if language == "zh" else f"  Example: {example}")

        return "\n".join(output)
