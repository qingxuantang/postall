"""End-to-end smoke test for the director's length hard-gate.

Verifies that:
  1. A within-cap post keeps whatever decision the AI scorer assigned.
  2. An over-cap post's decision is downgraded to REQUEST_REVISION with
     a structured note pinning the exact overage.

No live API calls — the AI scorer is stubbed via a context manager so the
test is deterministic and runs offline.
"""

import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Stub config dependencies before importing director.
import postall.config as cfg
if not hasattr(cfg, "OUTPUT_DIR"):
    cfg.OUTPUT_DIR = tempfile.mkdtemp()
if not hasattr(cfg, "TIMEZONE"):
    cfg.TIMEZONE = "UTC"

from postall.director.director import ContentDirector, ContentDecision  # noqa: E402


def expect(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"OK:   {msg}")


@contextmanager
def stubbed_ai_review(director, criteria_scores):
    """Replace _get_ai_review so review_content runs offline.

    `criteria_scores` is the dict the real AI normally returns.
    """
    original = director._get_ai_review
    director._get_ai_review = lambda content, platform: {
        "criteria_scores": criteria_scores,
        "issues": [],
        "feedback": "stubbed review",
        "revision_notes": None,
        "human_question": None,
    }
    try:
        yield
    finally:
        director._get_ai_review = original


def make_post(body_chars: int) -> Path:
    """Write a LinkedIn-shaped post with `body_chars` of publishable body."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    )
    tmp.write(
        "# LinkedIn Post — Test\n\n"
        "**Posting Time:** Flexible\n"
        "**Content Pillar:** Building in Public\n\n"
        "---\n\n"
        + ("A" * body_chars) + "\n\n"
        "### Image Prompt\nA cat on a desk.\n"
    )
    tmp.close()
    return Path(tmp.name)


def main():
    director = ContentDirector()

    # 1. Under-cap post → AI's approve_with_notes stays.
    under_post = make_post(2500)
    high_scores = {
        "brand_voice": 0.9, "platform_fit": 0.8, "quality_score": 0.85,
        "engagement_potential": 0.8, "risk_level": 0.1, "factual_accuracy": 0.9,
        "truth_score": 0.9, "relevance_score": 0.8, "strategic_score": 0.85,
        "geo_score": 0.7,
    }
    with stubbed_ai_review(director, high_scores):
        review = director._review_single_post(under_post, "linkedin")
    expect(
        review.decision in (
            ContentDecision.APPROVE,
            ContentDecision.APPROVE_WITH_NOTES,
        ),
        f"under-cap post keeps an approve-class decision (got {review.decision})",
    )
    expect(
        review.revision_notes is None,
        "under-cap post has no length-violation revision note",
    )

    # 2. Over-cap post → decision downgraded, note pinpoints overage.
    over_post = make_post(3500)
    with stubbed_ai_review(director, high_scores):
        review = director._review_single_post(over_post, "linkedin")
    expect(
        review.decision == ContentDecision.REQUEST_REVISION,
        f"over-cap post downgraded to REQUEST_REVISION (got {review.decision})",
    )
    expect(
        review.revision_notes is not None,
        "over-cap post has a revision note",
    )
    expect(
        "3500" in review.revision_notes,
        "revision note quotes the actual chars (3500)",
    )
    expect(
        "3000" in review.revision_notes,
        "revision note quotes the platform cap (3000)",
    )
    expect(
        "500" in review.revision_notes,
        "revision note quotes the exact overage (500)",
    )

    # 3. Hard gate respects pre-existing REJECT / ESCALATE.
    risky_scores = dict(high_scores)
    risky_scores["risk_level"] = 0.95  # Triggers ESCALATE in _make_decision.
    with stubbed_ai_review(director, risky_scores):
        review = director._review_single_post(over_post, "linkedin")
    expect(
        review.decision == ContentDecision.ESCALATE_TO_HUMAN,
        f"high-risk overrides length downgrade (got {review.decision})",
    )

    print("\nAll director length-gate tests passed.")


if __name__ == "__main__":
    main()
