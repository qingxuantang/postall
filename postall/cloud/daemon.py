"""
PostAll Cloud Daemon

Main daemon process for 24/7 cloud operation.
Handles:
- Scheduled post checking and publishing
- Weekly content generation (with reminder + cancellation flow)
- Content Director reviews
- Health check server
- Notifications via Discord/Telegram
- Graceful shutdown

Usage:
    python -m src.cloud.daemon          # Run daemon
    python -m src.cloud.daemon --once   # Run single check and exit
"""

import os
import sys
import signal
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import re

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from rich.console import Console
from rich.panel import Panel

from postall.config import (
    TIMEZONE, OUTPUT_DIR,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_BOT_ENABLED,
    GENERATION_ENABLED, GENERATION_DAY, GENERATION_TIME,
    REMINDER_1_DAY, REMINDER_1_TIME, REMINDER_2_DAY, REMINDER_2_TIME,
    get_next_week_folder_name
)
from postall.cloud.database import ScheduleDatabase
from postall.cloud.health import HealthServer
from postall.cloud.notifier import Notifier
from postall.cloud.telegram_bot import TelegramCommandBot
from postall.cloud.generation_controller import GenerationController
from zoneinfo import ZoneInfo

# Day name to cron number mapping
DAY_TO_CRON = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6
}

console = Console()


class CloudDaemon:
    """
    Main cloud daemon for PostAll.

    Runs 24/7 and handles:
    - Checking for due posts every N minutes
    - Publishing posts when their scheduled time arrives
    - Weekly content generation (configurable)
    - Health monitoring
    - Notifications
    """

    def __init__(
        self,
        check_interval_minutes: int = 15,
        health_port: int = 8080,
        db_path: str = "data/schedule.db",
        run_immediately: bool = True
    ):
        """
        Initialize the daemon.

        Args:
            check_interval_minutes: How often to check for due posts
            health_port: Port for health check server
            db_path: Path to SQLite database
            run_immediately: Run a check immediately on startup
        """
        self.check_interval = check_interval_minutes
        self.health_port = health_port
        self.run_immediately = run_immediately
        self.timezone = ZoneInfo(TIMEZONE)

        # Initialize components
        self.db = ScheduleDatabase(db_path)
        self.notifier = Notifier.from_env()
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.health_server: Optional[HealthServer] = None

        # State
        self.start_time = datetime.now(self.timezone)
        self.running = False
        self._stats = {
            'checks_performed': 0,
            'posts_published': 0,
            'posts_failed': 0,
            'last_check': None,
            'last_publish': None,
            'last_generation': None,
            'generations_completed': 0
        }

        # Publishers cache
        self._publishers: Dict[str, Any] = {}

        # Generation controller
        self.generation_controller = GenerationController()

        # Telegram bot
        self.telegram_bot: Optional[TelegramCommandBot] = None
        self._telegram_task: Optional[asyncio.Task] = None

        # Generation state
        self._generation_in_progress = False

    def _get_stats(self) -> Dict[str, Any]:
        """Get current daemon stats for health server."""
        db_stats = self.db.get_today_stats()
        schedule_summary = self.db.get_schedule_summary()

        return {
            'checks_performed': db_stats.get('checks_performed', 0),
            'posts_published': db_stats.get('posts_published', 0),
            'posts_failed': db_stats.get('posts_failed', 0),
            'posts_scheduled': schedule_summary.get('by_status', {}).get('scheduled', 0),
            'last_check': self._stats.get('last_check'),
            'next_post': schedule_summary.get('next_post')
        }

    def _get_publisher_status(self) -> Dict[str, str]:
        """Get publisher status for health server."""
        status = {}

        for platform in ['twitter', 'pinterest', 'linkedin', 'instagram', 'threads', 'wechat']:
            try:
                publisher = self._get_publisher(platform)
                if publisher and publisher.is_configured:
                    status[platform] = 'ready'
                else:
                    status[platform] = 'not_configured'
            except Exception as e:
                status[platform] = f'error: {str(e)[:30]}'

        return status

    def _get_publisher(self, platform: str):
        """Get or create publisher for a platform."""
        if platform in self._publishers:
            return self._publishers[platform]

        try:
            if platform == 'twitter':
                from postall.publishers.twitter_publisher import TwitterPublisher
                self._publishers[platform] = TwitterPublisher()
            elif platform == 'pinterest':
                from postall.publishers.pinterest_publisher import PinterestPublisher
                self._publishers[platform] = PinterestPublisher()
            elif platform == 'linkedin':
                from postall.publishers.linkedin_publisher import LinkedInPublisher
                self._publishers[platform] = LinkedInPublisher()
            elif platform == 'instagram':
                from postall.publishers.instagram_publisher import InstagramPublisher
                self._publishers[platform] = InstagramPublisher()
            elif platform == 'threads':
                from postall.publishers.threads_publisher import ThreadsPublisher
                self._publishers[platform] = ThreadsPublisher()
            elif platform == 'wechat':
                from postall.publishers.wechat_publisher import WeChatPublisher
                self._publishers[platform] = WeChatPublisher()
            else:
                return None
        except ImportError:
            return None

        return self._publishers.get(platform)

    async def _check_and_publish(self):
        """Check for due posts and publish them."""
        now = datetime.now(self.timezone)
        self._stats['last_check'] = now.isoformat()
        self._stats['checks_performed'] += 1

        console.print(f"\n[cyan]{'='*50}[/cyan]")
        console.print(f"[bold]Check: {now.strftime('%Y-%m-%d %H:%M:%S')}[/bold]")
        console.print(f"[cyan]{'='*50}[/cyan]")

        # Import any new schedules from JSON files
        await self._import_new_schedules()

        # Get due posts from database
        due_posts = self.db.get_due_posts()

        if not due_posts:
            console.print("[dim]No posts due[/dim]")
            self.db.record_check(published=0, failed=0)
            return

        console.print(f"[yellow]Found {len(due_posts)} post(s) due[/yellow]")

        published = 0
        failed = 0

        for post in due_posts:
            post_id = post['id']
            platform = post['platform']
            post_path = post['post_path']
            week_folder = post['week_folder']

            console.print(f"\n  Processing: {platform} - {post_path}")

            # Get publisher
            publisher = self._get_publisher(platform)
            if not publisher or not publisher.is_configured:
                console.print(f"    [yellow]Skipped: {platform} not configured[/yellow]")
                continue

            # Read post content
            full_path = OUTPUT_DIR / week_folder / post_path
            if not full_path.exists():
                error = f"File not found: {full_path}"
                console.print(f"    [red]Error: {error}[/red]")
                self.db.mark_failed(post_id, error)
                failed += 1
                await self.notifier.notify_failed(platform, error, post_path)
                continue

            try:
                content = full_path.read_text(encoding="utf-8")

                # Extract post content
                post_content = self._extract_post_content(content, platform)

                # Find images for platforms that support them
                local_image_paths = self._find_post_images(post_path, week_folder, platform)

                # Platform-specific publishing
                if platform == 'instagram':
                    # Instagram requires public URLs (uses media server)
                    if local_image_paths:
                        is_carousel = len(local_image_paths) > 1
                        result = publisher.publish_local_images(
                            content=post_content,
                            local_image_paths=local_image_paths,
                            is_carousel=is_carousel
                        )
                    else:
                        result = {
                            'success': False,
                            'error': "Instagram requires images but none found in assets folder"
                        }
                elif platform in ['twitter', 'linkedin', 'pinterest', 'threads']:
                    # These platforms support direct image upload
                    if local_image_paths:
                        result = publisher.publish(post_content, media_paths=local_image_paths)
                    else:
                        # Publish without images (text only)
                        result = publisher.publish(post_content)
                else:
                    # Other platforms (reddit, substack, etc.) - text only for now
                    result = publisher.publish(post_content)

                if result.get('success'):
                    console.print(f"    [green]Published![/green]")
                    self.db.mark_published(post_id, result)
                    published += 1
                    self._stats['posts_published'] += 1
                    self._stats['last_publish'] = now.isoformat()

                    await self.notifier.notify_published(
                        platform,
                        post_content[:100],
                        result.get('url')
                    )
                else:
                    error = result.get('error', 'Unknown error')
                    console.print(f"    [red]Failed: {error}[/red]")
                    self.db.mark_failed(post_id, error)
                    failed += 1
                    self._stats['posts_failed'] += 1

                    await self.notifier.notify_failed(platform, error, post_path)

            except Exception as e:
                error = str(e)
                console.print(f"    [red]Exception: {error}[/red]")
                self.db.mark_failed(post_id, error)
                failed += 1
                self._stats['posts_failed'] += 1

                await self.notifier.notify_failed(platform, error, post_path)

        # Record stats
        self.db.record_check(published=published, failed=failed)

        console.print(f"\n[bold]Results:[/bold] Published: {published}, Failed: {failed}")

    def _extract_post_content(self, content: str, platform: str = None) -> str:
        """
        Extract the actual post content from markdown file.

        Handles platform-specific content structures:
        - Twitter: **Text:** section
        - LinkedIn: **Post Text:** section
        - Instagram: ### Caption: section
        - Thread: **Thread Text:** or **Post Text:**
        - Other: Generic patterns
        """
        # Platform-specific extraction patterns
        if platform == 'twitter':
            # Extract text between **Text:** and **Character Count:** or ## Image Prompt
            match = re.search(
                r'\*\*Text:\*\*\s*\n(.+?)(?:\n\*\*Character Count:|## Image Prompt|---\s*$)',
                content,
                re.DOTALL
            )
            if match:
                return match.group(1).strip()

        elif platform == 'linkedin':
            # Extract text between **Post Text:** and ## Image Prompt or hashtags line
            # LinkedIn supports long-form posts up to 3000 chars
            match = re.search(
                r'\*\*Post Text:\*\*\s*\n(.+?)(?:## Image Prompt|^---\s*$)',
                content,
                re.DOTALL
            )
            if match:
                return match.group(1).strip()[:3000]

        elif platform == 'instagram':
            # Extract caption + hashtags for Instagram
            # First try: caption + hashtags together
            match = re.search(
                r'### Caption:\s*\n(.+?)(?:### Carousel Text|### Image Prompt|## Image Prompt|---\s*$)',
                content,
                re.DOTALL
            )
            if match:
                caption_block = match.group(1).strip()
                # Instagram caption should include hashtags
                return caption_block
            # Fallback: caption only (without hashtags section)
            match = re.search(
                r'### Caption:\s*\n(.+?)(?:\n\*\*Hashtags:|## Image Prompt)',
                content,
                re.DOTALL
            )
            if match:
                caption = match.group(1).strip()
                # Try to find and append hashtags
                hashtag_match = re.search(r'\*\*Hashtags?:\*\*\s*(.+?)(?:\n\n|\n###|## Image Prompt|$)', content, re.DOTALL)
                if hashtag_match:
                    hashtags = hashtag_match.group(1).strip()
                    return f"{caption}\n\n.\n.\n.\n{hashtags}"
                return caption

        elif platform == 'thread':
            # Extract thread text
            match = re.search(
                r'\*\*(?:Thread Text|Post Text):\*\*\s*\n(.+?)(?:## Image Prompt|---\s*$)',
                content,
                re.DOTALL
            )
            if match:
                return match.group(1).strip()

        # Generic fallback patterns (for other platforms or old formats)
        generic_patterns = [
            r'### Caption:\s*\n(.+?)(?:\n\*\*Hashtags:|## Image Prompt)',  # Instagram alt
            r'\*\*Post Text:\*\*\s*\n(.+?)(?:## Image Prompt)',  # LinkedIn alt
            r'\*\*Text:\*\*\s*\n(.+?)(?:\n\*\*Character Count:|## Image Prompt)',  # Twitter alt
            r'## Caption\n\n(.+?)(?:\n---|\n## )',  # Old Instagram format
            r'## (?:Tweet |Post )?Content\n\n(.+?)(?:\n---|\n## )',  # Old generic format
        ]

        for pattern in generic_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Last resort: use content after first --- but before ## Image Prompt
        # LinkedIn supports up to 3000 chars; other platforms use 1000
        char_limit = 3000 if platform == 'linkedin' else 1000
        parts = content.split("---")
        if len(parts) > 1:
            # Get content after first ---, but before ## Image Prompt
            text = parts[1]
            if '## Image Prompt' in text:
                text = text.split('## Image Prompt')[0]
            if '### Image Prompt' in text:
                text = text.split('### Image Prompt')[0]
            
            # Strip metadata lines that shouldn't appear in published content
            lines = text.strip().split('\n')
            clean_lines = []
            for line in lines:
                stripped = line.strip()
                # Skip markdown headers (## Monday Post, etc.)
                if stripped.startswith('## '):
                    continue
                # Skip metadata lines
                if stripped.startswith('**Posting Time:**'):
                    continue
                if stripped.startswith('**Content Pillar:**'):
                    continue
                if stripped.startswith('**Post Type:**'):
                    continue
                if stripped.startswith('**Theme:**'):
                    continue
                clean_lines.append(line)
            
            text = '\n'.join(clean_lines).strip()
            
            # For Twitter threads: remove thread numbering (1/, 2/, etc.)
            # The publisher adds its own numbering format
            if platform == 'twitter':
                # Split by thread markers first to preserve tweet boundaries
                thread_parts = re.split(r'\n(?=\d+/\s)', text)
                clean_parts = []
                for part in thread_parts:
                    # Remove the numbering prefix
                    part = re.sub(r'^\d+/\s*', '', part.strip())
                    if part:
                        clean_parts.append(part)
                if clean_parts:
                    text = '\n\n'.join(clean_parts)
            
            return text.strip()[:char_limit]

        return content[:char_limit]

    def _find_post_images(self, post_path: str, week_folder: str, platform: str) -> list:
        """
        Find images for a post from its assets folder.

        Different platforms have different naming conventions:
        - Instagram/LinkedIn/Thread/Substack: 01_assets, 02_assets (numbered prefix)
        - X/Twitter: Two formats supported:
          - New format: 01_assets, 02_assets (numbered prefix like other platforms)
          - Legacy format: monday_assets (day-based), but filters by morning/afternoon
        - Pinterest: pin_assets (specific name)

        Args:
            post_path: Path to the post file (e.g., instagram-posts/01_monday_educational.md)
            week_folder: Week folder name (e.g., 2026-01-12_week3)
            platform: Platform name

        Returns:
            List of absolute image file paths
        """
        full_path = OUTPUT_DIR / week_folder / post_path
        post_filename = Path(post_path).stem
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
        local_image_paths = []
        assets_folder = None
        image_filter = None  # For filtering specific images (e.g., morning/afternoon for Twitter, pin_01 for Pinterest)

        if platform == "twitter":
            # First try numbered prefix format (new style: 01_monday_tweet_1.md -> 01_assets/)
            post_prefix = post_filename.split("_")[0]
            if post_prefix.isdigit():
                numbered_assets = full_path.parent / f"{post_prefix}_assets"
                if numbered_assets.exists():
                    assets_folder = numbered_assets

            # Fallback to day-based format (legacy: monday_morning.md -> monday_assets/)
            if not assets_folder:
                day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                for day in day_names:
                    if day in post_filename.lower():
                        day_assets = full_path.parent / f"{day}_assets"
                        if day_assets.exists():
                            assets_folder = day_assets
                            # Determine time filter (morning/afternoon/evening)
                            # This ensures monday_morning.md only gets monday_morning*.png
                            if 'morning' in post_filename.lower():
                                image_filter = 'morning'
                            elif 'afternoon' in post_filename.lower():
                                image_filter = 'afternoon'
                            elif 'evening' in post_filename.lower():
                                image_filter = 'evening'
                        break
        elif platform == "pinterest":
            # First try numbered prefix format (new style: 01_monday_howto.md -> 01_assets/)
            post_prefix = post_filename.split("_")[0]
            if post_prefix.isdigit():
                numbered_assets = full_path.parent / f"{post_prefix}_assets"
                if numbered_assets.exists():
                    assets_folder = numbered_assets
            # Fallback to pin_assets (legacy: pin_01_howto.md -> pin_assets/)
            # Extract pin number to filter images (e.g., pin_01 -> pin_01_*.png)
            if not assets_folder:
                pin_assets = full_path.parent / "pin_assets"
                if pin_assets.exists():
                    assets_folder = pin_assets
                    # Extract pin prefix for filtering (e.g., "pin_01_howto" -> "pin_01")
                    pin_match = re.match(r'(pin_\d+)', post_filename.lower())
                    if pin_match:
                        image_filter = pin_match.group(1)  # Reuse the filter variable
        else:
            # Instagram, LinkedIn, Thread, Reddit, Substack use numbered prefix
            post_prefix = post_filename.split("_")[0]
            if post_prefix.isdigit():
                assets_folder = full_path.parent / f"{post_prefix}_assets"

        if assets_folder and assets_folder.exists():
            for img_file in sorted(assets_folder.iterdir()):
                if img_file.suffix.lower() in image_extensions:
                    # For Twitter with day-based folders, filter by time of day
                    if image_filter:
                        # Only include images that match the time filter
                        # e.g., monday_morning.md should only get monday_morning*.png
                        if image_filter in img_file.stem.lower():
                            local_image_paths.append(str(img_file))
                    else:
                        local_image_paths.append(str(img_file))
            if local_image_paths:
                console.print(f"    [dim]Found {len(local_image_paths)} images in {assets_folder.name}[/dim]")

        return local_image_paths

    async def _import_new_schedules(self):
        """Import any new schedule.json files to database."""
        if not OUTPUT_DIR.exists():
            return

        # Find week folders
        week_pattern = re.compile(r'\d{4}-\d{2}-\d{2}_week\d+')

        for folder in OUTPUT_DIR.iterdir():
            if folder.is_dir() and week_pattern.match(folder.name):
                schedule_file = folder / "schedule.json"
                if schedule_file.exists():
                    # Check if this specific week folder has already been imported
                    try:
                        with self.db._get_connection() as conn:
                            cursor = conn.execute(
                                "SELECT COUNT(*) FROM scheduled_posts WHERE week_folder = ?",
                                (folder.name,)
                            )
                            existing_count = cursor.fetchone()[0]
                    except Exception:
                        existing_count = 0

                    if existing_count == 0:
                        imported = self.db.import_from_json_schedule(folder)
                        if imported > 0:
                            console.print(f"[cyan]Imported {imported} posts from {folder.name}[/cyan]")

    async def _heartbeat(self):
        """Periodic heartbeat log."""
        now = datetime.now(self.timezone)
        uptime = now - self.start_time
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)

        stats = self._get_stats()

        console.print(
            f"[dim]♥ {now.strftime('%H:%M')} | "
            f"Uptime: {hours}h {minutes}m | "
            f"Checks: {stats['checks_performed']} | "
            f"Published: {stats['posts_published']} | "
            f"Failed: {stats['posts_failed']}[/dim]"
        )

    async def _daily_summary(self):
        """Send daily summary notification."""
        stats = self._get_stats()
        await self.notifier.notify_daily_summary(stats)
        console.print("[cyan]Daily summary sent[/cyan]")

    # ==========================================
    # CONTENT GENERATION METHODS
    # ==========================================

    async def _generation_reminder(self, reminder_num: int = 1):
        """
        Send generation reminder before scheduled generation.

        Args:
            reminder_num: 1 for first reminder (day before), 2 for second reminder (same day)

        Sends a Telegram message with cancel option.
        """
        console.print(f"\n[cyan]{'='*50}[/cyan]")
        console.print(f"[bold]Generation Reminder #{reminder_num}[/bold]")
        console.print(f"[cyan]{'='*50}[/cyan]")

        # Check if content already exists
        status = self.generation_controller.check_content_status()
        week_folder = status['week_folder']

        if status['exists']:
            console.print(f"[green]Content already exists for {week_folder}[/green]")
            console.print("[dim]Skipping generation reminder[/dim]")

            # Still notify user that generation will be skipped
            if self.telegram_bot:
                await self.telegram_bot._send_message(
                    self.telegram_bot.authorized_chat_id,
                    f"✅ <b>Content Check Complete</b>\n\n"
                    f"Week: {week_folder}\n"
                    f"All content already exists.\n\n"
                    f"Scheduled generation will be skipped."
                )
            return

        # Determine what needs to be generated
        missing_platforms = status['missing_platforms']
        existing_platforms = status['existing_platforms']

        if status['partial']:
            console.print(f"[yellow]Partial content found for {week_folder}[/yellow]")
            console.print(f"  Existing: {', '.join(existing_platforms)}")
            console.print(f"  Missing: {', '.join(missing_platforms)}")
        else:
            console.print(f"[yellow]No content found for {week_folder}[/yellow]")

        # Send reminder via Telegram with different messages based on reminder number
        if self.telegram_bot:
            generation_time = f"{GENERATION_DAY.capitalize()} {GENERATION_TIME}"

            if reminder_num == 1:
                # First reminder - 3 hours before
                reminder_label = "📅 Content Generation Reminder"
                time_until = f"in 3 hours at {GENERATION_TIME}"
            else:
                # Second reminder - 1 hour before
                reminder_label = "⏰ Final Reminder"
                time_until = f"in 1 hour at {GENERATION_TIME}"

            await self.telegram_bot.send_generation_reminder(
                week_folder=week_folder,
                missing_platforms=missing_platforms,
                generation_time=generation_time,
                reminder_label=reminder_label,
                time_until=time_until
            )
            console.print(f"[green]Reminder #{reminder_num} sent via Telegram[/green]")
        else:
            console.print("[yellow]Telegram bot not available, proceeding without reminder[/yellow]")

    async def _weekly_content_generation(self):
        """
        Execute weekly content generation.

        Called at GENERATION_TIME on GENERATION_DAY.
        Checks if user cancelled, then generates content.
        """
        console.print("\n[cyan]{'='*50}[/cyan]")
        console.print("[bold]Weekly Content Generation[/bold]")
        console.print(f"[cyan]{'='*50}[/cyan]")

        # Check if user cancelled via Telegram
        if self.telegram_bot and self.telegram_bot.is_generation_cancelled():
            console.print("[yellow]Generation cancelled by user[/yellow]")
            self.telegram_bot.reset_generation_state()

            await self.notifier.send_notification(
                "Content Generation Skipped",
                "Weekly generation was cancelled by user."
            )
            return

        # Check if content already exists
        status = self.generation_controller.check_content_status()

        if status['exists']:
            console.print(f"[green]Content already exists for {status['week_folder']}[/green]")
            console.print("[dim]Skipping generation[/dim]")

            if self.telegram_bot:
                self.telegram_bot.reset_generation_state()
            return

        # Prevent concurrent generation
        if self._generation_in_progress:
            console.print("[yellow]Generation already in progress, skipping[/yellow]")
            return

        # Execute generation
        await self._execute_generation(force=False)

    async def _trigger_generation(self, force: bool = False) -> Dict[str, Any]:
        """
        Trigger content generation (called from Telegram bot).

        Args:
            force: If True, regenerate all platforms even if content exists

        Returns:
            Generation result dictionary
        """
        return await self._execute_generation(force=force)

    async def _cancel_generation(self):
        """Cancel pending generation (called from Telegram bot)."""
        if self.telegram_bot:
            self.telegram_bot._generation_cancelled = True
            console.print("[yellow]Generation cancelled by user[/yellow]")

    async def _regenerate_post(self, platform: str, week_folder: str) -> Dict[str, Any]:
        """
        Regenerate content for a specific platform and re-run Director review.

        Called from Telegram bot escalation buttons.

        Args:
            platform: Platform key to regenerate
            week_folder: Week folder name

        Returns:
            Regeneration result dictionary
        """
        console.print(f"\n[cyan]Regenerating {platform} for {week_folder}[/cyan]")

        try:
            result = await self.generation_controller.regenerate_platform(
                platform=platform,
                week_folder=week_folder
            )

            if result.get('success'):
                console.print(f"[green]Regeneration successful for {platform}[/green]")
            else:
                errors = result.get('errors', [])
                console.print(f"[red]Regeneration failed: {errors}[/red]")

            return result

        except Exception as e:
            console.print(f"[red]Regeneration error: {e}[/red]")
            return {
                'success': False,
                'errors': [str(e)],
                'platform': platform,
                'week_folder': week_folder
            }

    async def _generate_images_for_approved(
        self,
        week_folder: str,
        approved_posts: list
    ) -> Dict[str, Any]:
        """
        Generate images for manually approved posts (called from Telegram bot).

        Args:
            week_folder: Week folder name
            approved_posts: List of dicts with 'post_path' and 'platform'

        Returns:
            Image generation result dict
        """
        console.print(f"\n[cyan]Generating images for {len(approved_posts)} approved posts in {week_folder}[/cyan]")

        try:
            result = await self.generation_controller._generate_images_for_approved_posts(
                week_folder, approved_posts
            )
            generated = result.get('generated', 0)
            failed = result.get('failed', 0)
            console.print(f"[green]Image generation complete: {generated} generated, {failed} failed[/green]")
            return result
        except Exception as e:
            console.print(f"[red]Image generation error: {e}[/red]")
            return {'success': False, 'generated': 0, 'failed': 0, 'error': str(e)}

    async def _execute_generation(self, force: bool = False) -> Dict[str, Any]:
        """
        Execute the actual content generation.

        Args:
            force: If True, regenerate all platforms

        Returns:
            Generation result dictionary
        """
        self._generation_in_progress = True
        now = datetime.now(self.timezone)

        console.print(f"[cyan]Starting content generation at {now.strftime('%H:%M:%S')}[/cyan]")

        # Notify generation started
        week_folder = get_next_week_folder_name()

        if self.telegram_bot:
            await self.telegram_bot.send_generation_started(week_folder)

        await self.notifier.send_notification(
            "Content Generation Started",
            f"Generating content for week {week_folder}"
        )

        try:
            # Run generation
            result = await self.generation_controller.generate_weekly_content(force=force)

            # Update stats
            self._stats['last_generation'] = now.isoformat()
            if result.get('success'):
                self._stats['generations_completed'] += 1

            # Log result
            if result.get('success'):
                console.print(f"[green]Generation completed successfully[/green]")
                console.print(f"  Generated: {', '.join(result.get('platforms_generated', []))}")
                if result.get('platforms_skipped'):
                    console.print(f"  Skipped: {', '.join(result['platforms_skipped'])}")
            else:
                console.print(f"[red]Generation completed with errors[/red]")
                for error in result.get('errors', []):
                    console.print(f"  [red]{error}[/red]")

            # Notify completion via Telegram
            if self.telegram_bot:
                await self.telegram_bot._send_generation_result(
                    self.telegram_bot.authorized_chat_id,
                    result
                )

                # Send Director review escalation notification if there are flagged posts
                director_review = result.get('director_review_result', {})
                if director_review.get('success'):
                    # Notify if there are escalations OR if avg score is still low after retries
                    has_escalations = bool(director_review.get('escalations'))
                    avg_score = director_review.get('avg_score', 10)
                    auto_retries = result.get('auto_regen_attempts', 0)

                    if has_escalations or avg_score < 7.0:
                        await self.telegram_bot.send_director_review_result(
                            week_folder=result.get('week_folder', ''),
                            review_result=director_review,
                            auto_regen_attempts=auto_retries
                        )

                self.telegram_bot.reset_generation_state()

            # Notify via Discord/other channels
            if result.get('success'):
                await self.notifier.send_notification(
                    "Content Generation Complete",
                    f"Week: {result.get('week_folder')}\n"
                    f"Generated: {len(result.get('platforms_generated', []))} platforms\n"
                    f"Duration: {result.get('generation_time')}"
                )
            else:
                await self.notifier.send_notification(
                    "Content Generation Failed",
                    f"Week: {result.get('week_folder')}\n"
                    f"Errors: {len(result.get('errors', []))}\n"
                    f"Check logs for details."
                )

            return result

        except Exception as e:
            console.print(f"[red]Generation error: {e}[/red]")

            if self.telegram_bot:
                await self.telegram_bot._send_message(
                    self.telegram_bot.authorized_chat_id,
                    f"❌ <b>Generation Error</b>\n\n{str(e)[:200]}"
                )
                self.telegram_bot.reset_generation_state()

            await self.notifier.send_notification(
                "Content Generation Error",
                f"Error: {str(e)[:200]}"
            )

            return {
                'success': False,
                'errors': [str(e)],
                'week_folder': week_folder
            }

        finally:
            self._generation_in_progress = False

    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        def signal_handler(signum, frame):
            console.print("\n[yellow]Shutdown signal received...[/yellow]")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start(self):
        """Start the daemon."""
        self._setup_signal_handlers()
        self.running = True

        console.print(Panel.fit(
            "[bold magenta]PostAll Cloud Daemon[/bold magenta]\n"
            "24/7 Scheduled Post Publishing\n"
            f"[dim]Check interval: {self.check_interval} minutes[/dim]"
        ))

        console.print(f"\n[cyan]Configuration:[/cyan]")
        console.print(f"  Timezone: {TIMEZONE}")
        console.print(f"  Database: {self.db.db_path}")
        console.print(f"  Health port: {self.health_port}")
        console.print(f"  Check interval: {self.check_interval} minutes")

        # Show publisher status
        console.print(f"\n[cyan]Publisher Status:[/cyan]")
        for platform, status in self._get_publisher_status().items():
            color = 'green' if status == 'ready' else 'yellow'
            console.print(f"  [{color}]{'✓' if status == 'ready' else '⚠'}[/] {platform}: {status}")

        # Start health server
        self.health_server = HealthServer(
            port=self.health_port,
            stats_callback=self._get_stats,
            publishers_callback=self._get_publisher_status
        )
        self.health_server.start()
        console.print(f"\n[green]Health server started on port {self.health_port}[/green]")

        # Start Telegram command bot
        if TELEGRAM_BOT_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            self.telegram_bot = TelegramCommandBot(
                bot_token=TELEGRAM_BOT_TOKEN,
                authorized_chat_id=TELEGRAM_CHAT_ID,
                database=self.db,
                stats_callback=self._get_stats,
                check_callback=self._check_and_publish,
                generation_callback=self._trigger_generation,
                cancel_generation_callback=self._cancel_generation,
                regenerate_callback=self._regenerate_post,
                approve_images_callback=self._generate_images_for_approved
            )
            self._telegram_task = asyncio.create_task(self.telegram_bot.start())
            console.print(f"[green]Telegram command bot started[/green]")
        else:
            console.print(f"[yellow]Telegram bot disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)[/yellow]")

        # Create scheduler
        self.scheduler = AsyncIOScheduler(timezone=TIMEZONE)

        # Add check job
        self.scheduler.add_job(
            self._check_and_publish,
            IntervalTrigger(minutes=self.check_interval),
            id='check_publish',
            name='Check and Publish Due Posts',
            replace_existing=True
        )

        # Add heartbeat job (every 30 minutes)
        self.scheduler.add_job(
            self._heartbeat,
            CronTrigger(minute='0,30'),
            id='heartbeat',
            name='Heartbeat',
            replace_existing=True
        )

        # Add daily summary job (9 PM)
        daily_summary_time = os.getenv('DAILY_SUMMARY_TIME', '21:00')
        hour, minute = map(int, daily_summary_time.split(':'))
        self.scheduler.add_job(
            self._daily_summary,
            CronTrigger(hour=hour, minute=minute),
            id='daily_summary',
            name='Daily Summary',
            replace_existing=True
        )

        # Add weekly content generation jobs
        if GENERATION_ENABLED:
            gen_hour, gen_minute = map(int, GENERATION_TIME.split(':'))
            gen_day = DAY_TO_CRON.get(GENERATION_DAY, 5)  # Default to Saturday

            # Reminder 1: Day before (e.g., Friday 17:00)
            r1_hour, r1_minute = map(int, REMINDER_1_TIME.split(':'))
            r1_day = DAY_TO_CRON.get(REMINDER_1_DAY, 4)  # Default to Friday

            self.scheduler.add_job(
                lambda: asyncio.create_task(self._generation_reminder(reminder_num=1)),
                CronTrigger(day_of_week=r1_day, hour=r1_hour, minute=r1_minute),
                id='generation_reminder_1',
                name='Content Generation Reminder 1 (Day Before)',
                replace_existing=True
            )

            # Reminder 2: Same day, earlier (e.g., Saturday 10:00)
            r2_hour, r2_minute = map(int, REMINDER_2_TIME.split(':'))
            r2_day = DAY_TO_CRON.get(REMINDER_2_DAY, 5)  # Default to Saturday

            self.scheduler.add_job(
                lambda: asyncio.create_task(self._generation_reminder(reminder_num=2)),
                CronTrigger(day_of_week=r2_day, hour=r2_hour, minute=r2_minute),
                id='generation_reminder_2',
                name='Content Generation Reminder 2 (Same Day)',
                replace_existing=True
            )

            # Add generation job (e.g., Saturday 12:00)
            self.scheduler.add_job(
                self._weekly_content_generation,
                CronTrigger(day_of_week=gen_day, hour=gen_hour, minute=gen_minute),
                id='weekly_generation',
                name='Weekly Content Generation',
                replace_existing=True
            )

            console.print(f"\n[cyan]Content Generation Schedule:[/cyan]")
            console.print(f"  Reminder 1: {REMINDER_1_DAY.capitalize()} {REMINDER_1_TIME}")
            console.print(f"  Reminder 2: {REMINDER_2_DAY.capitalize()} {REMINDER_2_TIME}")
            console.print(f"  Generation: {GENERATION_DAY.capitalize()} {GENERATION_TIME}")
        else:
            console.print(f"\n[yellow]Content generation disabled[/yellow]")

        self.scheduler.start()

        # Show next check time
        job = self.scheduler.get_job('check_publish')
        if job and job.next_run_time:
            console.print(f"\n[cyan]Next check:[/cyan] {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Run immediately if requested
        if self.run_immediately:
            console.print("\n[cyan]Running initial check...[/cyan]")
            await self._check_and_publish()

        # Notify daemon started
        await self.notifier.notify_daemon_started()

        console.print("\n[green]Daemon started successfully![/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")

        # Run until stopped
        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            await self.stop()

    async def stop(self):
        """Stop the daemon gracefully."""
        console.print("\n[yellow]Stopping daemon...[/yellow]")

        # Stop Telegram bot
        if self.telegram_bot:
            await self.telegram_bot.stop()
            if self._telegram_task:
                self._telegram_task.cancel()

        # Stop scheduler
        if self.scheduler:
            self.scheduler.shutdown(wait=False)

        # Stop health server
        if self.health_server:
            self.health_server.stop()

        # Send stop notification
        await self.notifier.notify_daemon_stopped(self._get_stats())

        # Close notifier
        await self.notifier.close()

        console.print(Panel(
            f"[bold]Daemon Stopped[/bold]\n\n"
            f"Total checks: {self._stats['checks_performed']}\n"
            f"Posts published: {self._stats['posts_published']}\n"
            f"Posts failed: {self._stats['posts_failed']}",
            title="Session Summary"
        ))

    async def run_once(self):
        """Run a single check and exit."""
        console.print("[cyan]Running single check...[/cyan]")
        await self._check_and_publish()
        console.print("[green]Done.[/green]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='PostAll Cloud Daemon')
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run single check and exit'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=int(os.getenv('CHECK_INTERVAL_MINUTES', '15')),
        help='Check interval in minutes (default: 15)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('HEALTH_CHECK_PORT', '8080')),
        help='Health check port (default: 8080)'
    )
    parser.add_argument(
        '--db',
        type=str,
        default=os.getenv('SCHEDULE_DB_PATH', 'data/schedule.db'),
        help='Database path (default: data/schedule.db)'
    )
    parser.add_argument(
        '--no-immediate',
        action='store_true',
        help='Skip immediate check on startup'
    )

    args = parser.parse_args()

    daemon = CloudDaemon(
        check_interval_minutes=args.interval,
        health_port=args.port,
        db_path=args.db,
        run_immediately=not args.no_immediate
    )

    if args.once:
        asyncio.run(daemon.run_once())
    else:
        asyncio.run(daemon.start())


if __name__ == '__main__':
    main()
