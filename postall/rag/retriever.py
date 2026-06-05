"""
Content Retriever - Semantic search for similar historical content.

Used during content generation to find relevant high-scoring examples
as few-shot references for Claude.
"""

from typing import Optional

from .indexer import get_or_create_collection


def retrieve_similar(
    query: str,
    platform: Optional[str] = None,
    language: Optional[str] = None,
    top_k: int = 3,
    min_score: float = 8.0,
    current_topic_type: Optional[str] = None,
) -> str:
    """
    Retrieve similar high-scoring historical content.

    Args:
        query: Current topic/prompt text to match against
        platform: Filter by platform (wechat/linkedin/twitter_zh/twitter_en)
        language: Filter by language (zh/en)
        top_k: Number of results to return
        min_score: Minimum director review score
        current_topic_type: The topic_type of the topic CURRENTLY being
            generated. When "normal" (the default for baseline posts), the
            retrieval excludes documents tagged with any non-normal vertical
            (e.g. "spotlight") so editorial verticals do not bleed into
            baseline content. When the current topic is itself a non-normal
            vertical, retrieval stays unfiltered so that vertical can learn
            from both its own history and from baseline content. Legacy
            index rows without a topic_type field pass through via $ne.

    Returns:
        Formatted context string for injection into system prompt,
        or empty string if no relevant content found.
    """
    try:
        collection = get_or_create_collection()
        if collection.count() == 0:
            return ""
    except Exception:
        return ""

    # Build where filter
    where_conditions = []
    if min_score > 0:
        where_conditions.append({"score": {"$gte": min_score}})
    if platform:
        platform_filter = platform.lower()
        if platform_filter == "twitter":
            where_conditions.append({
                "$or": [
                    {"platform": "twitter"},
                    {"platform": "twitter_zh"},
                    {"platform": "twitter_en"},
                ]
            })
        else:
            where_conditions.append({"platform": platform_filter})
    if language:
        where_conditions.append({"language": language})
    # Vertical isolation: when generating a baseline (normal) topic, exclude
    # entries tagged as a non-normal vertical. Legacy rows without a
    # topic_type field pass through.
    if current_topic_type == "normal":
        where_conditions.append({"topic_type": {"$ne": "spotlight"}})

    where = None
    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}

    try:
        results = collection.query(
            query_texts=[query[:3000]],
            n_results=top_k * 2,
            where=where,
        )
    except Exception:
        try:
            results = collection.query(
                query_texts=[query[:3000]],
                n_results=top_k * 2,
            )
        except Exception:
            return ""

    if not results or not results["documents"] or not results["documents"][0]:
        return ""

    # Build formatted context
    context_parts = []
    seen_topics = set()

    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        topic = meta.get("topic", "unknown")

        # Skip duplicate topics (only take best match per topic)
        if topic in seen_topics:
            continue
        seen_topics.add(topic)

        score = meta.get("score", 0)
        if score < min_score:
            continue

        # Truncate long content
        truncated = doc[:2000]
        if len(doc) > 2000:
            truncated += "\n[... truncated]"

        context_parts.append(
            f"--- Example (topic: {topic}, score: {score}/10) ---\n"
            f"{truncated}"
        )

        if len(context_parts) >= top_k:
            break

    return "\n\n".join(context_parts)
