"""Unit tests for postall.length_guard — no API calls required."""
import sys
from pathlib import Path

# Allow running directly without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from postall.length_guard import (
    PUBLISH_LIMITS,
    BUFFER_RATIO,
    get_publish_limit,
    get_target_length,
    compute_publishable_length,
    length_violation,
)


SAMPLE_OVER = (
    "# LinkedIn Post — Example\n\n"
    "**Posting Time:** Flexible\n"
    "**Content Pillar:** Building in Public\n\n"
    "---\n\n"
    + "A" * 3200 + "\n\n"
    "### Image Prompt\n"
    "Pencil sketch on cream paper showing a builder at a desk." + "B" * 200
)

SAMPLE_UNDER = (
    "# LinkedIn Post — Tight\n\n"
    "**Posting Time:** Flexible\n\n"
    "---\n\n"
    + "Short body content.\n\n"
    + "### Image Prompt\nA cat."
)


def expect(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"OK:   {msg}")


def main():
    # 1. Hard caps match expectations.
    expect(get_publish_limit("linkedin") == 3000, "LinkedIn cap is 3000")
    expect(get_publish_limit("LinkedIn") == 3000, "case-insensitive lookup")
    expect(get_publish_limit("unknownplatform") == 5000, "fallback cap is 5000")
    expect(get_publish_limit("linkedin", override=2500) == 2500, "override wins")
    expect(get_target_length("linkedin") == int(3000 * BUFFER_RATIO),
           "target = hard_cap * BUFFER_RATIO")

    # 2. compute_publishable_length strips headers + image prompt.
    under_len = compute_publishable_length(SAMPLE_UNDER, "linkedin")
    expect(under_len < 100, f"under-cap body strips to short text (got {under_len})")
    expect("Image Prompt" not in str(under_len), "no leaked markers in length")

    # 3. Over-cap sample is over.
    over_len = compute_publishable_length(SAMPLE_OVER, "linkedin")
    expect(over_len > 3000, f"over-cap sample reports > 3000 (got {over_len})")

    # 4. length_violation: None on safe content.
    expect(length_violation(SAMPLE_UNDER, "linkedin") is None,
           "no violation on under-cap content")

    # 5. length_violation: structured dict on over-cap.
    v = length_violation(SAMPLE_OVER, "linkedin")
    expect(v is not None, "violation dict returned for over-cap")
    expect(v["platform"] == "linkedin", "platform field correct")
    expect(v["limit"] == 3000, "limit field correct")
    expect(v["actual"] > 3000, "actual field reflects measured length")
    expect(v["over_by"] == v["actual"] - v["limit"], "over_by = actual - limit")

    # 6. Override flows through length_violation. SAMPLE_UNDER strips to a
    #    19-char body, so an override of 10 must trigger a violation while
    #    50 must not.
    v_small = length_violation(SAMPLE_UNDER, "linkedin", override=10)
    expect(v_small is not None, "override of 10 chars triggers violation")
    expect(v_small["limit"] == 10, "override flows through to violation dict")
    v_safe = length_violation(SAMPLE_UNDER, "linkedin", override=50)
    expect(v_safe is None, "override of 50 chars does not trigger on 19-char body")

    print("\nAll length_guard tests passed.")


if __name__ == "__main__":
    main()
