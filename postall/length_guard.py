"""
Platform length guard for PostAll.

Centralizes the hard publish character limits so the generator, director, and
publisher all measure the same thing the same way. Without this the pipeline
silently produces over-length content that the LLM never trimmed (prompt-only
"≤ N chars" instructions are notoriously unreliable), gets a soft scoring
penalty from the director (-0.2 on platform_fit), and only fails at the very
end of the pipeline when the publisher refuses to truncate.

The fix is layered:

  1. `PUBLISH_LIMITS` is the single source of truth. Publishers / director /
     executor all read from here.
  2. `compute_publishable_length()` measures the post the way the publisher
     will see it — after `clean_metadata()` has stripped headers / image
     prompt blocks. This is what the LinkedIn API will count, so this is
     what we have to keep under the cap.
  3. The executor calls `compute_publishable_length()` right after generation
     and, if it's over `target_chars(platform)`, fires a shrink retry against
     the LLM (see `executors.claude_api_executor.shrink_content`).
  4. The director calls `compute_publishable_length()` during review and, if
     the body is still over the hard cap, downgrades the decision to
     REQUEST_REVISION regardless of the average quality score — so an
     8.3/10 post that's 4458 chars stops being approve_with_notes and
     becomes a clear "trim before publish" signal.

`BUFFER_RATIO` of 0.9 keeps a margin between the executor's shrink target and
the hard cap. The shrink LLM call is itself imprecise, so we aim for 90% of
the cap and accept anything ≤ cap.
"""

from typing import Optional

# Hard publish-side character limits, by platform.
# Values match what individual publishers enforce as their refusal threshold.
# Keep this dict in sync if a platform raises or lowers its limit.
PUBLISH_LIMITS = {
    "linkedin": 3000,
    "instagram": 2200,
    "thread": 500,
    "threads": 500,
    "pinterest": 500,
    # Twitter is configurable per account (free vs Premium). 280 is the free
    # default; pipelines that publish from Premium accounts can override via
    # the resolver below or pass an explicit cap when reviewing.
    "twitter": 280,
    "twitter_zh": 280,
    "twitter_en": 280,
    # Long-form surfaces — generous caps mostly act as a sanity ceiling.
    "wechat": 50000,
    "reddit": 10000,
    "substack": 50000,
}

# Executor's shrink target is a fraction of the hard cap. The shrinker LLM
# call is imprecise (just like the original generation), so we aim a bit
# below the cap so a small overshoot still lands under the publisher's
# refusal threshold.
BUFFER_RATIO = 0.9


def get_publish_limit(platform: str, override: Optional[int] = None) -> int:
    """Return the hard publish-side cap for a platform.

    Args:
        platform: Platform key (e.g. "linkedin"). Case-insensitive.
        override: If provided, takes precedence over the table. Useful for
            Twitter Premium / Substack pro / any account that has a custom
            limit; the caller knows their account, the library does not.

    Returns:
        The hard cap in characters. Falls back to a generous 5000 for
        platforms not in the table so we never accidentally clamp content
        below a real limit.
    """
    if override is not None:
        return int(override)
    return PUBLISH_LIMITS.get(platform.lower(), 5000)


def get_target_length(platform: str, override: Optional[int] = None) -> int:
    """Return the executor's shrink target — i.e. the length to aim for so a
    small overshoot still lands under the hard cap.

    Calculated as `floor(hard_cap * BUFFER_RATIO)`.
    """
    return int(get_publish_limit(platform, override) * BUFFER_RATIO)


def compute_publishable_length(content: str, platform: str) -> int:
    """Measure the content the way the publisher will measure it.

    Strips PostAll metadata headers, the `### Image Prompt` block, horizontal
    rules, and (on LinkedIn) the paren substitution that the publisher
    applies. The returned int is exactly what the platform's API will count
    against the hard cap.

    Importing `clean_metadata` lazily keeps `length_guard` independent of
    publisher implementation details — callers can use this helper without
    pulling in the social SDKs that the publisher subpackage depends on.
    """
    try:
        from postall.publishers import clean_metadata  # noqa: WPS433 — lazy import
        cleaned = clean_metadata(content, platform)
    except Exception:
        # If the publisher subpackage isn't importable in this environment,
        # measure the raw content. We'd rather over-count (and trigger a
        # safe shrink) than skip the check.
        cleaned = content
    return len(cleaned)


def length_violation(
    content: str,
    platform: str,
    override: Optional[int] = None,
) -> Optional[dict]:
    """Return a structured violation dict if `content` exceeds the hard cap,
    or None if it's within limits.

    The dict shape is stable across callers so the director can put it into
    `revision_notes`, the executor can decide whether to shrink, and a future
    test can assert on the specific fields.

    Shape:
        {
            "platform": "linkedin",
            "limit": 3000,
            "actual": 4458,
            "over_by": 1458,
        }
    """
    limit = get_publish_limit(platform, override)
    actual = compute_publishable_length(content, platform)
    if actual <= limit:
        return None
    return {
        "platform": platform.lower(),
        "limit": limit,
        "actual": actual,
        "over_by": actual - limit,
    }
