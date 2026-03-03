"""
Claude API Executor (Fallback 1)
Uses Anthropic API directly when CLI is unavailable

Enhanced with James Writing Workflow's Four-Dimensional Weapons Arsenal:
- Philosophy: Cognitive hijacking mechanisms
- Psychology: Emotional triggers and archetypes
- Communication: Sharing drivers and narrative strategies
- Sociology: Identity alignment and social dynamics
"""

from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from postall.config import ANTHROPIC_API_KEY, get_brand_name, get_brand_style

# NEW: James Workflow integrations
try:
    from postall.theory_framework import (
        PhilosophyWeapons, HookTypes, VIRALScorer
    )
    from postall.utils.humanizer import ChineseHumanizer
    from postall.learning import RLHFManager
    THEORY_FRAMEWORK_AVAILABLE = True
except ImportError:
    THEORY_FRAMEWORK_AVAILABLE = False


def execute_with_claude_api(prompt: str, output_path: Path, platform_key: str, language: str = "") -> Dict[str, Any]:
    """
    Execute content generation using Claude API.

    This is Fallback 1 when Claude CLI is unavailable.
    Uses the Anthropic Python SDK.

    Args:
        prompt: The full prompt for content generation
        output_path: Directory to save generated content
        platform_key: Platform identifier
        language: Content language ("en", "zh", or "" for auto)

    Returns:
        Dictionary with success status and content/error
    """

    if not ANTHROPIC_API_KEY:
        return {
            "success": False,
            "error": "ANTHROPIC_API_KEY not configured"
        }

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        # Build messages with dynamic brand info
        brand_name = get_brand_name()
        brand_style = get_brand_style()

        # Build enhanced system message with Four-Dimensional framework + RLHF
        if THEORY_FRAMEWORK_AVAILABLE:
            # Get theory framework components
            philosophy_mechs = PhilosophyWeapons.select_mechanisms("", count=3)
            lang = language or "auto"
            hooks_guide = HookTypes.format_for_prompt(language=lang)

            # NEW: Get RLHF high-scoring rules
            try:
                from postall.config import OUTPUT_DIR
                rlhf_db = Path(OUTPUT_DIR).parent / "database" / "rlhf.db"
                rlhf_manager = RLHFManager(rlhf_db)
                rlhf_rules = rlhf_manager.get_rules_for_generation(count=8, include_exploration=True)
                rlhf_rules_text = rlhf_manager.format_prompt_with_rules("", rlhf_rules, language=lang)
            except Exception as e:
                print(f"[Executor] RLHF not available: {e}")
                rlhf_rules_text = ""
                rlhf_rules = []

            # Build language-appropriate system message
            if lang == "zh":
                framework_section = f"""
=== 哲学维度 (Philosophy - Cognitive Hijacking) ===
{PhilosophyWeapons.format_instructions(philosophy_mechs, language=lang)}

=== 心理学维度 (Psychology - Emotional Triggering) ===
Use high-intensity emotion triggers: Fear (恐惧), Curiosity (好奇), Anger (愤怒), Hope (希望)

=== 传播学维度 (Communication - Sharing Driver) ===
AIDA模型: Attention (抓眼球) → Interest (引兴趣) → Desire (造渴望) → Action (促行动)
社交货币: 提供洞察、态度、资讯、实用价值、情感共鸣、身份标识

=== 社会学维度 (Sociology - Identity Alignment) ===
激活社会认同: "我们" vs "他们"
社会比较: "你的同龄人已经..."
符号互动: 重新定义概念"""
                authenticity_note = """Content must feel authentic (no AI patterns in Chinese)

**🚫 禁止以下 AI 套话（发现即重写）：**
- 「整个人都被震撼了」「世界观被重构了」「价值观被颠覆了」
- 「久久不能平静」「陷入深思」「整个人愣住了」
- 「颠覆认知」「刷新三观」「醍醐灌顶」
- 「彻底改变了我」「完全不一样了」「从此以后...」
- 任何夸张的情绪表达

**✅ 正确的风格：**
- 以小见大：从具体细节引出洞察
- 有反转感：先说常见认知，再给出不同角度
- 轻描淡写：「挺有意思的一个观点」比「震撼」更真实
- 具体而非抽象：用例子说话，不用形容词堆砌"""
            else:
                framework_section = f"""
=== Philosophy (Cognitive Hijacking) ===
{PhilosophyWeapons.format_instructions(philosophy_mechs, language=lang)}

=== Psychology (Emotional Triggering) ===
Use high-intensity emotion triggers: Fear, Curiosity, Anger, Hope

=== Communication (Sharing Driver) ===
AIDA Model: Attention → Interest → Desire → Action
Social Currency: Insights, attitudes, practical value, emotional resonance, identity signals

=== Sociology (Identity Alignment) ===
Activate social identity: "Us" vs "Them"
Social comparison: "Your peers are already..."
Symbolic interaction: Redefine concepts"""
                authenticity_note = """Content must feel authentic and natural (no AI patterns)

**🚫 BANNED phrases (rewrite if found):**
- "completely changed my perspective" / "mind-blowing" / "game-changer"
- "I was shocked" / "I couldn't believe" / "This blew my mind"
- Any hyperbolic emotional language

**✅ Correct style:**
- Small insights, big implications (以小见大)
- Unexpected angles that make readers go "huh, interesting"
- Understated tone: "interesting point" beats "revolutionary"
- Specific examples over abstract claims"""

        # 注入当前日期用于时效性检查
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_year = datetime.now().year
        
        system_message = f"""You are an expert social media content creator for {brand_name}.
Content language: {"Chinese (中文)" if lang == "zh" else "English" if lang == "en" else "match the brand voice"}

**⚠️ CRITICAL - TIMELINESS CHECK (当前日期: {current_date}):**
- Current year is {current_year}. Verify all tech references are up-to-date.
- Claude models: Latest is Claude 4 Opus/Sonnet (NOT Claude 3 or 3.5)
- GPT models: Latest is GPT-4o, GPT-4 Turbo (check if referencing older versions)
- If the source material mentions outdated model versions, UPDATE them or note the context.
- Do NOT compare obsolete models (e.g., "GPT-4 vs Claude 3") as if they're current.
- When in doubt about current tech specs, state the information date or omit.

**CRITICAL: Apply the Four-Dimensional Weapons Arsenal for viral content:**
{framework_section}

=== Hook Types ===
{hooks_guide}

**Quality Standards:**
- Target VIRAL score ≥ 7.5
- {authenticity_note}
- Use specific examples, avoid vague claims
- Natural tone, conversational but impactful
- Quality threshold: 9.0/10

**⚠️ OUTPUT FORMAT - NO METADATA:**
- Do NOT include lines like "**Thread (N tweets):**" or "**Post Type:**"
- Do NOT include metadata headers like "**Content Pillar:**" or "**Theme:**"
- Start directly with the content (e.g., "1/ Hook text...")
- Only include ## Image Prompts section at the end

{rlhf_rules_text}

Brand guidelines: {brand_style}

Include image generation prompts marked with ## Image Prompts section."""
        else:
            # 注入当前日期用于时效性检查
            current_date = datetime.now().strftime("%Y-%m-%d")
            current_year = datetime.now().year
            
            system_message = f"""You are a social media content creator for {brand_name}.
Generate high-quality, engaging content ready for posting.
Follow brand guidelines: {brand_style}.
Include image generation prompts marked with ## Image Prompts section.

**⚠️ TIMELINESS CHECK (当前日期: {current_date}):**
- Current year is {current_year}. Verify all tech references are up-to-date.
- Claude models: Latest is Claude 4 Opus/Sonnet (NOT Claude 3 or 3.5)
- GPT models: Latest is GPT-4o, GPT-4 Turbo
- Do NOT compare obsolete model versions as if they're current."""

        # Call Claude API
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=system_message,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract content (keep image prompts in the file — image generator needs them)
        content = message.content[0].text

        # NEW: Humanize content (remove AI patterns)
        if THEORY_FRAMEWORK_AVAILABLE:
            lang = language or "auto"
            humanizer = ChineseHumanizer()
            ai_score_before = humanizer.calculate_ai_score(content)

            if ai_score_before > 0.3:  # If content has AI patterns
                content = humanizer.humanize(content, language=lang)
                ai_score_after = humanizer.calculate_ai_score(content)

                # Log humanization results
                print(f"[Humanizer] AI pattern score: {ai_score_before:.2f} → {ai_score_after:.2f}")

        # Save aggregate file (including image prompts — DO NOT strip them)
        content_file = output_path / f"{platform_key}_content.md"
        content_file.write_text(content, encoding="utf-8")

        # Split aggregate into individual post files for scheduler/director
        try:
            from postall.utils.content_parser import process_platform_content
            split_result = process_platform_content(output_path, platform_key)
            if split_result.get('success'):
                print(f"[Executor] Split into {split_result['post_count']} individual files")
            else:
                print(f"[Executor] Content split warning: {split_result.get('error', 'unknown')}")
        except Exception as e:
            print(f"[Executor] Content split error (non-fatal): {e}")

        return {
            "success": True,
            "output": content,
            "file_path": str(content_file),
            "model": message.model,
            "usage": {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens
            }
        }

    except ImportError:
        return {
            "success": False,
            "error": "anthropic package not installed. Run: pip install anthropic"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Claude API error: {str(e)}"
        }


def execute_review_with_claude_api(prompt: str) -> str:
    """
    Execute a review request using Claude API.

    Used by Content Director for reviewing generated content.

    Args:
        prompt: The review prompt with content to analyze

    Returns:
        Raw response text from Claude
    """

    if not ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text

    except Exception:
        return None
