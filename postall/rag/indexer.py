"""
Content Indexer - Build and maintain the vector index from historical PostAll content.

Scans single_topics output directories, reads content + director review scores,
and indexes them into ChromaDB for semantic retrieval.

Usage:
    from postall.rag.indexer import build_full_index, index_topic

    # Build index from all existing content
    build_full_index()

    # Index a single new topic after publishing
    index_topic("my_new_topic")
"""

import json
from pathlib import Path
from typing import Optional

import chromadb

from postall.config import get_output_dir, get_project_root


COLLECTION_NAME = "postall_content"


def _get_chroma_path() -> str:
    """Get ChromaDB storage path, derived from project data directory."""
    data_dir = get_project_root() / "data" / "chroma_db"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir)


def _get_output_base() -> Path:
    """Get the single_topics output base directory."""
    return get_output_dir() / "single_topics"


def get_client():
    """Get persistent ChromaDB client."""
    return chromadb.PersistentClient(path=_get_chroma_path())


def get_or_create_collection(client=None):
    """Get or create the content collection."""
    if client is None:
        client = get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "PostAll historical content with quality scores"}
    )


def _extract_review_scores(topic_dir: Path) -> dict:
    """Extract per-file review scores from director_review_report.json."""
    review_json = topic_dir / "director_review_report.json"
    scores = {}
    if not review_json.exists():
        return scores
    try:
        data = json.loads(review_json.read_text())
        for r in data.get("reviews", []):
            post_path = r.get("post_path", "")
            scores[post_path] = {
                "score": r.get("score", 0),
                "decision": r.get("decision", "unknown"),
                "platform": r.get("platform", "unknown"),
                "feedback": (r.get("feedback", "") or "")[:500],
            }
    except Exception:
        pass
    return scores


def _detect_platform_from_path(file_path: Path) -> str:
    """Detect platform from file path."""
    parts = str(file_path).lower()
    if "wechat" in parts:
        return "wechat"
    elif "linkedin" in parts:
        return "linkedin"
    elif "tweets-zh" in parts or "x-tweets-zh" in parts:
        return "twitter_zh"
    elif "tweets-en" in parts or "x-tweets-en" in parts:
        return "twitter_en"
    elif "tweet" in parts or "x-tweet" in parts:
        return "twitter"
    return "unknown"


def _detect_language(text: str) -> str:
    """Simple language detection based on character ratio."""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return "zh" if chinese_chars > len(text) * 0.1 else "en"


def index_topic(topic_name: str, collection=None):
    """Index a single topic's content files with their review scores."""
    if collection is None:
        collection = get_or_create_collection()

    topic_dir = _get_output_base() / topic_name
    if not topic_dir.exists():
        return 0

    review_scores = _extract_review_scores(topic_dir)
    indexed = 0

    # Find all *_content.md files (the aggregate files, not the split ones)
    for content_file in topic_dir.rglob("*_content.md"):
        text = content_file.read_text(encoding="utf-8").strip()
        if not text or len(text) < 100:
            continue

        # Strip image prompts section to keep index clean
        img_idx = text.find("### Image Prompt")
        if img_idx > 0:
            text = text[:img_idx].strip()

        # Strip metadata headers
        for prefix in ["## Tweet", "## LinkedIn", "## WeChat", "**Posting Time:**", "**Content Pillar:**"]:
            if text.startswith(prefix):
                lines = text.split("\n")
                for i, line in enumerate(lines):
                    if i > 0 and line.strip() and not line.startswith("**") and not line.startswith("##") and line.strip() != "---":
                        text = "\n".join(lines[i:]).strip()
                        break

        platform = _detect_platform_from_path(content_file)
        language = _detect_language(text)

        # Find matching review score
        rel_path = str(content_file.relative_to(topic_dir))
        score_info = review_scores.get(rel_path, {})

        # Also try matching by platform from review data
        if not score_info:
            for rpath, rinfo in review_scores.items():
                if rinfo["platform"] == platform.replace("_zh", "").replace("_en", ""):
                    if score_info.get("score", 0) < rinfo["score"]:
                        score_info = rinfo

        doc_id = f"{topic_name}__{platform}__{content_file.stem}"

        metadata = {
            "topic": topic_name,
            "platform": platform,
            "language": language,
            "score": score_info.get("score", 0.0),
            "decision": score_info.get("decision", "unknown"),
            "content_length": len(text),
        }

        # Upsert to handle re-indexing
        collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
        )
        indexed += 1

    return indexed


def build_full_index():
    """Build complete index from all topics."""
    output_base = _get_output_base()
    if not output_base.exists():
        print(f"No output directory found at {output_base}")
        return 0

    client = get_client()
    collection = get_or_create_collection(client)

    total = 0
    topics = sorted(d.name for d in output_base.iterdir() if d.is_dir())

    for topic_name in topics:
        count = index_topic(topic_name, collection)
        if count > 0:
            total += count
            print(f"  Indexed {topic_name}: {count} files")

    print(f"\nTotal indexed: {total} documents across {len(topics)} topics")
    print(f"Collection size: {collection.count()}")
    return total


def get_index_stats():
    """Get current index statistics."""
    try:
        collection = get_or_create_collection()
        count = collection.count()
        return {
            "total_documents": count,
            "db_path": _get_chroma_path(),
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("Building full PostAll content index...")
    build_full_index()
