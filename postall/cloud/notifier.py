"""
Notification Service for PostAll Cloud

Supports:
- Discord webhooks
- Telegram bot messages
- Email (future)

Notification events:
- Post published
- Post failed
- Content generated
- Token expiring
- System error
- Daily summary
"""

import os
import json
import httpx
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from postall.config import TIMEZONE
from zoneinfo import ZoneInfo


class NotificationEvent(Enum):
    """Types of notification events."""
    POST_PUBLISHED = "post_published"
    POST_FAILED = "post_failed"
    CONTENT_GENERATED = "content_generated"
    TOKEN_EXPIRING = "token_expiring"
    SYSTEM_ERROR = "system_error"
    DAILY_SUMMARY = "daily_summary"
    DAEMON_STARTED = "daemon_started"
    DAEMON_STOPPED = "daemon_stopped"


@dataclass
class NotificationConfig:
    """Notification configuration."""
    enabled: bool = False
    discord_webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    notify_on_publish: bool = True
    notify_on_error: bool = True
    daily_summary_enabled: bool = True

    @classmethod
    def from_env(cls) -> 'NotificationConfig':
        """Create config from environment variables."""
        return cls(
            enabled=os.getenv('NOTIFICATIONS_ENABLED', 'false').lower() == 'true',
            discord_webhook_url=os.getenv('DISCORD_WEBHOOK_URL'),
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            notify_on_publish=os.getenv('NOTIFY_ON_PUBLISH', 'true').lower() == 'true',
            notify_on_error=os.getenv('NOTIFY_ON_ERROR', 'true').lower() == 'true',
            daily_summary_enabled=os.getenv('DAILY_SUMMARY_ENABLED', 'true').lower() == 'true',
        )


class Notifier:
    """
    Multi-channel notification service.

    Usage:
        notifier = Notifier.from_env()
        await notifier.notify_published("twitter", "Great post!", "https://twitter.com/...")
    """

    def __init__(self, config: NotificationConfig):
        """Initialize notifier with config."""
        self.config = config
        self._client = httpx.AsyncClient(timeout=10.0)

    @classmethod
    def from_env(cls) -> 'Notifier':
        """Create notifier from environment variables."""
        return cls(NotificationConfig.from_env())

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    # ==========================================
    # HIGH-LEVEL NOTIFICATION METHODS
    # ==========================================

    async def notify_published(
        self,
        platform: str,
        content_preview: str,
        url: Optional[str] = None
    ):
        """Notify that a post was published."""
        if not self.config.enabled or not self.config.notify_on_publish:
            return

        message = self._format_published_message(platform, content_preview, url)
        await self._send_all(message, NotificationEvent.POST_PUBLISHED)

    async def notify_failed(
        self,
        platform: str,
        error: str,
        post_path: Optional[str] = None
    ):
        """Notify that a post failed to publish."""
        if not self.config.enabled or not self.config.notify_on_error:
            return

        message = self._format_failed_message(platform, error, post_path)
        await self._send_all(message, NotificationEvent.POST_FAILED)

    async def notify_content_generated(
        self,
        week_folder: str,
        platforms: List[str],
        post_count: int
    ):
        """Notify that content was generated."""
        if not self.config.enabled:
            return

        message = self._format_generated_message(week_folder, platforms, post_count)
        await self._send_all(message, NotificationEvent.CONTENT_GENERATED)

    async def notify_token_expiring(
        self,
        platform: str,
        expires_in_days: int
    ):
        """Notify that a token is expiring soon."""
        if not self.config.enabled or not self.config.notify_on_error:
            return

        message = self._format_token_expiring_message(platform, expires_in_days)
        await self._send_all(message, NotificationEvent.TOKEN_EXPIRING)

    async def notify_error(
        self,
        error: str,
        context: Optional[str] = None
    ):
        """Notify of a system error."""
        if not self.config.enabled or not self.config.notify_on_error:
            return

        message = self._format_error_message(error, context)
        await self._send_all(message, NotificationEvent.SYSTEM_ERROR)

    async def notify_daily_summary(
        self,
        stats: Dict[str, Any]
    ):
        """Send daily summary notification."""
        if not self.config.enabled or not self.config.daily_summary_enabled:
            return

        message = self._format_daily_summary(stats)
        await self._send_all(message, NotificationEvent.DAILY_SUMMARY)

    async def notify_daemon_started(self):
        """Notify that daemon has started."""
        if not self.config.enabled:
            return

        now = datetime.now(ZoneInfo(TIMEZONE))
        message = {
            'title': 'PostAll Daemon Started',
            'description': f'Daemon is now running and monitoring scheduled posts.',
            'color': 0x00FF00,  # Green
            'timestamp': now.isoformat(),
            'fields': [
                {'name': 'Status', 'value': 'Running', 'inline': True},
                {'name': 'Time', 'value': now.strftime('%Y-%m-%d %H:%M:%S'), 'inline': True},
            ]
        }
        await self._send_all(message, NotificationEvent.DAEMON_STARTED)

    async def notify_daemon_stopped(self, stats: Dict[str, Any]):
        """Notify that daemon has stopped."""
        if not self.config.enabled:
            return

        now = datetime.now(ZoneInfo(TIMEZONE))
        message = {
            'title': 'PostAll Daemon Stopped',
            'description': 'Daemon has been stopped.',
            'color': 0xFFFF00,  # Yellow
            'timestamp': now.isoformat(),
            'fields': [
                {'name': 'Published', 'value': str(stats.get('posts_published', 0)), 'inline': True},
                {'name': 'Failed', 'value': str(stats.get('posts_failed', 0)), 'inline': True},
                {'name': 'Checks', 'value': str(stats.get('checks_performed', 0)), 'inline': True},
            ]
        }
        await self._send_all(message, NotificationEvent.DAEMON_STOPPED)

    async def send_notification(
        self,
        title: str,
        description: str,
        color: int = 0x5865F2  # Discord blurple
    ):
        """
        Send a generic notification with title and description.

        This is a simplified interface for sending notifications when
        the more specific methods (notify_published, notify_failed, etc.)
        don't fit the use case.

        Args:
            title: Notification title
            description: Notification body/description
            color: Embed color (default: Discord blurple)
        """
        if not self.config.enabled:
            return

        now = datetime.now(ZoneInfo(TIMEZONE))
        message = {
            'title': title,
            'description': description,
            'color': color,
            'timestamp': now.isoformat(),
            'fields': []
        }
        await self._send_all(message, NotificationEvent.SYSTEM_ERROR)  # Use SYSTEM_ERROR as generic event type

    # ==========================================
    # MESSAGE FORMATTING
    # ==========================================

    def _format_published_message(
        self,
        platform: str,
        content_preview: str,
        url: Optional[str]
    ) -> Dict[str, Any]:
        """Format published notification."""
        now = datetime.now(ZoneInfo(TIMEZONE))

        return {
            'title': f'Published to {platform.title()}',
            'description': content_preview[:200] + ('...' if len(content_preview) > 200 else ''),
            'color': 0x00FF00,  # Green
            'timestamp': now.isoformat(),
            'url': url,
            'fields': [
                {'name': 'Platform', 'value': platform.title(), 'inline': True},
                {'name': 'Time', 'value': now.strftime('%H:%M'), 'inline': True},
            ]
        }

    def _format_failed_message(
        self,
        platform: str,
        error: str,
        post_path: Optional[str]
    ) -> Dict[str, Any]:
        """Format failed notification."""
        now = datetime.now(ZoneInfo(TIMEZONE))

        fields = [
            {'name': 'Platform', 'value': platform.title(), 'inline': True},
            {'name': 'Error', 'value': error[:100], 'inline': False},
        ]
        if post_path:
            fields.append({'name': 'Post', 'value': post_path, 'inline': False})

        return {
            'title': f'Failed to Publish to {platform.title()}',
            'description': 'A scheduled post failed to publish.',
            'color': 0xFF0000,  # Red
            'timestamp': now.isoformat(),
            'fields': fields
        }

    def _format_generated_message(
        self,
        week_folder: str,
        platforms: List[str],
        post_count: int
    ) -> Dict[str, Any]:
        """Format content generated notification."""
        now = datetime.now(ZoneInfo(TIMEZONE))

        return {
            'title': 'Weekly Content Generated',
            'description': f'Generated {post_count} posts for {len(platforms)} platforms.',
            'color': 0x0099FF,  # Blue
            'timestamp': now.isoformat(),
            'fields': [
                {'name': 'Week', 'value': week_folder, 'inline': True},
                {'name': 'Platforms', 'value': ', '.join(platforms), 'inline': False},
            ]
        }

    def _format_token_expiring_message(
        self,
        platform: str,
        expires_in_days: int
    ) -> Dict[str, Any]:
        """Format token expiring notification."""
        now = datetime.now(ZoneInfo(TIMEZONE))

        return {
            'title': f'{platform.title()} Token Expiring',
            'description': f'The OAuth token for {platform} will expire in {expires_in_days} days.',
            'color': 0xFFA500,  # Orange
            'timestamp': now.isoformat(),
            'fields': [
                {'name': 'Platform', 'value': platform.title(), 'inline': True},
                {'name': 'Days Remaining', 'value': str(expires_in_days), 'inline': True},
            ]
        }

    def _format_error_message(
        self,
        error: str,
        context: Optional[str]
    ) -> Dict[str, Any]:
        """Format error notification."""
        now = datetime.now(ZoneInfo(TIMEZONE))

        fields = [{'name': 'Error', 'value': error[:500], 'inline': False}]
        if context:
            fields.append({'name': 'Context', 'value': context, 'inline': False})

        return {
            'title': 'System Error',
            'description': 'An error occurred in PostAll.',
            'color': 0xFF0000,  # Red
            'timestamp': now.isoformat(),
            'fields': fields
        }

    def _format_daily_summary(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Format daily summary notification."""
        now = datetime.now(ZoneInfo(TIMEZONE))

        return {
            'title': 'Daily Summary',
            'description': f'PostAll activity for {now.strftime("%Y-%m-%d")}',
            'color': 0x9B59B6,  # Purple
            'timestamp': now.isoformat(),
            'fields': [
                {'name': 'Posts Published', 'value': str(stats.get('posts_published', 0)), 'inline': True},
                {'name': 'Posts Failed', 'value': str(stats.get('posts_failed', 0)), 'inline': True},
                {'name': 'Checks Performed', 'value': str(stats.get('checks_performed', 0)), 'inline': True},
                {'name': 'Scheduled Pending', 'value': str(stats.get('posts_scheduled', 0)), 'inline': True},
            ]
        }

    # ==========================================
    # CHANNEL SENDERS
    # ==========================================

    async def _send_all(self, message: Dict[str, Any], event: NotificationEvent):
        """Send notification to all configured channels."""
        tasks = []

        if self.config.discord_webhook_url:
            tasks.append(self._send_discord(message))

        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            tasks.append(self._send_telegram(message))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"[Notifier] Failed to send notification: {result}")

    async def _send_discord(self, message: Dict[str, Any]):
        """Send notification to Discord webhook."""
        embed = {
            'title': message.get('title', 'PostAll'),
            'description': message.get('description', ''),
            'color': message.get('color', 0x5865F2),
            'timestamp': message.get('timestamp'),
            'fields': message.get('fields', []),
            'footer': {'text': 'PostAll Cloud'}
        }

        if message.get('url'):
            embed['url'] = message['url']

        payload = {
            'embeds': [embed],
            'username': 'PostAll'
        }

        response = await self._client.post(
            self.config.discord_webhook_url,
            json=payload
        )
        response.raise_for_status()

    async def _send_telegram(self, message: Dict[str, Any]):
        """Send notification to Telegram."""
        # Format message for Telegram (HTML)
        title = message.get('title', 'PostAll')
        description = message.get('description', '')

        text_parts = [f"<b>{title}</b>", description]

        for field in message.get('fields', []):
            text_parts.append(f"<b>{field['name']}:</b> {field['value']}")

        if message.get('url'):
            text_parts.append(f"\n<a href=\"{message['url']}\">View Post</a>")

        text = '\n'.join(text_parts)

        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        payload = {
            'chat_id': self.config.telegram_chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }

        response = await self._client.post(url, json=payload)
        response.raise_for_status()


# Import asyncio at module level for _send_all
import asyncio
