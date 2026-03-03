"""
Feedback Collector - Collect feedback from multiple sources

Sources:
1. Telegram bot user ratings (manual)
2. Engagement metrics (automatic)
3. Director review scores (automatic)
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import sqlite3


class FeedbackCollector:
    """
    Collect and aggregate feedback from multiple sources.

    Feedback sources:
    - Telegram manual ratings (+1.0 to -1.0)
    - Engagement metrics (normalized to +1.0 to -1.0)
    - Director review scores (converted to signal)
    """

    def __init__(self, db_path: Path):
        """
        Initialize feedback collector.

        Args:
            db_path: Path to database (same as RuleLibrary)
        """
        self.db_path = Path(db_path)

    def collect_telegram_feedback(self, post_id: str) -> Optional[float]:
        """
        Collect feedback from Telegram bot ratings.

        Args:
            post_id: Database post ID

        Returns:
            Feedback signal (-1.0 to +1.0) or None if no feedback
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT signal FROM content_feedback
                    WHERE post_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (post_id,))

                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception as e:
            print(f"[FeedbackCollector] Error collecting Telegram feedback: {e}")

        return None

    def collect_engagement_feedback(self, post_id: str, platform: str) -> Optional[float]:
        """
        Collect feedback from engagement metrics.

        Note: This is a placeholder. Actual implementation would query
        platform APIs for likes, shares, comments, clicks.

        Args:
            post_id: Database post ID
            platform: Platform name

        Returns:
            Engagement score normalized to -1.0 to +1.0
        """
        # TODO: Implement actual engagement metric collection from platform APIs
        # For now, return None (no automatic engagement tracking)
        return None

    def collect_director_feedback(self, post_id: str) -> Optional[float]:
        """
        Collect feedback from Director review scores.

        Converts Director score (0-10) to RLHF signal (-1.0 to +1.0).

        Args:
            post_id: Database post ID

        Returns:
            Converted feedback signal
        """
        # TODO: Implement director score retrieval
        # For now, return None
        return None

    def aggregate_feedback(self, post_id: str) -> Dict[str, Any]:
        """
        Aggregate feedback from all sources for a post.

        Args:
            post_id: Database post ID

        Returns:
            Dictionary with feedback data
        """
        telegram = self.collect_telegram_feedback(post_id)
        # engagement = self.collect_engagement_feedback(post_id, platform)
        # director = self.collect_director_feedback(post_id)

        # Weighted average (if multiple sources available)
        signals = []
        if telegram is not None:
            signals.append(('telegram', telegram, 1.0))  # Weight 1.0

        # Calculate final signal
        if signals:
            total_weight = sum(w for _, _, w in signals)
            final_signal = sum(s * w for _, s, w in signals) / total_weight
        else:
            final_signal = 0.0

        return {
            'post_id': post_id,
            'telegram_signal': telegram,
            # 'engagement_signal': engagement,
            # 'director_signal': director,
            'final_signal': final_signal,
            'sources': [name for name, _, _ in signals]
        }

    @staticmethod
    def convert_director_score_to_signal(director_score: float) -> float:
        """
        Convert Director score (0-10) to RLHF signal (-1.0 to +1.0).

        Mapping:
        - 9.0-10.0 → +1.0 (Excellent)
        - 8.0-8.9 → +0.5 (Good)
        - 6.0-7.9 → 0.0 (Average)
        - 4.0-5.9 → -0.5 (Poor)
        - 0.0-3.9 → -1.0 (Very Poor)

        Args:
            director_score: Score from 0-10

        Returns:
            Signal from -1.0 to +1.0
        """
        if director_score >= 9.0:
            return 1.0
        elif director_score >= 8.0:
            return 0.5
        elif director_score >= 6.0:
            return 0.0
        elif director_score >= 4.0:
            return -0.5
        else:
            return -1.0

    @staticmethod
    def normalize_engagement_metrics(likes: int, shares: int, comments: int, threshold_high: int = 100) -> float:
        """
        Normalize engagement metrics to signal (-1.0 to +1.0).

        Args:
            likes: Number of likes
            shares: Number of shares
            comments: Number of comments
            threshold_high: Threshold for "high engagement"

        Returns:
            Engagement signal
        """
        # Weighted sum
        engagement_score = likes + shares * 3 + comments * 2

        # Normalize to -1.0 to +1.0
        if engagement_score >= threshold_high:
            return 1.0
        elif engagement_score >= threshold_high * 0.5:
            return 0.5
        elif engagement_score >= threshold_high * 0.2:
            return 0.0
        elif engagement_score >= threshold_high * 0.1:
            return -0.5
        else:
            return -1.0
