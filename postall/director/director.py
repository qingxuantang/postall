"""
Content Director Agent for PostAll

The Content Director supervises content generation quality, providing:
- Quality control review before scheduling
- Brand voice consistency checks
- Scoring and approval decisions
- Human escalation when needed

Workflow:
1. Content Intern (PostAll) generates content with status="pending"
2. Content Director reviews each post
3. Director decides: APPROVE → status="scheduled", or ESCALATE → human review
4. Daemon publishes posts with status="scheduled" when time arrives
"""

import json
import re
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python < 3.9 fallback
    from dateutil.tz import gettz as ZoneInfo

from postall.config import (
    OUTPUT_DIR, TIMEZONE, get_platforms,
    get_brand_name, get_brand_style, get_brand_website
)
# NEW: James Workflow integrations
from postall.theory_framework.viral_scorer import VIRALScorer
from postall.utils.humanizer import ChineseHumanizer


class ContentDecision(str, Enum):
    """Decision outcomes from Content Director review."""
    APPROVE = "approve"                    # Score >= 9.0, auto-schedule (RAISED from 8.0)
    APPROVE_WITH_NOTES = "approve_with_notes"  # Score 8-9, schedule with feedback
    REQUEST_REVISION = "revise"            # Score 6-8, needs improvement
    ESCALATE_TO_HUMAN = "escalate"         # Score < 6 OR high risk
    REJECT = "reject"                      # Fundamentally flawed


@dataclass
class ReviewCriteria:
    """Scoring criteria for content review."""
    brand_voice: float = 0.0       # 0-1, alignment with brand voice
    platform_fit: float = 0.0      # 0-1, appropriate for platform
    quality_score: float = 0.0     # 0-1, overall writing quality
    engagement_potential: float = 0.0  # 0-1, predicted engagement
    risk_level: float = 0.0        # 0-1, potential controversy/issues (higher = riskier)
    factual_accuracy: float = 0.0  # 0-1, verifiable claims are correct
    # NEW v2.2: Three Circles Framework (Go Direct Methodology)
    truth_score: float = 0.0       # 0-1, factual accuracy about product/brand
    relevance_score: float = 0.0   # 0-1, relevance to current audience concerns
    strategic_score: float = 0.0   # 0-1, alignment with business goals
    geo_score: float = 0.0        # 0-1, GEO optimization (problem-targeting, structured data, AI-extractable, front-loaded value)

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'ReviewCriteria':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ReviewResult:
    """Result of a single post review."""
    post_path: str
    platform: str
    decision: ContentDecision
    score: float
    criteria_scores: ReviewCriteria
    feedback: str
    revision_notes: Optional[str] = None
    human_question: Optional[str] = None
    reviewed_at: str = field(default_factory=lambda: datetime.now(ZoneInfo(TIMEZONE)).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_path": self.post_path,
            "platform": self.platform,
            "decision": self.decision.value,
            "score": self.score,
            "criteria_scores": self.criteria_scores.to_dict(),
            "feedback": self.feedback,
            "revision_notes": self.revision_notes,
            "human_question": self.human_question,
            "reviewed_at": self.reviewed_at
        }


class ContentDirector:
    """
    Content Director Agent - Supervises content generation quality.

    The Director reviews generated content and decides whether to:
    - Auto-approve for scheduling (score >= approval_threshold)
    - Approve with notes (score >= 7)
    - Request revision (score 5-7)
    - Escalate to human (score < 5 or high risk)
    """

    # Default scoring weights (Updated v2.2 with Three Circles)
    DEFAULT_WEIGHTS = {
        "brand_voice": 0.15,           # Brand voice alignment
        "platform_fit": 0.10,          # Platform format compliance
        "quality_score": 0.10,         # Writing quality
        "engagement_potential": 0.10,  # Predicted engagement
        "risk_level": 0.05,            # Controversy risk (inverted)
        "factual_accuracy": 0.05,      # Verifiable claims accuracy
        # Three Circles Framework (Go Direct Methodology)
        "truth_score": 0.10,           # Is this factually accurate about us?
        "relevance_score": 0.10,       # Does audience care right now?
        "strategic_score": 0.05,       # Does this help business goals?
        # GEO (Generative Engine Optimization)
        "geo_score": 0.20,             # AI discovery: problem-targeting, structured data, front-loaded value
    }

    # Three Circles validation patterns
    EXAGGERATION_PATTERNS = [
        r"#1 planner",
        r"best .* ever",
        r"revolutionary",
        r"game-changing",
        r"guaranteed",
        r"always works",
        r"never fails",
    ]

    VERIFIABLE_FACTS = [
        # These should be customized per project in the review_criteria.yaml config
        r"proven system",
        r"tested methodology",
    ]

    HIGH_RELEVANCE_TOPICS = [
        r"new year",
        r"goal.?setting",
        r"quarterly review",
        r"planning system",
        r"AI.?assist",
        r"productivity",
        r"January planning",
        r"Q1 goals",
    ]

    STRATEGIC_PATTERNS = [
        # Common call-to-action patterns - brand-specific URLs should be in project config
        r"link in bio",
        r"free guide",
        r"download",
        r"newsletter",
        r"substack",
    ]

    PRE_APEX_INDICATORS = [
        r"building",
        r"growing",
        r"learning",
        r"just getting started",
        r"on the path",
        r"working toward",
        r"join us",
    ]

    POST_APEX_RED_FLAGS = [
        r"#1 planner",
        r"we're the best",
        r"we've achieved",
        r"mission accomplished",
        r"market leader",
        r"revolutionary",
    ]

    # Gain/Pain Psychological Framing patterns (Phase 5)
    LOSS_AVERSION_PATTERNS = [
        r"stop (losing|wasting|missing)",
        r"don't let .* slip away",
        r"protect your",
        r"end the chaos",
        r"before .* costs you",
    ]

    GAIN_ONLY_PATTERNS = [
        r"improve your",
        r"get more",
        r"achieve",
        r"better",
        r"upgrade",
    ]

    def __init__(self, config_path: Path = None):
        """
        Initialize the Content Director.

        Args:
            config_path: Path to director_rules.yaml (optional)
        """
        self.timezone = ZoneInfo(TIMEZONE)
        self.config = self._load_config(config_path)
        self.review_history: List[ReviewResult] = []

        # Thresholds (RAISED to James Workflow standards)
        self.approval_threshold = self.config.get("approval_threshold", 8.5)
        self.approval_with_notes_threshold = self.config.get("approval_with_notes_threshold", 8.0)
        self.revision_threshold = self.config.get("revision_threshold", 6.0)

        # Weights for composite score
        self.weights = self.config.get("weights", self.DEFAULT_WEIGHTS)

        # Auto-approve settings
        self.auto_approve_enabled = self.config.get("auto_approve_enabled", True)
        self.auto_approve_min_score = self.config.get("auto_approve_min_score", 8.5)
        self.auto_approve_exclude_platforms = self.config.get("auto_approve_exclude_platforms", [])

        # VIRAL scoring (NEW - from James Workflow)
        self.enable_viral_scoring = self.config.get("enable_viral_scoring", True)

    def _load_config(self, config_path: Path = None) -> Dict[str, Any]:
        """Load configuration from YAML or use defaults."""
        if config_path and config_path.exists():
            import yaml
            return yaml.safe_load(config_path.read_text(encoding="utf-8"))

        # Try default path
        default_path = Path(__file__).parent.parent.parent / "config" / "director_rules.yaml"
        if default_path.exists():
            import yaml
            return yaml.safe_load(default_path.read_text(encoding="utf-8"))

        # Return defaults (UPDATED to James Workflow standards)
        return {
            "approval_threshold": 8.5,
            "approval_with_notes_threshold": 8.0,
            "revision_threshold": 6.0,
            "auto_approve_enabled": True,
            "auto_approve_min_score": 8.5,
            "auto_approve_exclude_platforms": [],
            "weights": self.DEFAULT_WEIGHTS,
            "enable_viral_scoring": True  # NEW - VIRAL scoring from James Workflow
        }

    def review_week_content(self, output_path: Path, auto_schedule: bool = True) -> Dict[str, Any]:
        """
        Review all generated content for a week.

        Args:
            output_path: Path to the week's output folder
            auto_schedule: If True, auto-update schedule.json for approved posts

        Returns:
            {
                "summary": {...},
                "reviews": [...],
                "decisions": {...},
                "escalations": [...],
                "ready_to_schedule": [...],
                "review_report_path": str
            }
        """
        reviews: List[ReviewResult] = []
        escalations = []
        ready_to_schedule = []
        rejected_reviews = []

        # Iterate through platform folders
        for platform_key, platform_info in get_platforms().items():
            folder_name = platform_info.get("output_folder", platform_key)
            platform_path = output_path / folder_name

            if not platform_path.exists():
                continue

            # Find all post files
            for post_file in platform_path.glob("*.md"):
                # Skip non-post files
                if post_file.name.startswith("README"):
                    continue
                if post_file.name.endswith("_content.md"):
                    continue
                if post_file.name in ["image_prompts.md", "generation_report.md"]:
                    continue

                # Review the post
                review = self._review_single_post(post_file, platform_key)
                reviews.append(review)

                # Categorize by decision
                if review.decision == ContentDecision.APPROVE:
                    ready_to_schedule.append(review)
                elif review.decision == ContentDecision.APPROVE_WITH_NOTES:
                    ready_to_schedule.append(review)
                elif review.decision == ContentDecision.ESCALATE_TO_HUMAN:
                    escalations.append(review)
                    rejected_reviews.append(review)
                elif review.decision == ContentDecision.REQUEST_REVISION:
                    escalations.append(review)
                    rejected_reviews.append(review)
                elif review.decision == ContentDecision.REJECT:
                    rejected_reviews.append(review)

        # Compile results
        result = self._compile_review_report(reviews, output_path)
        result["escalations"] = [e.to_dict() for e in escalations]
        result["ready_to_schedule"] = [r.to_dict() for r in ready_to_schedule]

        # Auto-update schedule.json if enabled
        if auto_schedule:
            if ready_to_schedule:
                self._update_schedule_status(output_path, ready_to_schedule)
            # Mark rejected/escalated posts so they don't stay as ambiguous "pending"
            if rejected_reviews:
                self._mark_rejected_in_schedule(output_path, rejected_reviews)

        # Save review history
        self.review_history.extend(reviews)

        return result

    def _review_single_post(self, post_path: Path, platform: str) -> ReviewResult:
        """
        Review a single post using AI-powered analysis.

        Args:
            post_path: Path to the post file
            platform: Platform name

        Returns:
            ReviewResult with scoring and decision
        """
        content = post_path.read_text(encoding="utf-8")

        # Get AI review
        review_response = self._get_ai_review(content, platform)

        # Parse criteria scores
        criteria = ReviewCriteria.from_dict(review_response.get("criteria_scores", {}))

        # Calculate composite score (0-10 scale)
        composite_score = self._calculate_composite_score(criteria)

        # Make decision
        decision = self._make_decision(composite_score, criteria, platform)

        return ReviewResult(
            post_path=str(post_path),
            platform=platform,
            decision=decision,
            score=composite_score,
            criteria_scores=criteria,
            feedback=review_response.get("feedback", ""),
            revision_notes=review_response.get("revision_notes"),
            human_question=review_response.get("human_question")
        )

    def _get_ai_review(self, content: str, platform: str) -> Dict[str, Any]:
        """
        Use AI to analyze content quality.

        Tries executors in order: Claude CLI → Claude API → Gemini API
        Falls back to rule-based scoring if AI unavailable.
        """
        review_prompt = self._build_review_prompt(content, platform)

        # Try Claude CLI first
        try:
            from postall.executors.claude_cli_executor import execute_with_claude_cli
            response = execute_with_claude_cli(review_prompt, output_path=None, platform=None)
            if response.get("success") and response.get("content"):
                return self._parse_review_response(response["content"])
        except Exception:
            pass

        # Try Claude API
        try:
            from postall.executors.claude_api_executor import execute_review_with_claude_api
            response = execute_review_with_claude_api(review_prompt)
            if response:
                return self._parse_review_response(response)
        except Exception:
            pass

        # Try Gemini API
        try:
            from postall.executors.gemini_api_executor import execute_review_with_gemini
            response = execute_review_with_gemini(review_prompt)
            if response:
                return self._parse_review_response(response)
        except Exception:
            pass

        # Fallback: rule-based scoring
        return self._rule_based_review(content, platform)

    def _build_review_prompt(self, content: str, platform: str) -> str:
        """Build the review prompt for AI analysis."""
        prompt_template_path = Path(__file__).parent.parent.parent / "prompts" / "review_prompt.md"

        if prompt_template_path.exists():
            template = prompt_template_path.read_text(encoding="utf-8")
            return template.replace("{platform}", platform).replace("{content}", content)

        # Default prompt - use dynamic brand configuration
        brand_name = get_brand_name()
        brand_style = get_brand_style()
        return f"""You are the Content Director for {brand_name}. Review this {platform} post.

## Review Criteria
Score each from 0.0 to 1.0:
1. brand_voice - Matches {brand_style} tone
2. platform_fit - Content length/format matches {platform} best practices
3. quality_score - Clear, concise, no grammatical errors, engaging
4. engagement_potential - Provides value, has clear takeaway
5. risk_level - 0.0=safe, 1.0=risky (controversial statements, unverifiable claims)
6. factual_accuracy - All claims are accurate and verifiable; NO fabricated statistics or data
7. truth_score - Factual accuracy about the creator/brand; no exaggerated claims
8. relevance_score - Relevance to current audience interests and trends
9. strategic_score - Alignment with business/channel growth goals
10. geo_score - GEO (Generative Engine Optimization) quality

## Important
- Score factual_accuracy and truth_score LOW (0.3 or below) if the post contains fabricated statistics, invented research findings, or unverifiable data points
- Score relevance_score based on how well the topic matches what the target audience cares about RIGHT NOW
- Score strategic_score based on whether the post drives meaningful engagement or channel growth
- Score geo_score based on: (a) Does it target a specific problem/question users search for? (b) Is value front-loaded in first 2-3 sentences? (c) Contains AI-extractable insights (can be embedded in natural prose — does NOT require bullet lists)? (d) Includes named methods/brands for citation? (e) Question-based or problem-based title?
- IMPORTANT BALANCE: If a post is over-structured (too many bullet lists, numbered steps, formulaic "X reasons why" format), score engagement_potential and brand_voice DOWN. The best content wraps structured insights inside authentic storytelling. Naked checklists = low engagement. Conversational prose with extractable structure = high geo_score AND high engagement.

## Content to Review
Platform: {platform}

```
{content[:3000]}
```

## Output Format (JSON only)
```json
{{
    "criteria_scores": {{
        "brand_voice": 0.0-1.0,
        "platform_fit": 0.0-1.0,
        "quality_score": 0.0-1.0,
        "engagement_potential": 0.0-1.0,
        "risk_level": 0.0-1.0,
        "factual_accuracy": 0.0-1.0,
        "truth_score": 0.0-1.0,
        "relevance_score": 0.0-1.0,
        "strategic_score": 0.0-1.0,
        "geo_score": 0.0-1.0
    }},
    "feedback": "Brief overall assessment",
    "revision_notes": "Specific changes needed (or null if none)",
    "human_question": "Question for human if uncertain (or null)"
}}
```

Output ONLY the JSON, no other text."""

    def _parse_review_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response to extract review data."""
        # Try to find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                # Validate required fields
                if "criteria_scores" in data:
                    return data
            except json.JSONDecodeError:
                pass

        # Fallback: return default scores
        return {
            "criteria_scores": {
                "brand_voice": 0.7,
                "platform_fit": 0.7,
                "quality_score": 0.7,
                "engagement_potential": 0.6,
                "risk_level": 0.2,
                "factual_accuracy": 0.8
            },
            "feedback": "Unable to parse AI review. Using default scores.",
            "revision_notes": None,
            "human_question": None
        }

    def _rule_based_review(self, content: str, platform: str) -> Dict[str, Any]:
        """
        Fallback rule-based review when AI is unavailable.
        Uses heuristics to score content.
        """
        scores = {
            "brand_voice": 0.7,
            "platform_fit": 0.7,
            "quality_score": 0.7,
            "engagement_potential": 0.6,
            "risk_level": 0.1,
            "factual_accuracy": 0.8
        }

        feedback_parts = []

        # Brand voice checks - use dynamic brand name
        brand_name = get_brand_name()
        brand_name_lower = brand_name.lower().replace(" ", "")
        if brand_name_lower in content.lower().replace(" ", "") or brand_name in content:
            scores["brand_voice"] = 0.9
        if "™" in content or "Method" in content:
            scores["brand_voice"] = min(1.0, scores["brand_voice"] + 0.1)

        # Platform fit checks
        content_length = len(content)
        platform_limits = {
            "twitter": 280,
            "instagram": 2200,
            "linkedin": 3000,
            "thread": 500,
            "pinterest": 500,
            "reddit": 10000,
            "substack": 50000
        }
        limit = platform_limits.get(platform, 5000)

        # Check if content has reasonable length
        if content_length < limit * 0.1:
            scores["platform_fit"] = 0.5
            feedback_parts.append("Content seems too short")
        elif content_length > limit:
            scores["platform_fit"] = 0.6
            feedback_parts.append("Content may be too long for platform")
        else:
            scores["platform_fit"] = 0.8

        # Quality checks
        if content.count("##") >= 2:  # Has structure
            scores["quality_score"] = 0.8
        if "---" in content:  # Has sections
            scores["quality_score"] = min(1.0, scores["quality_score"] + 0.1)

        # Risk checks
        risk_words = ["guaranteed", "never fail", "100%", "promise", "secret"]
        for word in risk_words:
            if word.lower() in content.lower():
                scores["risk_level"] = min(1.0, scores["risk_level"] + 0.2)
                feedback_parts.append(f"Contains potentially risky word: '{word}'")

        # Engagement checks
        if "?" in content:  # Has questions
            scores["engagement_potential"] = 0.7
        if "link in bio" in content.lower() or "CTA" in content:
            scores["engagement_potential"] = min(1.0, scores["engagement_potential"] + 0.1)

        feedback = "Rule-based review (AI unavailable). " + " ".join(feedback_parts)

        # Add Three Circles scores
        scores["truth_score"] = self._evaluate_truth_score(content, platform)
        scores["relevance_score"] = self._evaluate_relevance_score(content, platform)
        scores["strategic_score"] = self._evaluate_strategic_score(content, platform)

        return {
            "criteria_scores": scores,
            "feedback": feedback,
            "revision_notes": None if scores["risk_level"] < 0.5 else "Review flagged content for risk",
            "human_question": None
        }

    def _evaluate_truth_score(self, content: str, platform: str) -> float:
        """
        Evaluate if content is factually accurate about product/brand.
        Part of Three Circles Framework (Go Direct Methodology).

        Returns: 0-1 score (higher = more truthful)
        """
        score = 0.8  # Start high, penalize for exaggerations

        # Check for exaggeration patterns (penalize)
        for pattern in self.EXAGGERATION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                score -= 0.15

        # Check for verifiable facts (bonus)
        for fact in self.VERIFIABLE_FACTS:
            if re.search(fact, content, re.IGNORECASE):
                score += 0.05

        return max(0.0, min(1.0, score))

    def _evaluate_relevance_score(self, content: str, platform: str) -> float:
        """
        Evaluate if content addresses current audience concerns.
        Part of Three Circles Framework (Go Direct Methodology).

        Returns: 0-1 score (higher = more relevant)
        """
        score = 0.6  # Start neutral

        # High relevance topics (current focus)
        for topic in self.HIGH_RELEVANCE_TOPICS:
            if re.search(topic, content, re.IGNORECASE):
                score += 0.1

        # Cap at 1.0
        return max(0.0, min(1.0, score))

    def _evaluate_strategic_score(self, content: str, platform: str) -> float:
        """
        Evaluate if content supports business goals.
        Part of Three Circles Framework (Go Direct Methodology).

        Returns: 0-1 score (higher = more strategic)
        """
        score = 0.5  # Start neutral

        # Strategic elements (aligned with goals)
        for pattern in self.STRATEGIC_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                score += 0.15

        # Slight penalty for no conversion path on key platforms
        if platform in ["instagram", "linkedin"] and score < 0.6:
            has_cta = any(re.search(p, content, re.IGNORECASE) for p in self.STRATEGIC_PATTERNS)
            if not has_cta:
                score -= 0.1

        return max(0.0, min(1.0, score))

    def _evaluate_pre_apex_positioning(self, content: str) -> Tuple[float, List[str]]:
        """
        Evaluate if content maintains pre-apex positioning.
        Part of Go Direct Methodology.

        Returns: (score adjustment, list of issues found)
        """
        adjustment = 0.0
        issues = []

        # Check for pre-apex indicators (bonus)
        for pattern in self.PRE_APEX_INDICATORS:
            if re.search(pattern, content, re.IGNORECASE):
                adjustment += 0.1

        # Check for post-apex red flags (penalty)
        for pattern in self.POST_APEX_RED_FLAGS:
            if re.search(pattern, content, re.IGNORECASE):
                adjustment -= 0.2
                issues.append(f"Post-apex language detected: pattern '{pattern}'")

        return adjustment, issues

    def _evaluate_psychology_score(self, content: str) -> float:
        """
        Evaluate if content uses loss-aversion framing effectively.
        Part of Gain/Pain Psychological Reframing (Phase 5).

        Returns: 0-1 score (higher = better use of psychology)
        """
        score = 0.6  # Start neutral

        # Loss-aversion patterns (good - bonus)
        for pattern in self.LOSS_AVERSION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                score += 0.1

        # Check for gain-only patterns without loss framing (weak)
        has_loss = any(re.search(p, content, re.IGNORECASE) for p in self.LOSS_AVERSION_PATTERNS)
        has_gain = any(re.search(p, content, re.IGNORECASE) for p in self.GAIN_ONLY_PATTERNS)

        # If ONLY gain patterns and no loss patterns, slight penalty
        if has_gain and not has_loss:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _calculate_composite_score(self, criteria: ReviewCriteria) -> float:
        """
        Calculate weighted composite score (0-10 scale).

        Risk level is inverted: lower risk = higher contribution.
        """
        scores = criteria.to_dict()

        # Invert risk_level (1.0 risk → 0.0 contribution, 0.0 risk → 1.0 contribution)
        scores["risk_level"] = 1.0 - scores["risk_level"]

        weighted_sum = 0.0
        total_weight = 0.0

        for key, weight in self.weights.items():
            if key in scores:
                weighted_sum += scores[key] * weight
                total_weight += weight

        if total_weight == 0:
            return 5.0

        # Convert to 0-10 scale
        return round((weighted_sum / total_weight) * 10, 2)

    def _make_decision(self, score: float, criteria: ReviewCriteria, platform: str) -> ContentDecision:
        """
        Make approval decision based on score and criteria.

        Hard rules override score-based decisions.
        """
        # Hard rules (override score)
        if criteria.risk_level > 0.7:
            return ContentDecision.ESCALATE_TO_HUMAN

        if criteria.factual_accuracy < 0.5:
            return ContentDecision.REJECT

        # Check auto-approve exclusions
        if platform in self.auto_approve_exclude_platforms:
            if score >= self.approval_threshold:
                return ContentDecision.APPROVE_WITH_NOTES

        # Score-based decisions
        if score >= self.approval_threshold:
            return ContentDecision.APPROVE
        elif score >= self.approval_with_notes_threshold:
            return ContentDecision.APPROVE_WITH_NOTES
        elif score >= self.revision_threshold:
            return ContentDecision.REQUEST_REVISION
        else:
            return ContentDecision.ESCALATE_TO_HUMAN

    def _update_schedule_status(self, output_path: Path, approved_reviews: List[ReviewResult]):
        """
        Update schedule.json to mark approved posts as "scheduled".
        Also insert approved posts into the SQLite database for cloud daemon.

        This is the key integration point: changing status from "pending" to "scheduled"
        allows the daemon to pick up posts for publishing.
        """
        schedule_file = output_path / "schedule.json"
        if not schedule_file.exists():
            return

        schedule = json.loads(schedule_file.read_text(encoding="utf-8"))

        # Build lookup of approved posts
        approved_paths = {r.post_path: r for r in approved_reviews}

        # Track posts to insert into database
        posts_to_insert = []

        # Update status for approved posts
        updated_count = 0
        for platform_key, posts in schedule.get("posts", {}).items():
            for post in posts:
                post_path = post.get("post_path", "")
                full_path = str(output_path / post_path)

                if full_path in approved_paths:
                    review = approved_paths[full_path]

                    # Only update if currently pending
                    if post.get("status") == "pending":
                        post["status"] = "scheduled"
                        post["director_review"] = {
                            "decision": review.decision.value,
                            "score": review.score,
                            "feedback": review.feedback,
                            "reviewed_at": review.reviewed_at
                        }
                        updated_count += 1

                        # Queue for database insertion
                        posts_to_insert.append({
                            'week_folder': output_path.name,
                            'platform': platform_key,
                            'post_path': post_path,
                            'scheduled_at': post.get('scheduled_at'),
                            'content_preview': self._extract_content_preview(output_path / post_path)
                        })

        # Save updated schedule
        if updated_count > 0:
            schedule["updated_at"] = datetime.now(self.timezone).isoformat()
            schedule["director_review_at"] = datetime.now(self.timezone).isoformat()
            schedule_file.write_text(
                json.dumps(schedule, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

        # Insert approved posts into database (for cloud daemon)
        if posts_to_insert:
            self._insert_posts_to_database(posts_to_insert)

        return updated_count

    def _mark_rejected_in_schedule(self, output_path: Path, rejected_reviews: List[ReviewResult]):
        """
        Mark rejected/escalated/revision posts in schedule.json so they don't
        remain as ambiguous "pending" entries.
        """
        schedule_file = output_path / "schedule.json"
        if not schedule_file.exists():
            return

        schedule = json.loads(schedule_file.read_text(encoding="utf-8"))
        rejected_paths = {r.post_path: r for r in rejected_reviews}

        updated_count = 0
        for platform_key, posts in schedule.get("posts", {}).items():
            for post in posts:
                post_path = post.get("post_path", "")
                full_path = str(output_path / post_path)

                if full_path in rejected_paths:
                    review = rejected_paths[full_path]
                    if post.get("status") == "pending":
                        post["status"] = review.decision.value  # "escalate", "revise", "reject"
                        post["director_review"] = {
                            "decision": review.decision.value,
                            "score": review.score,
                            "feedback": review.feedback,
                            "revision_notes": review.revision_notes,
                            "reviewed_at": review.reviewed_at
                        }
                        updated_count += 1

        if updated_count > 0:
            schedule["updated_at"] = datetime.now(self.timezone).isoformat()
            schedule_file.write_text(
                json.dumps(schedule, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            print(f"[ContentDirector] Marked {updated_count} posts as rejected/escalated in schedule.json")

    def _extract_content_preview(self, post_path: Path, max_length: int = 200) -> str:
        """Extract a preview of the post content for database storage."""
        try:
            if post_path.exists():
                content = post_path.read_text(encoding="utf-8")
                # Remove markdown headers and get first meaningful line
                lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
                if lines:
                    preview = lines[0]
                    return preview[:max_length] + '...' if len(preview) > max_length else preview
        except Exception:
            pass
        return ""

    def _insert_posts_to_database(self, posts: List[Dict[str, Any]]):
        """Insert approved posts into the cloud database."""
        try:
            from postall.cloud.database import ScheduleDatabase

            # Initialize database
            db = ScheduleDatabase()

            inserted_count = 0
            for post_data in posts:
                try:
                    # Parse scheduled datetime
                    scheduled_at_str = post_data.get('scheduled_at')
                    if not scheduled_at_str:
                        continue

                    # Convert ISO string to datetime
                    scheduled_at = datetime.fromisoformat(scheduled_at_str)

                    # Insert into database
                    db.add_scheduled_post(
                        week_folder=post_data['week_folder'],
                        platform=post_data['platform'],
                        post_path=post_data['post_path'],
                        scheduled_at=scheduled_at,
                        content_preview=post_data.get('content_preview', '')
                    )
                    inserted_count += 1

                except Exception as e:
                    print(f"[ContentDirector] Failed to insert post {post_data.get('post_path')}: {e}")
                    continue

            if inserted_count > 0:
                print(f"[ContentDirector] Inserted {inserted_count} approved posts into database")

        except ImportError:
            # Database module not available (local mode)
            print("[ContentDirector] Database module not available - skipping database insertion")
        except Exception as e:
            print(f"[ContentDirector] Failed to insert posts into database: {e}")

    def _compile_review_report(self, reviews: List[ReviewResult], output_path: Path) -> Dict[str, Any]:
        """Compile review results into a report."""
        # Count decisions
        decision_counts = {}
        for review in reviews:
            decision = review.decision.value
            decision_counts[decision] = decision_counts.get(decision, 0) + 1

        # Calculate averages
        if reviews:
            avg_score = sum(r.score for r in reviews) / len(reviews)
        else:
            avg_score = 0.0

        # Group by platform
        by_platform = {}
        for review in reviews:
            if review.platform not in by_platform:
                by_platform[review.platform] = []
            by_platform[review.platform].append(review.to_dict())

        # Generate report
        report = {
            "summary": {
                "total_reviewed": len(reviews),
                "avg_score": round(avg_score, 2),
                "decisions": decision_counts,
                "reviewed_at": datetime.now(self.timezone).isoformat()
            },
            "reviews": [r.to_dict() for r in reviews],
            "by_platform": by_platform
        }

        # Save report to file
        report_path = output_path / "director_review_report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        report["review_report_path"] = str(report_path)

        # Generate markdown report
        self._generate_markdown_report(reviews, output_path)

        return report

    def _generate_markdown_report(self, reviews: List[ReviewResult], output_path: Path):
        """Generate a human-readable markdown report."""
        report_lines = [
            "# Content Director Review Report",
            f"\n**Generated:** {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}",
            f"**Week Folder:** {output_path.name}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Posts Reviewed | {len(reviews)} |",
            f"| Average Score | {sum(r.score for r in reviews) / len(reviews) if reviews else 0:.1f}/10 |",
        ]

        # Decision breakdown
        decisions = {}
        for r in reviews:
            decisions[r.decision.value] = decisions.get(r.decision.value, 0) + 1

        for decision, count in decisions.items():
            icon = {"approve": "✅", "approve_with_notes": "📝", "revise": "🔄", "escalate": "⚠️", "reject": "❌"}.get(decision, "•")
            report_lines.append(f"| {icon} {decision.replace('_', ' ').title()} | {count} |")

        report_lines.extend([
            "",
            "## Review Details",
            ""
        ])

        # Group by platform
        by_platform = {}
        for review in reviews:
            if review.platform not in by_platform:
                by_platform[review.platform] = []
            by_platform[review.platform].append(review)

        for platform, platform_reviews in by_platform.items():
            report_lines.append(f"### {platform.title()}")
            report_lines.append("")
            report_lines.append("| Post | Score | Decision | Feedback |")
            report_lines.append("|------|-------|----------|----------|")

            for r in platform_reviews:
                post_name = Path(r.post_path).name[:30]
                decision_icon = {"approve": "✅", "approve_with_notes": "📝", "revise": "🔄", "escalate": "⚠️", "reject": "❌"}.get(r.decision.value, "•")
                feedback_short = r.feedback[:50] + "..." if len(r.feedback) > 50 else r.feedback
                report_lines.append(f"| {post_name} | {r.score:.1f} | {decision_icon} | {feedback_short} |")

            report_lines.append("")

        # Escalations section
        escalations = [r for r in reviews if r.decision == ContentDecision.ESCALATE_TO_HUMAN]
        if escalations:
            report_lines.extend([
                "## ⚠️ Escalations Requiring Human Review",
                ""
            ])
            for e in escalations:
                report_lines.extend([
                    f"### {Path(e.post_path).name}",
                    f"- **Platform:** {e.platform}",
                    f"- **Score:** {e.score:.1f}/10",
                    f"- **Reason:** {e.feedback}",
                    f"- **Question:** {e.human_question or 'N/A'}",
                    ""
                ])

        report_lines.extend([
            "---",
            "",
            "*Report generated by Content Director Agent*"
        ])

        # Save report
        report_path = output_path / "director_review_report.md"
        report_path.write_text("\n".join(report_lines), encoding="utf-8")

    def get_stats(self) -> Dict[str, Any]:
        """Get director statistics from review history."""
        if not self.review_history:
            return {
                "total_reviews": 0,
                "approved": 0,
                "revised": 0,
                "escalated": 0,
                "avg_score": 0.0
            }

        approved = sum(1 for r in self.review_history if r.decision in [ContentDecision.APPROVE, ContentDecision.APPROVE_WITH_NOTES])
        revised = sum(1 for r in self.review_history if r.decision == ContentDecision.REQUEST_REVISION)
        escalated = sum(1 for r in self.review_history if r.decision == ContentDecision.ESCALATE_TO_HUMAN)
        avg_score = sum(r.score for r in self.review_history) / len(self.review_history)

        return {
            "total_reviews": len(self.review_history),
            "approved": approved,
            "revised": revised,
            "escalated": escalated,
            "avg_score": round(avg_score, 2)
        }
