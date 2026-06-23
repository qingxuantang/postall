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
from typing import Dict, Any, Optional
from datetime import datetime

from postall.config import ANTHROPIC_API_KEY, get_brand_name, get_brand_style
from postall.length_guard import (
    get_publish_limit,
    get_target_length,
    length_violation,
)

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

# RAG: Semantic retrieval of historical high-scoring content
try:
    from postall.rag.retriever import retrieve_similar
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False


def _split_image_prompt(content: str) -> tuple:
    """Split content at `### Image Prompt` so the shrinker never touches it.

    Image prompts are downstream contracts — the image generator reads them
    verbatim. Letting the shrinker rewrite them risks dropping the block
    entirely (the LLM treats it as fluff) or paraphrasing it in ways that
    break image generation. The shrinker only sees the body; the image
    prompt is re-attached verbatim after.

    Returns: (body, image_prompt_section) where image_prompt_section may
    be an empty string if there was no Image Prompt block.
    """
    import re
    match = re.search(r'(\n#+\s*Image Prompt[\s\S]*$)', content, flags=re.IGNORECASE)
    if not match:
        return content, ""
    return content[: match.start()].rstrip() + "\n", match.group(1)


def shrink_content(
    content: str,
    platform_key: str,
    target_chars: int,
    hard_cap: int,
    language: str = "",
    client: Optional[Any] = None,
    max_attempts: int = 2,
) -> Optional[str]:
    """Ask the LLM to compress an over-length post to fit a target body length.

    The shrinker is intentionally narrow:
      * The `### Image Prompt` block is split off before the LLM call and
        re-attached verbatim afterwards. The LLM only sees the publishable
        body — this prevents it from "tidying away" the image prompt and
        breaking downstream image generation.
      * Anything inside ASCII straight quotes (`"…"`) and curly quotes
        (`"…"`) is treated as a source-of-truth quote that must survive
        the shrink. Generic prose can be tightened; attributed quotes
        cannot be paraphrased away.
      * It targets `target_chars` of *publishable body* (matching what the
        publisher will count) and hard-caps at `hard_cap`.
      * `max_attempts` retries with progressively tighter targets if the
        first shrink lands close-but-still-over. LLMs are imprecise about
        exact lengths; two attempts usually clear a long post.

    Returns the shrunk content on success (image prompt re-attached), or
    None if every attempt fails. The caller decides whether to keep, retry,
    or fall back to the original.
    """
    if not ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic  # noqa: WPS433 — lazy import keeps the dependency optional
    except ImportError:
        return None

    if client is None:
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        except Exception:
            return None

    body, image_prompt_block = _split_image_prompt(content)

    lang_hint = ""
    if language == "zh":
        lang_hint = (
            "OUTPUT MUST stay in Chinese. Keep proper-noun English terms "
            "in their original form."
        )
    elif language == "en":
        lang_hint = "OUTPUT MUST stay in English."

    last_shrunk = None
    current_target = target_chars
    for attempt in range(1, max_attempts + 1):
        shrink_prompt = f"""You are a precision content editor. Tighten the post below so its
publishable body fits under the platform character cap. Do not paraphrase quoted
material; only tighten prose around it.

Hard rules:
1. The publishable body MUST be ≤ {current_target} characters and MUST NOT
   exceed {hard_cap} characters under any circumstance. This is attempt
   {attempt} of {max_attempts}.
2. Keep every direct quote — anything inside straight quotes "…" or curly
   quotes "…" — EXACTLY as written. Do not abbreviate quotes, do not
   paraphrase them. Tighten only the prose around them.
3. Keep the structural shell intact: title header at the top (if present),
   section dividers (`---`) between major sections, and paragraph structure.
4. Keep proper nouns, statistics, percentages, dates, and URLs unchanged.
5. Tighten by removing redundancy, filler words, and repeated framing. If a
   sentence appears twice (in the body and in a closing recap), drop the
   recap, not the body.
6. Do NOT add new content or new claims.
7. Do NOT add any explanation, preamble, or "here is the shortened version"
   text. Output ONLY the rewritten post body.
{lang_hint}

Platform: {platform_key}
Target body length: {current_target} characters
Hard cap (must not exceed): {hard_cap} characters

Original post body to shrink:

{body}
"""

        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                messages=[{"role": "user", "content": shrink_prompt}],
            )
            shrunk_body = message.content[0].text
        except Exception as exc:
            print(f"[Shrinker] attempt {attempt} API call failed (non-fatal): {exc}")
            return last_shrunk  # may be None if first attempt failed

        # Re-attach the image prompt block before checking length. Length is
        # measured against the publisher view, which strips the image prompt
        # anyway — but reconstructing the full file is what the caller saves.
        full = shrunk_body.rstrip() + ("\n" + image_prompt_block if image_prompt_block else "")
        last_shrunk = full

        # If we're inside the hard cap, ship it.
        v = length_violation(full, platform_key)
        if v is None:
            return full

        # Still over: tighten the target by the leftover overshoot and retry.
        # Aim ~80% of the leftover to give the LLM headroom on the next pass.
        leftover = v["over_by"]
        current_target = max(int(current_target - leftover * 1.2), 200)

    return last_shrunk


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

        # RAG: Inject similar high-scoring historical content as few-shot examples
        if RAG_AVAILABLE:
            try:
                lang = language or "auto"
                rag_platform = platform_key
                if lang == "zh" and platform_key == "twitter":
                    rag_platform = "twitter_zh"
                elif lang == "en" and platform_key == "twitter":
                    rag_platform = "twitter_en"

                # Vertical isolation: classify the topic CURRENTLY being
                # generated so the retriever can skip rows from other
                # editorial verticals when this is a baseline (normal) post.
                # `output_path` always lives under .../single_topics/<topic>/
                try:
                    from postall.rag.indexer import classify_topic_type
                    parts = list(output_path.parts)
                    if "single_topics" in parts:
                        topic_idx = parts.index("single_topics") + 1
                        current_topic_name = parts[topic_idx] if topic_idx < len(parts) else ""
                    else:
                        current_topic_name = output_path.name
                    current_topic_type = classify_topic_type(current_topic_name) \
                        if current_topic_name else "normal"
                except Exception:
                    current_topic_type = "normal"

                rag_context = retrieve_similar(
                    query=prompt[:3000],
                    platform=rag_platform,
                    language=lang if lang != "auto" else None,
                    top_k=2,
                    min_score=8.0,
                    current_topic_type=current_topic_type,
                )
                if rag_context:
                    system_message += f"""

=== Historical High-Scoring Content Reference ===
Below are examples of previously approved, high-scoring content on similar topics.
Use them as STYLE and QUALITY reference only. Do NOT copy, closely paraphrase,
or reuse their specific angles. Create original content with a fresh perspective.

{rag_context}
=== End Reference ==="""
                    print(f"[RAG] Injected {rag_context.count('--- Example')} reference(s) for {platform_key}/{lang}")
                else:
                    print(f"[RAG] No matching high-scoring content found for {platform_key}/{lang}")
            except Exception as e:
                print(f"[RAG] Retrieval failed (non-fatal): {e}")

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

        # Length guard — see postall.length_guard for the rationale. Prompt-only
        # "≤ N chars" instructions are unreliable, especially when the prompt
        # also pins down a long must-include list. If the post-generation body
        # is over the platform's hard cap, fire one shrink retry against the
        # LLM. The shrinker preserves the markdown structure (so image prompts
        # at the end survive), and is best-effort — if shrinking fails or
        # still doesn't fit, the director will catch the overflow downstream
        # and downgrade the decision to REQUEST_REVISION rather than silently
        # publishing an over-length post.
        violation = length_violation(content, platform_key)
        if violation is not None:
            print(
                f"[LengthGuard] Generated {violation['actual']} chars, "
                f"exceeds {platform_key} cap of {violation['limit']} by "
                f"{violation['over_by']}. Calling shrinker..."
            )
            shrunk = shrink_content(
                content=content,
                platform_key=platform_key,
                target_chars=get_target_length(platform_key),
                hard_cap=violation['limit'],
                language=language,
                client=client,
            )
            if shrunk is not None:
                new_violation = length_violation(shrunk, platform_key)
                if new_violation is None:
                    print(
                        f"[LengthGuard] Shrink succeeded — body now within "
                        f"{platform_key} cap of {violation['limit']}."
                    )
                    content = shrunk
                else:
                    print(
                        f"[LengthGuard] Shrink reduced to {new_violation['actual']} "
                        f"chars but still over by {new_violation['over_by']}. "
                        "Keeping shrunk version; director will flag."
                    )
                    content = shrunk
            else:
                print(
                    "[LengthGuard] Shrink call failed; keeping original. "
                    "Director will downgrade decision."
                )

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


# Tool schema forces Claude to return well-formed JSON for content review.
# Free-form JSON output was failing on Chinese WeChat content where inner ASCII
# double quotes (e.g. "超长就 return error") inside string fields were not being
# escaped, breaking json.loads downstream and dropping every review to the
# default 6.5 fallback score. Tool use validates server-side.
_REVIEW_TOOL_SCHEMA = {
    "name": "submit_content_review",
    "description": "Submit the structured content review with scores, issues, and verdict.",
    "input_schema": {
        "type": "object",
        "properties": {
            "criteria_scores": {
                "type": "object",
                "properties": {
                    "brand_voice": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "platform_fit": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "quality_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "engagement_potential": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "risk_level": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "factual_accuracy": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "truth_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "relevance_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "strategic_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "geo_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
                "required": [
                    "brand_voice", "platform_fit", "quality_score",
                    "engagement_potential", "risk_level", "factual_accuracy",
                    "truth_score", "relevance_score", "strategic_score", "geo_score",
                ],
            },
            "issues": {
                "type": "array",
                "description": "One entry per score deduction, explaining what + how to fix.",
                "items": {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string"},
                        "deduction": {"type": "number"},
                        "location": {"type": "string"},
                        "problem": {"type": "string"},
                        "original_text": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["dimension", "problem", "suggestion"],
                },
            },
            "feedback": {"type": "string", "description": "Brief overall assessment."},
            "verdict": {
                "type": "string",
                "enum": ["可发布", "需修改后发布", "建议人工复核"],
            },
            "revision_notes": {"type": ["string", "null"]},
            "human_question": {"type": ["string", "null"]},
        },
        "required": ["criteria_scores", "issues", "feedback"],
    },
}


def execute_review_with_claude_api(prompt: str) -> str:
    """
    Execute a review request using Claude API.

    Uses Anthropic tool-use forced output so the JSON is validated server-side
    against _REVIEW_TOOL_SCHEMA. This eliminates the recurring parser failures
    seen on multi-language content where the model emitted unescaped inner
    ASCII double quotes inside string fields, breaking json.loads and dropping
    every review to the 6.5-default fallback score.

    Args:
        prompt: The review prompt with content to analyze

    Returns:
        JSON string ready to be parsed by ContentDirector._parse_review_response.
        Returns None on API failure so the Director can fall back to Gemini /
        rule-based review.
    """

    if not ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic
        import json as _json

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=5000,
            tools=[_REVIEW_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "submit_content_review"},
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        # The tool_use block's .input is a Python dict already validated by Anthropic.
        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_content_review":
                tool_input = block.input
                # Defensive post-process: Claude occasionally encodes a complex
                # nested array as a JSON-encoded string instead of a native list
                # (especially under tool_choice forced output). Re-parse here so
                # downstream code always sees the expected structure.
                for nested_array_key in ("issues",):
                    val = tool_input.get(nested_array_key)
                    if isinstance(val, str):
                        try:
                            tool_input[nested_array_key] = _json.loads(val)
                        except (ValueError, TypeError):
                            tool_input[nested_array_key] = []
                return _json.dumps(tool_input, ensure_ascii=False)

        # Fallback: model didn't call the tool (extremely rare with tool_choice forced).
        # Return whatever text came back so the legacy parser can have a go.
        for block in message.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return None

    except Exception:
        return None
