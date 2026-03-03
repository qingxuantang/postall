"""
Post Scheduler for PostAll

File-based scheduling system that:
- Extracts suggested publish times from generated posts
- Creates schedule.json to track scheduled posts
- Manages schedule.ready marker files
- Publishes posts when their scheduled time arrives

Uses US/Pacific timezone for all scheduling.
"""

import json
import re
from datetime import datetime, timedelta, time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from zoneinfo import ZoneInfo

from postall.config import OUTPUT_DIR, TIMEZONE, get_platforms


class ScheduleStatus(str, Enum):
    """Post scheduling status."""
    PENDING = "pending"           # Generated but not scheduled
    SCHEDULED = "scheduled"       # Scheduled for future publish
    PUBLISHED = "published"       # Successfully published
    FAILED = "failed"             # Publishing failed
    SKIPPED = "skipped"           # Manually skipped


# Default optimal posting times by platform (US/Pacific timezone)
DEFAULT_POSTING_TIMES = {
    "twitter": {
        "morning": "08:00",
        "afternoon": "12:00",
        "evening": "17:00"
    },
    "linkedin": {
        "morning": "07:30",
        "afternoon": "12:00"
    },
    "instagram": {
        "morning": "08:00",
        "afternoon": "12:00",
        "evening": "19:00"
    },
    "thread": {
        "morning": "09:00",
        "evening": "18:00"
    },
    "pinterest": {
        "afternoon": "14:00",
        "evening": "20:00"
    },
    "reddit": {
        "morning": "09:00",
        "afternoon": "13:00"
    },
    "substack": {
        "morning": "08:00"
    }
}

# Day name to weekday number mapping
DAY_TO_WEEKDAY = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6
}


class PostScheduler:
    """Scheduler for managing post publishing times."""

    def __init__(self, week_folder: Path = None):
        """
        Initialize the scheduler.

        Args:
            week_folder: Path to the week's output folder
        """
        self.timezone = ZoneInfo(TIMEZONE)
        self.week_folder = week_folder
        self.schedule_file = week_folder / "schedule.json" if week_folder else None

    def _get_week_start_date(self) -> Optional[datetime]:
        """
        Extract the week start date from the folder name.

        Folder format: YYYY-MM-DD_weekN (e.g., 2025-12-29_week1)

        Returns:
            datetime of the week's Monday, or None if invalid
        """
        if not self.week_folder:
            return None

        folder_name = self.week_folder.name
        match = re.match(r'(\d{4}-\d{2}-\d{2})_week\d+', folder_name)
        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, "%Y-%m-%d")
        return None

    def _parse_day_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract day name from filename.

        Examples:
            monday_morning_tweet.md -> monday
            01_tuesday_educational_carousel.md -> tuesday

        Returns:
            Day name (lowercase) or None
        """
        filename_lower = filename.lower()
        for day in DAY_TO_WEEKDAY.keys():
            if day in filename_lower:
                return day
        return None

    def _parse_time_from_content(self, content: str) -> Optional[str]:
        """
        Extract posting time from post content.

        Looks for patterns like:
            **Posting Time:** 8-9 AM
            **Posting Time:** 12:00 PM

        Returns:
            Time string in HH:MM format, or None
        """
        # Pattern: **Posting Time:** followed by time
        patterns = [
            r'\*\*Posting Time:\*\*\s*(\d{1,2})(?:-\d{1,2})?\s*(AM|PM|am|pm)',
            r'\*\*Posting Time:\*\*\s*(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)',
            r'\*\*Best Time:\*\*\s*(\d{1,2})(?:-\d{1,2})?\s*(AM|PM|am|pm)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                groups = match.groups()
                hour = int(groups[0])
                minute = int(groups[1]) if len(groups) > 2 and groups[1].isdigit() else 0
                period = groups[-1].upper()

                # Convert to 24-hour format
                if period == "PM" and hour != 12:
                    hour += 12
                elif period == "AM" and hour == 12:
                    hour = 0

                return f"{hour:02d}:{minute:02d}"

        return None

    def _parse_date_from_content(self, content: str) -> Optional[datetime]:
        """
        Extract full date from post content.

        Looks for patterns like:
            **Post Date**: Monday, December 30, 2025

        Returns:
            datetime or None
        """
        # Pattern: **Post Date**: Day, Month DD, YYYY
        pattern = r'\*\*Post Date\*\*:\s*\w+,\s+(\w+)\s+(\d{1,2}),\s+(\d{4})'
        match = re.search(pattern, content)
        if match:
            month_str, day, year = match.groups()
            try:
                date_str = f"{month_str} {day}, {year}"
                return datetime.strptime(date_str, "%B %d, %Y")
            except ValueError:
                pass
        return None

    def _get_datetime_for_day(
        self,
        day_name: str,
        time_str: str = None,
        time_of_day: str = "morning"
    ) -> Optional[datetime]:
        """
        Calculate the actual datetime for a day in the week.

        Args:
            day_name: Day name (e.g., "monday")
            time_str: Time in HH:MM format (optional)
            time_of_day: morning/afternoon/evening for default time

        Returns:
            datetime with timezone
        """
        week_start = self._get_week_start_date()
        if not week_start:
            return None

        day_name_lower = day_name.lower()
        if day_name_lower not in DAY_TO_WEEKDAY:
            return None

        # Calculate the date
        target_weekday = DAY_TO_WEEKDAY[day_name_lower]
        start_weekday = week_start.weekday()
        days_diff = target_weekday - start_weekday
        target_date = week_start + timedelta(days=days_diff)

        # Get the time
        if time_str:
            hour, minute = map(int, time_str.split(":"))
        else:
            # Use default time based on time_of_day
            default_time = "09:00"  # Fallback
            hour, minute = map(int, default_time.split(":"))

        # Combine date and time with timezone
        target_datetime = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            hour,
            minute,
            tzinfo=self.timezone
        )

        return target_datetime

    def extract_schedule_from_post(
        self,
        post_path: Path,
        platform: str
    ) -> Dict[str, Any]:
        """
        Extract scheduling information from a post file.

        Args:
            post_path: Path to the post markdown file
            platform: Platform name (twitter, linkedin, etc.)

        Returns:
            Dictionary with scheduling info
        """
        content = post_path.read_text(encoding="utf-8")
        filename = post_path.name

        # Extract day from filename
        day_name = self._parse_day_from_filename(filename)

        # Extract time from content
        time_str = self._parse_time_from_content(content)

        # Extract full date if present
        explicit_date = self._parse_date_from_content(content)

        # Determine time of day from filename
        time_of_day = "morning"  # default
        if "afternoon" in filename.lower():
            time_of_day = "afternoon"
        elif "evening" in filename.lower():
            time_of_day = "evening"

        # If no explicit time, use platform defaults
        if not time_str and platform in DEFAULT_POSTING_TIMES:
            platform_times = DEFAULT_POSTING_TIMES[platform]
            time_str = platform_times.get(time_of_day, list(platform_times.values())[0])

        # Calculate scheduled datetime
        scheduled_at = None
        if explicit_date:
            # Use explicit date with extracted or default time
            hour, minute = map(int, (time_str or "09:00").split(":"))
            scheduled_at = datetime(
                explicit_date.year,
                explicit_date.month,
                explicit_date.day,
                hour,
                minute,
                tzinfo=self.timezone
            )
        elif day_name:
            scheduled_at = self._get_datetime_for_day(day_name, time_str, time_of_day)

        return {
            "post_path": str(post_path.relative_to(self.week_folder)),
            "platform": platform,
            "day": day_name,
            "time": time_str,
            "time_of_day": time_of_day,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "status": ScheduleStatus.PENDING.value
        }

    def scan_week_for_posts(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scan the week folder and extract all posts with schedule info.

        Returns:
            Dictionary with platform keys and lists of post schedule info
        """
        all_posts = {}

        for platform_key, platform_info in get_platforms().items():
            folder_name = platform_info["output_folder"]
            platform_path = self.week_folder / folder_name

            if not platform_path.exists():
                continue

            platform_posts = []

            # Find all markdown files (excluding READMEs and aggregate files)
            for md_file in platform_path.glob("*.md"):
                if md_file.name.startswith("README"):
                    continue
                if md_file.name.endswith("_content.md"):
                    continue
                if md_file.name == "image_prompts.md":
                    continue

                schedule_info = self.extract_schedule_from_post(md_file, platform_key)
                if schedule_info.get("scheduled_at"):
                    platform_posts.append(schedule_info)

            if platform_posts:
                # Sort by scheduled time
                platform_posts.sort(key=lambda x: x.get("scheduled_at", ""))
                all_posts[platform_key] = platform_posts

        return all_posts

    def load_schedule(self) -> Dict[str, Any]:
        """Load existing schedule from schedule.json."""
        if self.schedule_file and self.schedule_file.exists():
            return json.loads(self.schedule_file.read_text(encoding="utf-8"))
        return {"posts": {}, "created_at": None, "updated_at": None}

    def save_schedule(self, schedule_data: Dict[str, Any]):
        """Save schedule to schedule.json."""
        if not self.schedule_file:
            return

        schedule_data["updated_at"] = datetime.now(self.timezone).isoformat()
        if not schedule_data.get("created_at"):
            schedule_data["created_at"] = schedule_data["updated_at"]

        self.schedule_file.write_text(
            json.dumps(schedule_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def create_schedule(self, force: bool = False) -> Dict[str, Any]:
        """
        Create schedule for all posts in the week folder.

        Args:
            force: If True, recreate even if schedule exists

        Returns:
            Schedule data dictionary
        """
        if not self.week_folder or not self.week_folder.exists():
            return {"error": "Week folder not found"}

        # Check existing schedule
        existing = self.load_schedule()
        if existing.get("posts") and not force:
            return {"error": "Schedule already exists. Use force=True to recreate."}

        # Scan for posts
        all_posts = self.scan_week_for_posts()

        # Build schedule data
        schedule_data = {
            "week_folder": self.week_folder.name,
            "timezone": TIMEZONE,
            "created_at": datetime.now(self.timezone).isoformat(),
            "updated_at": None,
            "posts": all_posts,
            "stats": {
                "total_posts": sum(len(posts) for posts in all_posts.values()),
                "platforms": list(all_posts.keys())
            }
        }

        # Save schedule
        self.save_schedule(schedule_data)

        # Create schedule.ready markers for each post
        self._create_schedule_markers(all_posts)

        return schedule_data

    def _create_schedule_markers(self, all_posts: Dict[str, List[Dict]]):
        """Create schedule.ready marker files for scheduled posts."""
        for platform_key, posts in all_posts.items():
            platform_info = get_platforms().get(platform_key, {})
            folder_name = platform_info.get("output_folder", platform_key)
            platform_path = self.week_folder / folder_name

            for post in posts:
                post_path = self.week_folder / post["post_path"]
                if post_path.exists():
                    # Create marker in post's directory or alongside the post
                    marker_path = post_path.parent / f"{post_path.stem}.schedule.ready"
                    marker_data = {
                        "scheduled_at": post.get("scheduled_at"),
                        "platform": platform_key,
                        "status": ScheduleStatus.SCHEDULED.value,
                        "created_at": datetime.now(self.timezone).isoformat()
                    }
                    marker_path.write_text(
                        json.dumps(marker_data, indent=2),
                        encoding="utf-8"
                    )

    def get_due_posts(self) -> List[Dict[str, Any]]:
        """
        Get posts that are due for publishing (scheduled time has passed).

        Returns:
            List of posts ready to publish
        """
        schedule = self.load_schedule()
        now = datetime.now(self.timezone)
        due_posts = []

        for platform_key, posts in schedule.get("posts", {}).items():
            for post in posts:
                if post.get("status") != ScheduleStatus.SCHEDULED.value:
                    continue

                scheduled_at_str = post.get("scheduled_at")
                if not scheduled_at_str:
                    continue

                scheduled_at = datetime.fromisoformat(scheduled_at_str)
                if scheduled_at <= now:
                    post["platform"] = platform_key
                    due_posts.append(post)

        return due_posts

    def get_upcoming_posts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get posts scheduled in the next N hours.

        Args:
            hours: Look ahead window in hours

        Returns:
            List of upcoming posts
        """
        schedule = self.load_schedule()
        now = datetime.now(self.timezone)
        cutoff = now + timedelta(hours=hours)
        upcoming = []

        for platform_key, posts in schedule.get("posts", {}).items():
            for post in posts:
                if post.get("status") != ScheduleStatus.SCHEDULED.value:
                    continue

                scheduled_at_str = post.get("scheduled_at")
                if not scheduled_at_str:
                    continue

                scheduled_at = datetime.fromisoformat(scheduled_at_str)
                if now < scheduled_at <= cutoff:
                    post["platform"] = platform_key
                    upcoming.append(post)

        # Sort by scheduled time
        upcoming.sort(key=lambda x: x.get("scheduled_at", ""))
        return upcoming

    def mark_published(self, post_path: str, platform: str, result: Dict[str, Any]):
        """
        Mark a post as published and update its marker.

        Args:
            post_path: Relative path to the post
            platform: Platform name
            result: Publishing result dictionary
        """
        schedule = self.load_schedule()

        # Update status in schedule.json
        for post in schedule.get("posts", {}).get(platform, []):
            if post.get("post_path") == post_path:
                post["status"] = ScheduleStatus.PUBLISHED.value
                post["published_at"] = datetime.now(self.timezone).isoformat()
                post["publish_result"] = result
                break

        self.save_schedule(schedule)

        # Update marker file
        full_post_path = self.week_folder / post_path
        marker_path = full_post_path.parent / f"{full_post_path.stem}.schedule.ready"
        if marker_path.exists():
            marker_data = json.loads(marker_path.read_text(encoding="utf-8"))
            marker_data["status"] = ScheduleStatus.PUBLISHED.value
            marker_data["published_at"] = datetime.now(self.timezone).isoformat()
            marker_data["publish_result"] = result
            marker_path.write_text(json.dumps(marker_data, indent=2), encoding="utf-8")

            # Also create publish.ready marker
            publish_marker = full_post_path.parent / f"{full_post_path.stem}.publish.ready"
            publish_marker.write_text(
                json.dumps({
                    "published_at": marker_data["published_at"],
                    "platform": platform,
                    "result": result
                }, indent=2),
                encoding="utf-8"
            )

    def mark_failed(self, post_path: str, platform: str, error: str):
        """
        Mark a post as failed.

        Args:
            post_path: Relative path to the post
            platform: Platform name
            error: Error message
        """
        schedule = self.load_schedule()

        for post in schedule.get("posts", {}).get(platform, []):
            if post.get("post_path") == post_path:
                post["status"] = ScheduleStatus.FAILED.value
                post["failed_at"] = datetime.now(self.timezone).isoformat()
                post["error"] = error
                break

        self.save_schedule(schedule)

    def get_schedule_summary(self) -> Dict[str, Any]:
        """Get a summary of the current schedule."""
        schedule = self.load_schedule()

        summary = {
            "week": self.week_folder.name if self.week_folder else None,
            "timezone": TIMEZONE,
            "total": 0,
            "by_status": {},
            "by_platform": {},
            "next_post": None
        }

        now = datetime.now(self.timezone)

        for platform_key, posts in schedule.get("posts", {}).items():
            platform_stats = {"total": 0, "scheduled": 0, "published": 0, "failed": 0}

            for post in posts:
                status = post.get("status", ScheduleStatus.PENDING.value)
                platform_stats["total"] += 1
                platform_stats[status] = platform_stats.get(status, 0) + 1

                # Track next scheduled post
                if status == ScheduleStatus.SCHEDULED.value:
                    scheduled_at_str = post.get("scheduled_at")
                    if scheduled_at_str:
                        scheduled_at = datetime.fromisoformat(scheduled_at_str)
                        if scheduled_at > now:
                            if not summary["next_post"] or scheduled_at < datetime.fromisoformat(summary["next_post"]["scheduled_at"]):
                                summary["next_post"] = {
                                    "post_path": post.get("post_path"),
                                    "platform": platform_key,
                                    "scheduled_at": scheduled_at_str
                                }

            summary["by_platform"][platform_key] = platform_stats
            summary["total"] += platform_stats["total"]

        # Aggregate by status
        for platform_stats in summary["by_platform"].values():
            for status, count in platform_stats.items():
                if status != "total":
                    summary["by_status"][status] = summary["by_status"].get(status, 0) + count

        return summary


def create_week_schedule(week_folder: Path, force: bool = False) -> Dict[str, Any]:
    """
    Convenience function to create schedule for a week.

    Args:
        week_folder: Path to week's output folder
        force: Recreate even if exists

    Returns:
        Schedule data
    """
    scheduler = PostScheduler(week_folder)
    return scheduler.create_schedule(force=force)


def get_due_posts_for_week(week_folder: Path) -> List[Dict[str, Any]]:
    """
    Convenience function to get due posts for a week.

    Args:
        week_folder: Path to week's output folder

    Returns:
        List of due posts
    """
    scheduler = PostScheduler(week_folder)
    return scheduler.get_due_posts()
