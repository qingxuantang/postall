"""
SQLite Database for PostAll Cloud Scheduling

Provides persistent storage for:
- Scheduled posts
- Publish history
- OAuth tokens
- Daemon statistics
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from zoneinfo import ZoneInfo

from postall.config import TIMEZONE


class ScheduleDatabase:
    """SQLite database for cloud scheduling."""

    def __init__(self, db_path: str = "data/schedule.db"):
        """
        Initialize the database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.timezone = ZoneInfo(TIMEZONE)
        self._initialize()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Scheduled posts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_folder TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    post_path TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    status TEXT DEFAULT 'scheduled',
                    content_preview TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    published_at TEXT,
                    publish_result TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    UNIQUE(week_folder, platform, post_path)
                )
            """)

            # Publish history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS publish_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    post_id TEXT,
                    week_folder TEXT,
                    post_path TEXT,
                    content_preview TEXT,
                    published_at TEXT NOT NULL,
                    result TEXT,
                    url TEXT
                )
            """)

            # OAuth tokens table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    platform TEXT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Daemon statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daemon_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_date TEXT NOT NULL,
                    checks_performed INTEGER DEFAULT 0,
                    posts_published INTEGER DEFAULT 0,
                    posts_failed INTEGER DEFAULT 0,
                    api_calls_made INTEGER DEFAULT 0,
                    UNIQUE(stat_date)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scheduled_posts_status
                ON scheduled_posts(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scheduled_posts_scheduled_at
                ON scheduled_posts(scheduled_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_publish_history_platform
                ON publish_history(platform)
            """)

    def initialize(self):
        """Public method to initialize database (for entrypoint script)."""
        self._initialize()

    # ==========================================
    # SCHEDULED POSTS OPERATIONS
    # ==========================================

    def add_scheduled_post(
        self,
        week_folder: str,
        platform: str,
        post_path: str,
        scheduled_at: datetime,
        content_preview: str = None
    ) -> int:
        """Add a new scheduled post."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scheduled_posts
                (week_folder, platform, post_path, scheduled_at, content_preview, status)
                VALUES (?, ?, ?, ?, ?, 'scheduled')
            """, (
                week_folder,
                platform,
                post_path,
                scheduled_at.isoformat(),
                content_preview
            ))
            return cursor.lastrowid

    def get_due_posts(self) -> List[Dict[str, Any]]:
        """Get all posts that are due for publishing."""
        now = datetime.now(self.timezone).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scheduled_posts
                WHERE status = 'scheduled'
                AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
            """, (now,))

            return [dict(row) for row in cursor.fetchall()]

    def get_upcoming_posts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get posts scheduled within the next N hours."""
        now = datetime.now(self.timezone)
        cutoff = (now + timedelta(hours=hours)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scheduled_posts
                WHERE status = 'scheduled'
                AND scheduled_at > ?
                AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
            """, (now.isoformat(), cutoff))

            return [dict(row) for row in cursor.fetchall()]

    def mark_published(
        self,
        post_id: int,
        result: Dict[str, Any]
    ):
        """Mark a post as published."""
        now = datetime.now(self.timezone).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Update scheduled_posts
            cursor.execute("""
                UPDATE scheduled_posts
                SET status = 'published',
                    published_at = ?,
                    publish_result = ?
                WHERE id = ?
            """, (now, json.dumps(result), post_id))

            # Get post info for history
            cursor.execute("""
                SELECT platform, week_folder, post_path, content_preview
                FROM scheduled_posts WHERE id = ?
            """, (post_id,))
            post = cursor.fetchone()

            if post:
                # Add to publish history
                cursor.execute("""
                    INSERT INTO publish_history
                    (platform, post_id, week_folder, post_path, content_preview,
                     published_at, result, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post['platform'],
                    str(post_id),
                    post['week_folder'],
                    post['post_path'],
                    post['content_preview'],
                    now,
                    json.dumps(result),
                    result.get('url')
                ))

    def mark_failed(
        self,
        post_id: int,
        error: str,
        increment_retry: bool = True
    ):
        """Mark a post as failed."""
        now = datetime.now(self.timezone).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if increment_retry:
                cursor.execute("""
                    UPDATE scheduled_posts
                    SET status = 'failed',
                        error = ?,
                        retry_count = retry_count + 1
                    WHERE id = ?
                """, (error, post_id))
            else:
                cursor.execute("""
                    UPDATE scheduled_posts
                    SET status = 'failed',
                        error = ?
                    WHERE id = ?
                """, (error, post_id))

    def reset_failed_post(self, post_id: int):
        """Reset a failed post back to scheduled status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scheduled_posts
                SET status = 'scheduled',
                    error = NULL
                WHERE id = ?
            """, (post_id,))

    def get_schedule_summary(self) -> Dict[str, Any]:
        """Get a summary of all scheduled posts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Count by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM scheduled_posts
                GROUP BY status
            """)
            by_status = {row['status']: row['count'] for row in cursor.fetchall()}

            # Count by platform
            cursor.execute("""
                SELECT platform, status, COUNT(*) as count
                FROM scheduled_posts
                GROUP BY platform, status
            """)
            by_platform = {}
            for row in cursor.fetchall():
                if row['platform'] not in by_platform:
                    by_platform[row['platform']] = {}
                by_platform[row['platform']][row['status']] = row['count']

            # Get next post
            cursor.execute("""
                SELECT * FROM scheduled_posts
                WHERE status = 'scheduled'
                ORDER BY scheduled_at ASC
                LIMIT 1
            """)
            next_post = cursor.fetchone()

            return {
                'total': sum(by_status.values()),
                'by_status': by_status,
                'by_platform': by_platform,
                'next_post': dict(next_post) if next_post else None
            }

    # ==========================================
    # IMPORT FROM JSON SCHEDULES
    # ==========================================

    def import_from_json_schedule(self, week_folder: Path) -> int:
        """
        Import posts from a week's schedule.json file.

        Args:
            week_folder: Path to week folder containing schedule.json

        Returns:
            Number of posts imported
        """
        schedule_file = week_folder / "schedule.json"
        if not schedule_file.exists():
            return 0

        schedule_data = json.loads(schedule_file.read_text(encoding="utf-8"))
        imported = 0

        for platform, posts in schedule_data.get("posts", {}).items():
            for post in posts:
                if post.get("status") == "scheduled":
                    scheduled_at = datetime.fromisoformat(post["scheduled_at"])
                    self.add_scheduled_post(
                        week_folder=week_folder.name,
                        platform=platform,
                        post_path=post.get("post_path", ""),
                        scheduled_at=scheduled_at,
                        content_preview=post.get("content_preview", "")[:200]
                    )
                    imported += 1

        return imported

    # ==========================================
    # DAEMON STATISTICS
    # ==========================================

    def record_check(self, published: int = 0, failed: int = 0):
        """Record a daemon check in statistics."""
        today = datetime.now(self.timezone).date().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO daemon_stats (stat_date, checks_performed, posts_published, posts_failed)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(stat_date) DO UPDATE SET
                    checks_performed = checks_performed + 1,
                    posts_published = posts_published + ?,
                    posts_failed = posts_failed + ?
            """, (today, published, failed, published, failed))

    def get_today_stats(self) -> Dict[str, int]:
        """Get today's daemon statistics."""
        today = datetime.now(self.timezone).date().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM daemon_stats WHERE stat_date = ?
            """, (today,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return {
                'checks_performed': 0,
                'posts_published': 0,
                'posts_failed': 0
            }

    # ==========================================
    # OAUTH TOKENS
    # ==========================================

    def save_token(
        self,
        platform: str,
        access_token: str,
        refresh_token: str = None,
        expires_at: datetime = None
    ):
        """Save or update OAuth token."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO oauth_tokens
                (platform, access_token, refresh_token, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                platform,
                access_token,
                refresh_token,
                expires_at.isoformat() if expires_at else None,
                datetime.now(self.timezone).isoformat()
            ))

    def get_token(self, platform: str) -> Optional[Dict[str, Any]]:
        """Get OAuth token for a platform."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM oauth_tokens WHERE platform = ?
            """, (platform,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_expiring_tokens(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get tokens expiring within N days."""
        cutoff = (datetime.now(self.timezone) + timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM oauth_tokens
                WHERE expires_at IS NOT NULL
                AND expires_at <= ?
            """, (cutoff,))
            return [dict(row) for row in cursor.fetchall()]
