"""
Telegram Command Bot for PostAll Cloud

Provides interactive commands to query the daemon:
- /schedule - Show today's scheduled posts
- /status - Show daemon status
- /upcoming - Show posts for next 24 hours
- /publish - Force publish due posts now
- /generate - Manually trigger content generation
- /cancel_generation - Cancel pending generation
- /content_status - Check next week's content status
- /menu - Show visual command buttons
- /help - Show available commands

Features:
- Visual command buttons (Reply Keyboard) for easy access
- Inline keyboard buttons for user interaction
- Generation reminder with cancel option
- Callback query handling

Requires:
- TELEGRAM_BOT_TOKEN: Bot token from @BotFather
- TELEGRAM_CHAT_ID: Your chat ID (for authorization)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from zoneinfo import ZoneInfo
import json

import httpx

from postall.config import TIMEZONE
from postall.cloud.database import ScheduleDatabase


class TelegramCommandBot:
    """
    Telegram bot that responds to commands.

    Usage:
        bot = TelegramCommandBot(token, chat_id, db)
        await bot.start()  # Start polling for commands
    """

    API_BASE = "https://api.telegram.org/bot"

    def __init__(
        self,
        bot_token: str,
        authorized_chat_id: str,
        database: ScheduleDatabase,
        stats_callback: Optional[Callable] = None,
        check_callback: Optional[Callable] = None,
        generation_callback: Optional[Callable] = None,
        cancel_generation_callback: Optional[Callable] = None,
        regenerate_callback: Optional[Callable] = None,
        approve_images_callback: Optional[Callable] = None
    ):
        """
        Initialize the Telegram bot.

        Args:
            bot_token: Telegram bot token
            authorized_chat_id: Chat ID authorized to use commands
            database: ScheduleDatabase instance
            stats_callback: Callback to get daemon stats
            check_callback: Callback to trigger immediate check
            generation_callback: Callback to trigger content generation
            cancel_generation_callback: Callback to cancel pending generation
            regenerate_callback: Callback to regenerate a platform's content
            approve_images_callback: Callback to generate images after manual approval
        """
        self.token = bot_token
        self.authorized_chat_id = str(authorized_chat_id)
        self.db = database
        self.stats_callback = stats_callback
        self.check_callback = check_callback
        self.generation_callback = generation_callback
        self.cancel_generation_callback = cancel_generation_callback
        self.regenerate_callback = regenerate_callback
        self.approve_images_callback = approve_images_callback

        self._client = httpx.AsyncClient(timeout=60.0)  # Must be longer than Telegram polling timeout
        self._running = False
        self._last_update_id = 0
        self.timezone = ZoneInfo(TIMEZONE)

        # Generation state
        self._generation_pending = False
        self._generation_cancelled = False
        self._reminder_message_id = None

        # Command handlers
        self._commands = {
            '/start': self._cmd_start,
            '/help': self._cmd_help,
            '/menu': self._cmd_menu,
            '/schedule': self._cmd_schedule,
            '/today': self._cmd_schedule,  # Alias
            '/status': self._cmd_status,
            '/upcoming': self._cmd_upcoming,
            '/publish': self._cmd_publish,
            '/stats': self._cmd_stats,
            '/generate': self._cmd_generate,
            '/cancel_generation': self._cmd_cancel_generation,
            '/content_status': self._cmd_content_status,
            '/review': self._cmd_review_content,  # NEW: Content quality feedback
            '/feedback': self._cmd_review_content,  # Alias
        }

        # Button text to command mapping (for reply keyboard buttons)
        self._button_commands = {
            '📅 Schedule': self._cmd_schedule,
            '📅 schedule': self._cmd_schedule,
            '⏰ Upcoming': self._cmd_upcoming,
            '⏰ upcoming': self._cmd_upcoming,
            '📊 Status': self._cmd_status,
            '📊 status': self._cmd_status,
            '📈 Stats': self._cmd_stats,
            '📈 stats': self._cmd_stats,
            '📝 Content Status': self._cmd_content_status,
            '📝 content status': self._cmd_content_status,
            '🚀 Generate': self._cmd_generate,
            '🚀 generate': self._cmd_generate,
            '▶️ Publish Now': self._cmd_publish,
            '▶️ publish now': self._cmd_publish,
            '🔄 Menu': self._cmd_menu,
            '🔄 menu': self._cmd_menu,
        }

        # Callback query handlers (for inline buttons)
        self._callback_handlers = {
            'cancel_generation': self._callback_cancel_generation,
            'confirm_generation': self._callback_confirm_generation,
            'force_generate': self._callback_force_generate,
            # Content quality feedback handlers
            'rate_perfect': self._callback_rate_content,
            'rate_excellent': self._callback_rate_content,
            'rate_average': self._callback_rate_content,
            'rate_poor': self._callback_rate_content,
            'rate_very_poor': self._callback_rate_content,
            'rate_custom': self._callback_request_custom_feedback,
            # Post selection for review
            'review_post': self._callback_review_post,
            # Escalation handlers
            'escalation_approve_all': self._callback_escalation_approve_all,
            'escalation_regenerate': self._callback_escalation_regenerate,
        }

        # State tracking for custom feedback
        self._awaiting_custom_feedback = {}  # {chat_id: post_id}

    async def start(self):
        """Start the bot (polling mode)."""
        self._running = True
        print(f"[TelegramBot] Starting command bot...")

        while self._running:
            try:
                await self._poll_updates()
            except Exception as e:
                print(f"[TelegramBot] Error polling: {e}")
                await asyncio.sleep(5)

            await asyncio.sleep(1)

    async def stop(self):
        """Stop the bot."""
        self._running = False
        await self._client.aclose()
        print("[TelegramBot] Bot stopped")

    async def _poll_updates(self):
        """Poll for new messages and callback queries."""
        url = f"{self.API_BASE}{self.token}/getUpdates"
        params = {
            'offset': self._last_update_id + 1,
            'timeout': 30,
            'allowed_updates': ['message', 'callback_query']
        }

        response = await self._client.get(url, params=params)
        data = response.json()

        if not data.get('ok'):
            return

        for update in data.get('result', []):
            self._last_update_id = update['update_id']
            await self._handle_update(update)

    async def _handle_update(self, update: Dict[str, Any]):
        """Handle a single update (message or callback query)."""
        # Handle callback queries (inline button presses)
        if 'callback_query' in update:
            await self._handle_callback_query(update['callback_query'])
            return

        message = update.get('message', {})
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '').strip()

        # Authorization check
        if chat_id != self.authorized_chat_id:
            await self._send_message(
                chat_id,
                "Unauthorized. This bot only responds to its owner."
            )
            return

        # Check if awaiting custom feedback
        if chat_id in self._awaiting_custom_feedback:
            await self._handle_custom_feedback_text(chat_id, text)
            return

        # Check for button text (reply keyboard buttons)
        if text in self._button_commands:
            await self._button_commands[text](chat_id, text)
            return

        # Find and execute command
        command = text.split()[0].lower() if text else ''

        if command in self._commands:
            await self._commands[command](chat_id, text)
        elif text.startswith('/'):
            await self._send_message(
                chat_id,
                f"Unknown command: {command}\nUse /help or tap 🔄 Menu for options."
            )

    async def _handle_callback_query(self, callback_query: Dict[str, Any]):
        """Handle callback query from inline keyboard button press."""
        callback_id = callback_query.get('id')
        chat_id = str(callback_query.get('message', {}).get('chat', {}).get('id', ''))
        message_id = callback_query.get('message', {}).get('message_id')
        data = callback_query.get('data', '')

        # Authorization check
        if chat_id != self.authorized_chat_id:
            await self._answer_callback(callback_id, "Unauthorized")
            return

        # Find and execute callback handler
        handler_name = data.split(':')[0] if ':' in data else data

        if handler_name in self._callback_handlers:
            await self._callback_handlers[handler_name](callback_id, chat_id, message_id, data)
        else:
            await self._answer_callback(callback_id, "Unknown action")

    async def _answer_callback(self, callback_id: str, text: str = ""):
        """Answer a callback query."""
        url = f"{self.API_BASE}{self.token}/answerCallbackQuery"
        payload = {
            'callback_query_id': callback_id,
            'text': text
        }

        try:
            await self._client.post(url, json=payload)
        except Exception as e:
            print(f"[TelegramBot] Failed to answer callback: {e}")

    async def _send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = 'HTML',
        reply_markup: Optional[Dict] = None
    ) -> Optional[int]:
        """Send a message, optionally with inline keyboard."""
        url = f"{self.API_BASE}{self.token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }

        if reply_markup:
            payload['reply_markup'] = reply_markup

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get('result', {}).get('message_id')
        except Exception as e:
            print(f"[TelegramBot] Failed to send message: {e}")
            return None

    async def _edit_message(
        self,
        chat_id: str,
        message_id: int,
        text: str,
        parse_mode: str = 'HTML',
        reply_markup: Optional[Dict] = None
    ):
        """Edit an existing message."""
        url = f"{self.API_BASE}{self.token}/editMessageText"
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }

        if reply_markup:
            payload['reply_markup'] = reply_markup

        try:
            await self._client.post(url, json=payload)
        except Exception as e:
            print(f"[TelegramBot] Failed to edit message: {e}")

    def _make_inline_keyboard(self, buttons: list) -> Dict:
        """
        Create an inline keyboard markup.

        Args:
            buttons: List of rows, each row is a list of (text, callback_data) tuples

        Example:
            buttons = [
                [("Cancel", "cancel_generation"), ("Proceed", "confirm_generation")],
            ]
        """
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for text, callback_data in row:
                keyboard_row.append({
                    'text': text,
                    'callback_data': callback_data
                })
            keyboard.append(keyboard_row)

        return {'inline_keyboard': keyboard}

    def _make_reply_keyboard(self, buttons: list, resize: bool = True, one_time: bool = False) -> Dict:
        """
        Create a reply keyboard markup with persistent buttons.

        Args:
            buttons: List of rows, each row is a list of button text strings
            resize: Whether to resize the keyboard to fit buttons
            one_time: Whether to hide keyboard after one use

        Example:
            buttons = [
                ["📅 Schedule", "⏰ Upcoming"],
                ["📊 Status", "📈 Stats"],
            ]
        """
        keyboard = []
        for row in buttons:
            keyboard_row = [{'text': btn} for btn in row]
            keyboard.append(keyboard_row)

        return {
            'keyboard': keyboard,
            'resize_keyboard': resize,
            'one_time_keyboard': one_time
        }

    def _get_command_menu_keyboard(self) -> Dict:
        """Create the main command menu as a reply keyboard."""
        return self._make_reply_keyboard([
            ["📅 Schedule", "⏰ Upcoming"],
            ["📊 Status", "📈 Stats"],
            ["📝 Content Status", "🚀 Generate"],
            ["▶️ Publish Now", "🔄 Menu"]
        ])

    # ==========================================
    # COMMAND HANDLERS
    # ==========================================

    async def _cmd_start(self, chat_id: str, text: str):
        """Handle /start command - show welcome message with command menu."""
        keyboard = self._get_command_menu_keyboard()
        await self._send_message(
            chat_id,
            """
<b>PostAll Command Bot</b>

Welcome! I can help you manage your scheduled social media posts.

<b>Quick Actions:</b>
📅 View today's schedule
⏰ See upcoming posts
📊 Check daemon status
🚀 Trigger content generation

Tap a button below or use /help for all commands.
            """.strip(),
            reply_markup=keyboard
        )

    async def _cmd_menu(self, chat_id: str, text: str):
        """Handle /menu command - show the command menu keyboard."""
        keyboard = self._get_command_menu_keyboard()
        await self._send_message(
            chat_id,
            """
<b>Command Menu</b>

Tap a button to execute a command:

<b>Row 1:</b> 📅 Schedule | ⏰ Upcoming
<b>Row 2:</b> 📊 Status | 📈 Stats
<b>Row 3:</b> 📝 Content Status | 🚀 Generate
<b>Row 4:</b> ▶️ Publish Now | 🔄 Menu
            """.strip(),
            reply_markup=keyboard
        )

    async def _cmd_help(self, chat_id: str, text: str):
        """Handle /help command."""
        keyboard = self._get_command_menu_keyboard()
        await self._send_message(
            chat_id,
            """
<b>Available Commands</b>

<b>Publishing:</b>
/schedule - Show today's scheduled posts
/upcoming - Show posts for next 24 hours
/publish - Force publish due posts now

<b>Content Generation:</b>
/content_status - Check next week's content status
/generate - Manually trigger content generation
/cancel_generation - Cancel pending generation

<b>Monitoring:</b>
/status - Show daemon status
/stats - Show publishing statistics

<b>Navigation:</b>
/menu - Show command buttons
/help - Show this message

<i>Tip: Use the buttons below for quick access!</i>
            """.strip(),
            reply_markup=keyboard
        )

    async def _cmd_schedule(self, chat_id: str, text: str):
        """Handle /schedule command - show today's posts."""
        now = datetime.now(self.timezone)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Get today's posts from database
        summary = self.db.get_schedule_summary()
        due_posts = self.db.get_due_posts()

        # Format message
        lines = [
            f"<b>Schedule for {now.strftime('%Y-%m-%d')}</b>",
            f"<b>Timezone:</b> {TIMEZONE}",
            ""
        ]

        # Get all scheduled posts for today
        all_posts = self._get_posts_for_period(today_start, today_end)

        if not all_posts:
            lines.append("No posts scheduled for today.")
        else:
            # Group by platform
            by_platform = {}
            for post in all_posts:
                platform = post.get('platform', 'unknown')
                if platform not in by_platform:
                    by_platform[platform] = []
                by_platform[platform].append(post)

            for platform, posts in sorted(by_platform.items()):
                lines.append(f"\n<b>{platform.upper()}</b> ({len(posts)} posts)")
                for post in posts[:5]:  # Limit to 5 per platform
                    time_str = post.get('scheduled_time', '')[:16]
                    status = post.get('status', 'scheduled')
                    status_emoji = {
                        'pending': '🕐',     # Awaiting approval
                        'scheduled': '⏰',   # Approved, ready to publish
                        'published': '✅',   # Published
                        'failed': '❌',      # Failed
                        'skipped': '⏭️'      # Skipped
                    }.get(status, '❓')
                    path = post.get('post_path', '')[:30]
                    lines.append(f"  {status_emoji} {time_str} - {path}")

        # Due posts
        if due_posts:
            lines.append(f"\n<b>Due Now:</b> {len(due_posts)} post(s)")

        await self._send_message(chat_id, '\n'.join(lines))

    async def _cmd_upcoming(self, chat_id: str, text: str):
        """Handle /upcoming command - show next 24 hours."""
        now = datetime.now(self.timezone)
        end = now + timedelta(hours=24)

        posts = self._get_posts_for_period(now, end)

        lines = [
            f"<b>Upcoming Posts (Next 24h)</b>",
            f"<b>Current Time:</b> {now.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]

        if not posts:
            lines.append("No posts scheduled in the next 24 hours.")
        else:
            # Sort by time
            posts_sorted = sorted(posts, key=lambda x: x.get('scheduled_time', ''))

            for post in posts_sorted[:15]:  # Limit to 15
                time_str = post.get('scheduled_time', '')[11:16]  # HH:MM
                platform = post.get('platform', '?')[:8]
                status = post.get('status', 'scheduled')
                status_emoji = {
                    'pending': '🕐',
                    'scheduled': '⏰',
                    'published': '✅',
                    'failed': '❌',
                    'skipped': '⏭️'
                }.get(status, '❓')
                path = post.get('post_path', '')[:25]
                lines.append(f"{status_emoji} {time_str} | {platform:<8} | {path}")

        await self._send_message(chat_id, '\n'.join(lines))

    async def _cmd_status(self, chat_id: str, text: str):
        """Handle /status command - show daemon status."""
        now = datetime.now(self.timezone)

        lines = [
            "<b>PostAll Daemon Status</b>",
            ""
        ]

        if self.stats_callback:
            stats = self.stats_callback()
            lines.extend([
                f"<b>Running:</b> Yes",
                f"<b>Checks:</b> {stats.get('checks_performed', 0)}",
                f"<b>Last Check:</b> {stats.get('last_check', 'N/A')[:16] if stats.get('last_check') else 'N/A'}",
                f"<b>Published Today:</b> {stats.get('posts_published', 0)}",
                f"<b>Failed Today:</b> {stats.get('posts_failed', 0)}",
                f"<b>Pending:</b> {stats.get('posts_scheduled', 0)}",
            ])

            if stats.get('next_post'):
                lines.append(f"<b>Next Post:</b> {stats.get('next_post')[:16]}")
        else:
            lines.append("Stats not available")

        await self._send_message(chat_id, '\n'.join(lines))

    async def _cmd_stats(self, chat_id: str, text: str):
        """Handle /stats command - show detailed statistics."""
        summary = self.db.get_schedule_summary()
        today_stats = self.db.get_today_stats()

        lines = [
            "<b>Publishing Statistics</b>",
            "",
            "<b>Today:</b>",
            f"  Published: {today_stats.get('posts_published', 0)}",
            f"  Failed: {today_stats.get('posts_failed', 0)}",
            f"  Checks: {today_stats.get('checks_performed', 0)}",
            "",
            "<b>Overall:</b>",
            f"  Total Scheduled: {summary.get('total', 0)}",
        ]

        # By status
        by_status = summary.get('by_status', {})
        if by_status:
            lines.append("")
            lines.append("<b>By Status:</b>")
            for status, count in by_status.items():
                lines.append(f"  {status}: {count}")

        # By platform
        by_platform = summary.get('by_platform', {})
        if by_platform:
            lines.append("")
            lines.append("<b>By Platform:</b>")
            for platform, count in sorted(by_platform.items()):
                lines.append(f"  {platform}: {count}")

        await self._send_message(chat_id, '\n'.join(lines))

    async def _cmd_publish(self, chat_id: str, text: str):
        """Handle /publish command - force publish due posts."""
        due_posts = self.db.get_due_posts()

        if not due_posts:
            await self._send_message(chat_id, "No posts are currently due for publishing.")
            return

        await self._send_message(
            chat_id,
            f"Found {len(due_posts)} due post(s). Triggering publish check..."
        )

        if self.check_callback:
            try:
                # Run the check callback
                await self.check_callback()
                await self._send_message(chat_id, "Publish check completed. Check /status for results.")
            except Exception as e:
                await self._send_message(chat_id, f"Error during publish: {str(e)[:100]}")
        else:
            await self._send_message(chat_id, "Publish callback not available.")

    async def _cmd_content_status(self, chat_id: str, text: str):
        """Handle /content_status command - check next week's content status."""
        try:
            from postall.cloud.generation_controller import GenerationController
            controller = GenerationController()
            status = controller.check_content_status()

            lines = [
                "<b>Next Week Content Status</b>",
                "",
                f"<b>Week:</b> {status['week_folder']}",
                f"<b>Status:</b> {'✅ Complete' if status['exists'] else '⚠️ Partial' if status['partial'] else '❌ Missing'}",
                ""
            ]

            if status['existing_platforms']:
                lines.append(f"<b>Existing:</b> {', '.join(status['existing_platforms'])}")

            if status['missing_platforms']:
                lines.append(f"<b>Missing:</b> {', '.join(status['missing_platforms'])}")

            # Show details per platform
            lines.append("")
            lines.append("<b>Details:</b>")
            for platform, details in status['details'].items():
                emoji = '✅' if details['exists'] else '❌'
                count = details['post_count']
                lines.append(f"  {emoji} {platform}: {count} post(s)")

            await self._send_message(chat_id, '\n'.join(lines))

        except Exception as e:
            await self._send_message(chat_id, f"Error checking content status: {str(e)[:100]}")

    async def _cmd_generate(self, chat_id: str, text: str):
        """Handle /generate command - manually trigger content generation."""
        try:
            from postall.cloud.generation_controller import GenerationController
            controller = GenerationController()
            status = controller.check_content_status()

            # Check if content already exists
            if status['exists']:
                keyboard = self._make_inline_keyboard([
                    [("Force Regenerate", "force_generate"), ("Cancel", "cancel_generation")]
                ])
                await self._send_message(
                    chat_id,
                    f"<b>Content Already Exists</b>\n\n"
                    f"Week: {status['week_folder']}\n"
                    f"All {len(status['existing_platforms'])} platforms have content.\n\n"
                    f"Do you want to force regenerate?",
                    reply_markup=keyboard
                )
                return

            # Show what will be generated
            if status['partial']:
                msg = (
                    f"<b>Partial Content Found</b>\n\n"
                    f"Week: {status['week_folder']}\n"
                    f"Existing: {', '.join(status['existing_platforms'])}\n"
                    f"Missing: {', '.join(status['missing_platforms'])}\n\n"
                    f"Generate missing platforms?"
                )
            else:
                enabled = ', '.join(controller.all_platforms) or 'none'
                msg = (
                    f"<b>No Content Found</b>\n\n"
                    f"Week: {status['week_folder']}\n"
                    f"Platforms to generate: {enabled}\n\n"
                    f"Start generation?"
                )

            keyboard = self._make_inline_keyboard([
                [("Generate Now", "confirm_generation"), ("Cancel", "cancel_generation")]
            ])

            await self._send_message(chat_id, msg, reply_markup=keyboard)

        except Exception as e:
            await self._send_message(chat_id, f"Error: {str(e)[:100]}")

    async def _cmd_cancel_generation(self, chat_id: str, text: str):
        """Handle /cancel_generation command - cancel pending generation."""
        if self._generation_pending:
            self._generation_cancelled = True
            await self._send_message(chat_id, "Generation cancelled. The scheduled generation will be skipped.")
        else:
            await self._send_message(chat_id, "No generation is currently pending.")

    # ==========================================
    # CALLBACK HANDLERS (Inline Button Actions)
    # ==========================================

    async def _callback_cancel_generation(
        self,
        callback_id: str,
        chat_id: str,
        message_id: int,
        data: str
    ):
        """Handle cancel generation button press."""
        self._generation_cancelled = True
        self._generation_pending = False

        await self._answer_callback(callback_id, "Generation cancelled")
        await self._edit_message(
            chat_id,
            message_id,
            "❌ <b>Generation Cancelled</b>\n\nThe content generation has been cancelled."
        )

    async def _callback_confirm_generation(
        self,
        callback_id: str,
        chat_id: str,
        message_id: int,
        data: str
    ):
        """Handle confirm generation button press."""
        await self._answer_callback(callback_id, "Starting generation...")

        # Update the message to show generation is in progress
        await self._edit_message(
            chat_id,
            message_id,
            "⏳ <b>Generation Started</b>\n\nGenerating content... This may take 10-30 minutes.\n\nYou will be notified when complete."
        )

        # Trigger generation
        if self.generation_callback:
            try:
                result = await self.generation_callback(force=False)
                await self._send_generation_result(chat_id, result)
            except Exception as e:
                await self._send_message(chat_id, f"❌ Generation failed: {str(e)[:200]}")
        else:
            await self._send_message(chat_id, "Generation callback not available.")

    async def _callback_force_generate(
        self,
        callback_id: str,
        chat_id: str,
        message_id: int,
        data: str
    ):
        """Handle force regenerate button press."""
        await self._answer_callback(callback_id, "Starting force generation...")

        await self._edit_message(
            chat_id,
            message_id,
            "⏳ <b>Force Generation Started</b>\n\nRegenerating all content... This may take 20-40 minutes.\n\nYou will be notified when complete."
        )

        if self.generation_callback:
            try:
                result = await self.generation_callback(force=True)
                await self._send_generation_result(chat_id, result)
            except Exception as e:
                await self._send_message(chat_id, f"❌ Generation failed: {str(e)[:200]}")
        else:
            await self._send_message(chat_id, "Generation callback not available.")

    # ==========================================
    # GENERATION REMINDER METHODS
    # ==========================================

    async def send_generation_reminder(
        self,
        week_folder: str,
        missing_platforms: list,
        generation_time: str,
        reminder_label: str = "⏰ Content Generation Scheduled",
        time_until: str = ""
    ):
        """
        Send a generation reminder with cancel button.

        Called by daemon before scheduled generation.

        Args:
            week_folder: The target week folder name
            missing_platforms: List of platforms to generate
            generation_time: Full generation time string (e.g., "Saturday 12:00")
            reminder_label: Label for the reminder (e.g., "📅 Day-Before Reminder")
            time_until: Human-readable time until generation (e.g., "tomorrow", "at 12:00")
        """
        self._generation_pending = True
        self._generation_cancelled = False

        time_info = f" ({time_until})" if time_until else ""

        msg = (
            f"{reminder_label}\n\n"
            f"<b>Week:</b> {week_folder}\n"
            f"<b>Generation:</b> {generation_time}{time_info}\n"
            f"<b>Platforms:</b> {', '.join(missing_platforms) if missing_platforms else 'All'}\n\n"
            f"Generation will start automatically.\n"
            f"Press Cancel to skip this week's generation."
        )

        keyboard = self._make_inline_keyboard([
            [("Cancel Generation", "cancel_generation"), ("Generate Now", "confirm_generation")]
        ])

        message_id = await self._send_message(
            self.authorized_chat_id,
            msg,
            reply_markup=keyboard
        )

        self._reminder_message_id = message_id
        return message_id

    async def send_generation_started(self, week_folder: str):
        """Notify that generation has started."""
        await self._send_message(
            self.authorized_chat_id,
            f"🚀 <b>Content Generation Started</b>\n\n"
            f"Week: {week_folder}\n\n"
            f"This may take 10-30 minutes..."
        )

    async def _send_generation_result(self, chat_id: str, result: Dict[str, Any]):
        """Send generation result summary."""
        if result.get('success'):
            emoji = '✅'
            status = 'Complete'
        else:
            emoji = '⚠️' if result.get('platforms_generated') else '❌'
            status = 'Partial' if result.get('platforms_generated') else 'Failed'

        lines = [
            f"{emoji} <b>Content Generation {status}</b>",
            "",
            f"<b>Week:</b> {result.get('week_folder', 'N/A')}",
            f"<b>Duration:</b> {result.get('generation_time', 'N/A')}",
            ""
        ]

        if result.get('platforms_generated'):
            lines.append(f"<b>Generated:</b> {', '.join(result['platforms_generated'])}")

        if result.get('platforms_skipped'):
            lines.append(f"<b>Skipped (existing):</b> {', '.join(result['platforms_skipped'])}")

        if result.get('platforms_failed'):
            lines.append(f"<b>Failed:</b> {', '.join(result['platforms_failed'])}")

        if result.get('director_review_done'):
            lines.append("")
            lines.append("✅ Director review completed")

        if result.get('errors'):
            lines.append("")
            lines.append("<b>Errors:</b>")
            for error in result['errors'][:3]:  # Limit to 3 errors
                lines.append(f"  • {error[:50]}")

        if result.get('message'):
            lines.append("")
            lines.append(f"<i>{result['message']}</i>")

        await self._send_message(chat_id, '\n'.join(lines))

    def is_generation_cancelled(self) -> bool:
        """Check if generation has been cancelled by user."""
        return self._generation_cancelled

    def reset_generation_state(self):
        """Reset generation state after generation completes or is cancelled."""
        self._generation_pending = False
        self._generation_cancelled = False
        self._reminder_message_id = None

    # ==========================================
    # DIRECTOR REVIEW ESCALATION NOTIFICATIONS
    # ==========================================

    async def send_director_review_result(
        self,
        week_folder: str,
        review_result: Dict[str, Any],
        auto_regen_attempts: int = 0
    ):
        """
        Send Director review results via Telegram, highlighting escalations.

        Args:
            week_folder: The week folder name
            review_result: The director review result dict from GenerationController
            auto_regen_attempts: Number of auto-regeneration attempts already made
        """
        total_reviewed = review_result.get('total_reviewed', 0)
        avg_score = review_result.get('avg_score', 0)
        decisions = review_result.get('decisions', {})
        escalations = review_result.get('escalations', [])
        ready = review_result.get('ready_to_schedule', [])

        # Build summary message
        approved_count = decisions.get('approve', 0) + decisions.get('approve_with_notes', 0)
        revision_count = decisions.get('revise', 0)
        escalation_count = decisions.get('escalate', 0)
        reject_count = decisions.get('reject', 0)

        lines = [
            "<b>Content Director Review Complete</b>",
            "",
            f"<b>Week:</b> {week_folder}",
            f"<b>Posts Reviewed:</b> {total_reviewed}",
            f"<b>Average Score:</b> {avg_score:.1f}/10",
            "",
            f"✅ Approved: {approved_count}",
            f"🔄 Needs Revision: {revision_count}",
            f"⚠️ Escalated: {escalation_count}",
            f"❌ Rejected: {reject_count}",
        ]

        if auto_regen_attempts > 0:
            lines.append("")
            lines.append(f"🔁 <b>Auto-regenerated {auto_regen_attempts} time(s)</b> — score still below threshold")

        if not escalations and approved_count == total_reviewed:
            lines.append("")
            lines.append("✅ <b>All posts approved! No escalations needed.</b>")
            await self._send_message(self.authorized_chat_id, '\n'.join(lines))
            return

        # Show escalated posts
        lines.append("")
        lines.append("<b>⚠️ Posts Requiring Human Review:</b>")

        for i, esc in enumerate(escalations[:5], 1):
            platform = esc.get('platform', '?')
            score = esc.get('score', 0)
            feedback = esc.get('feedback', 'No feedback')[:80]
            post_path = esc.get('post_path', '')
            # Extract just the filename
            post_name = post_path.split('/')[-1] if '/' in post_path else post_path
            post_name = post_name.split('\\')[-1] if '\\' in post_name else post_name

            lines.append(f"")
            lines.append(f"<b>{i}. {platform.upper()}</b> — Score: {score:.1f}/10")
            lines.append(f"   File: {post_name[:40]}")
            lines.append(f"   {feedback}")

        # Add action buttons
        keyboard_buttons = [
            [
                ("✅ Approve All", f"escalation_approve_all:{week_folder}"),
            ]
        ]

        # Add per-platform regenerate buttons for escalated platforms
        escalated_platforms = list(set(esc.get('platform', '') for esc in escalations))
        for platform in escalated_platforms[:3]:  # Max 3 platforms
            keyboard_buttons.append([
                (f"🔄 Regenerate {platform.capitalize()}", f"escalation_regenerate:{week_folder}:{platform}")
            ])

        keyboard = self._make_inline_keyboard(keyboard_buttons)

        await self._send_message(
            self.authorized_chat_id,
            '\n'.join(lines),
            reply_markup=keyboard
        )

    async def _callback_escalation_approve_all(
        self,
        callback_id: str,
        chat_id: str,
        message_id: int,
        data: str
    ):
        """Handle 'Approve All' escalation button — force-approve all escalated posts."""
        await self._answer_callback(callback_id, "Approving all escalated posts...")

        # Extract week_folder from data (format: escalation_approve_all:week_folder)
        parts = data.split(':', 1)
        week_folder = parts[1] if len(parts) > 1 else ''

        if not week_folder:
            await self._edit_message(chat_id, message_id, "❌ Invalid week folder.")
            return

        try:
            from pathlib import Path
            from postall.config import OUTPUT_DIR

            week_path = Path(OUTPUT_DIR) / week_folder
            schedule_file = week_path / "schedule.json"

            if not schedule_file.exists():
                await self._edit_message(chat_id, message_id, "❌ Schedule file not found.")
                return

            # Update all non-scheduled posts to scheduled and collect them for image generation
            schedule = json.loads(schedule_file.read_text(encoding="utf-8"))
            updated_count = 0
            approved_posts = []

            for platform_key, posts in schedule.get("posts", {}).items():
                for post in posts:
                    if post.get("status") in ("pending", "revise", "escalate", "reject"):
                        post["status"] = "scheduled"
                        post["director_review"] = {
                            "decision": "approve",
                            "score": 0,
                            "feedback": "Manually approved via Telegram",
                            "reviewed_at": datetime.now(self.timezone).isoformat()
                        }
                        updated_count += 1
                        approved_posts.append({
                            'post_path': post.get('post_path', ''),
                            'platform': platform_key,
                        })

            schedule["updated_at"] = datetime.now(self.timezone).isoformat()
            schedule_file.write_text(
                json.dumps(schedule, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            await self._edit_message(
                chat_id,
                message_id,
                f"✅ <b>All Escalated Posts Approved</b>\n\n"
                f"Updated {updated_count} post(s) to 'scheduled'.\n"
                f"Week: {week_folder}\n\n"
                f"Generating images for approved posts..."
            )

            # Trigger image generation for the newly approved posts
            if approved_posts and self.approve_images_callback:
                try:
                    img_result = await self.approve_images_callback(
                        week_folder=week_folder,
                        approved_posts=approved_posts
                    )
                    img_count = img_result.get('generated', 0)
                    img_failed = img_result.get('failed', 0)

                    status_lines = [
                        f"✅ <b>All Escalated Posts Approved</b>",
                        f"",
                        f"Updated {updated_count} post(s) to 'scheduled'.",
                        f"Week: {week_folder}",
                        f"",
                        f"<b>Image Generation:</b>",
                        f"  Generated: {img_count}",
                    ]
                    if img_failed:
                        status_lines.append(f"  Failed: {img_failed}")
                    if img_result.get('error'):
                        status_lines.append(f"  Error: {img_result['error'][:100]}")
                    status_lines.append("")
                    status_lines.append("Posts will be published at their scheduled times.")

                    await self._send_message(chat_id, '\n'.join(status_lines))
                except Exception as e:
                    await self._send_message(
                        chat_id,
                        f"⚠️ Posts approved but image generation failed: {str(e)[:200]}\n\n"
                        f"You may need to regenerate images manually."
                    )
            elif approved_posts:
                await self._send_message(
                    chat_id,
                    "⚠️ Posts approved but image generation callback not available.\n"
                    "Images were not generated."
                )

        except Exception as e:
            await self._edit_message(
                chat_id,
                message_id,
                f"❌ Error approving posts: {str(e)[:200]}"
            )

    async def _callback_escalation_regenerate(
        self,
        callback_id: str,
        chat_id: str,
        message_id: int,
        data: str
    ):
        """Handle 'Regenerate' escalation button — regenerate a platform's content."""
        # Extract week_folder and platform from data
        # Format: escalation_regenerate:week_folder:platform
        parts = data.split(':')
        if len(parts) < 3:
            await self._answer_callback(callback_id, "Invalid regeneration data")
            return

        week_folder = parts[1]
        platform = parts[2]

        await self._answer_callback(callback_id, f"Regenerating {platform}...")
        await self._edit_message(
            chat_id,
            message_id,
            f"⏳ <b>Regenerating {platform.capitalize()} Content</b>\n\n"
            f"Week: {week_folder}\n"
            f"This may take several minutes..."
        )

        if self.regenerate_callback:
            try:
                result = await self.regenerate_callback(platform=platform, week_folder=week_folder)

                if result.get('success'):
                    escalations = result.get('escalations', [])
                    avg_score = result.get('avg_score', 0)

                    if escalations:
                        await self._send_message(
                            chat_id,
                            f"⚠️ <b>Regeneration Complete — Still Has Escalations</b>\n\n"
                            f"Platform: {platform.capitalize()}\n"
                            f"New Avg Score: {avg_score:.1f}/10\n"
                            f"Escalations: {len(escalations)}\n\n"
                            f"Consider manually reviewing or approving."
                        )
                    else:
                        await self._send_message(
                            chat_id,
                            f"✅ <b>Regeneration Successful</b>\n\n"
                            f"Platform: {platform.capitalize()}\n"
                            f"New Avg Score: {avg_score:.1f}/10\n"
                            f"All posts approved and scheduled!"
                        )
                else:
                    errors = result.get('errors', ['Unknown error'])
                    await self._send_message(
                        chat_id,
                        f"❌ <b>Regeneration Failed</b>\n\n"
                        f"Platform: {platform.capitalize()}\n"
                        f"Error: {errors[0][:200] if errors else 'Unknown'}"
                    )
            except Exception as e:
                await self._send_message(
                    chat_id,
                    f"❌ Regeneration error: {str(e)[:200]}"
                )
        else:
            await self._send_message(
                chat_id,
                "❌ Regeneration callback not available. Please use /generate to regenerate all content."
            )

    # ==========================================
    # CONTENT QUALITY FEEDBACK SYSTEM (James Workflow Integration)
    # ==========================================

    async def _cmd_review_content(self, chat_id: str, text: str):
        """
        Show recent published posts for quality feedback.

        Usage: /review or /feedback
        """
        # Get recently published posts (last 10)
        try:
            with self.db._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, platform, post_path, week_folder, scheduled_at, published_at, status
                    FROM scheduled_posts
                    WHERE status = 'published'
                    ORDER BY published_at DESC
                    LIMIT 10
                """)

                columns = ['id', 'platform', 'post_path', 'week_folder', 'scheduled_at', 'published_at', 'status']
                posts = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            await self._send_message(chat_id, f"❌ Error retrieving posts: {e}")
            return

        if not posts:
            await self._send_message(chat_id, "📭 No published posts found.")
            return

        # Show list of posts
        lines = ["<b>📝 Recent Published Posts</b>", ""]
        lines.append("Select a post to review:")

        for i, post in enumerate(posts[:5], 1):  # Show top 5
            platform = post['platform'].capitalize()
            published_time = datetime.fromisoformat(post['published_at']).strftime("%m-%d %H:%M")
            lines.append(f"{i}. <b>{platform}</b> - {published_time}")

        # Create inline keyboard with post selection
        keyboard = []
        for i, post in enumerate(posts[:5], 1):
            platform_emoji = {'instagram': '📷', 'twitter': '🐦', 'linkedin': '💼', 'pinterest': '📌', 'threads': '🧵'}.get(post['platform'], '📄')
            keyboard.append([{
                'text': f"{platform_emoji} {i}. {post['platform'].capitalize()}",
                'callback_data': f"review_post:{post['id']}"
            }])

        await self._send_message(chat_id, '\n'.join(lines), reply_markup={'inline_keyboard': keyboard})

    async def _callback_rate_content(
        self,
        callback_id: str,
        chat_id: str,
        message_id: int,
        data: str
    ):
        """Handle content quality rating callback."""
        # Extract post_id and rating from callback_data
        # Format: rate_perfect:post_id or rate_excellent:post_id
        if ':' in data:
            action, post_id = data.split(':', 1)
        else:
            await self._answer_callback(callback_id, "❌ Invalid rating data")
            return

        # Map rating to signal value (RLHF feedback signals)
        rating_map = {
            'rate_perfect': ('+1.0', '⭐⭐⭐⭐⭐ 完美 (Perfect)'),
            'rate_excellent': ('+0.5', '⭐⭐⭐⭐ 优秀 (Excellent)'),
            'rate_average': ('0.0', '⭐⭐⭐ 一般 (Average)'),
            'rate_poor': ('-0.5', '⭐⭐ 需改进 (Needs Improvement)'),
            'rate_very_poor': ('-1.0', '⭐ 较差 (Poor)'),
        }

        if action not in rating_map:
            await self._answer_callback(callback_id, "❌ Unknown rating")
            return

        signal, rating_text = rating_map[action]

        # Store feedback
        await self._store_content_feedback(post_id, signal, rating_text, None)

        # Update message
        await self._edit_message(
            chat_id,
            message_id,
            f"✅ Feedback recorded: {rating_text}\n\nSignal: {signal}\nPost ID: {post_id}"
        )

        await self._answer_callback(callback_id, f"✅ Rated: {rating_text}")

    async def _callback_review_post(
        self,
        callback_id: str,
        chat_id: str,
        message_id: int,
        data: str
    ):
        """Handle post selection callback — show rating options for selected post."""
        # Format: review_post:post_id
        if ':' in data:
            post_id = data.split(':', 1)[1]
        else:
            await self._answer_callback(callback_id, "❌ Invalid post data")
            return

        await self._answer_callback(callback_id, "")
        await self._show_post_rating_options(chat_id, post_id, message_id)

    async def _callback_request_custom_feedback(
        self,
        callback_id: str,
        chat_id: str,
        message_id: int,
        data: str
    ):
        """Handle custom feedback request callback."""
        # Extract post_id
        if ':' in data:
            _, post_id = data.split(':', 1)
        else:
            await self._answer_callback(callback_id, "❌ Invalid data")
            return

        # Mark this chat as awaiting custom feedback
        self._awaiting_custom_feedback[chat_id] = post_id

        # Update message
        await self._edit_message(
            chat_id,
            message_id,
            "✏️ <b>Custom Feedback Mode</b>\n\nPlease type your detailed feedback for this post.\n\nYour message will be recorded and used to improve future content generation."
        )

        await self._answer_callback(callback_id, "✏️ Type your feedback...")

    async def _handle_custom_feedback_text(self, chat_id: str, text: str):
        """Handle custom feedback text input."""
        post_id = self._awaiting_custom_feedback.pop(chat_id, None)

        if not post_id:
            return

        # Store custom feedback (signal = 0.0 for manual review, actual signal determined by feedback sentiment)
        await self._store_content_feedback(post_id, '0.0', 'Custom Feedback', text)

        await self._send_message(
            chat_id,
            f"✅ <b>Custom feedback recorded</b>\n\n<i>{text[:200]}{'...' if len(text) > 200 else ''}</i>\n\nPost ID: {post_id}\n\nThank you! This feedback will help improve future content."
        )

    async def _show_post_rating_options(self, chat_id: str, post_id: str, message_id: int):
        """Show inline keyboard with rating options for a post."""
        # Get post details
        try:
            with self.db._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT platform, post_path, published_at
                    FROM scheduled_posts
                    WHERE id = ?
                """, (post_id,))
                row = cursor.fetchone()

                if not row:
                    await self._send_message(chat_id, "❌ Post not found")
                    return

                platform, post_path, published_at = row
        except Exception as e:
            await self._send_message(chat_id, f"❌ Error: {e}")
            return

        # Read post content preview
        try:
            from pathlib import Path
            post_file = Path(post_path)
            if post_file.exists():
                content_preview = post_file.read_text(encoding='utf-8')[:300]
            else:
                content_preview = "[Content file not found]"
        except:
            content_preview = "[Unable to read content]"

        # Create message with rating options
        lines = [
            "<b>📝 Rate this post</b>",
            "",
            f"<b>Platform:</b> {platform.capitalize()}",
            f"<b>Published:</b> {datetime.fromisoformat(published_at).strftime('%Y-%m-%d %H:%M')}",
            "",
            "<b>Content Preview:</b>",
            f"<i>{content_preview}...</i>",
            "",
            "<b>How would you rate this content?</b>"
        ]

        # Create inline keyboard (按照用户要求的格式)
        keyboard = [
            [{'text': '⭐⭐⭐⭐⭐ 完美 (Perfect)', 'callback_data': f'rate_perfect:{post_id}'}],
            [{'text': '⭐⭐⭐⭐ 优秀 (Excellent)', 'callback_data': f'rate_excellent:{post_id}'}],
            [{'text': '⭐⭐⭐ 一般 (Average)', 'callback_data': f'rate_average:{post_id}'}],
            [{'text': '⭐⭐ 需改进 (Needs Improvement)', 'callback_data': f'rate_poor:{post_id}'}],
            [{'text': '⭐ 较差 (Poor)', 'callback_data': f'rate_very_poor:{post_id}'}],
            [{'text': '✏️ 自定义反馈 (Custom Feedback)', 'callback_data': f'rate_custom:{post_id}'}],  # CRITICAL: Custom option
        ]

        await self._edit_message(chat_id, message_id, '\n'.join(lines), reply_markup={'inline_keyboard': keyboard})

    async def _store_content_feedback(self, post_id: str, signal: str, rating: str, custom_text: Optional[str]):
        """
        Store content quality feedback for RLHF system.

        Args:
            post_id: Database post ID
            signal: Feedback signal (+1.0, +0.5, 0.0, -0.5, -1.0)
            rating: Rating text
            custom_text: Custom feedback text (optional)
        """
        try:
            # Store in feedback database table
            with self.db._get_connection() as conn:
                # Create feedback table if not exists
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS content_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        post_id INTEGER NOT NULL,
                        signal REAL NOT NULL,
                        rating TEXT NOT NULL,
                        custom_feedback TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (post_id) REFERENCES scheduled_posts(id)
                    )
                """)

                # Insert feedback
                conn.execute("""
                    INSERT INTO content_feedback (post_id, signal, rating, custom_feedback, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    post_id,
                    float(signal),
                    rating,
                    custom_text,
                    datetime.now(self.timezone).isoformat()
                ))

                conn.commit()

            print(f"[TelegramBot] Feedback stored: Post {post_id}, Signal {signal}, Rating: {rating}")

        except Exception as e:
            print(f"[TelegramBot] Error storing feedback: {e}")

    # ==========================================
    # HELPER METHODS
    # ==========================================

    def _get_posts_for_period(self, start: datetime, end: datetime) -> list:
        """
        Get posts scheduled within a time period.

        Queries both database (for scheduled posts) and schedule.json files
        (for pending posts awaiting approval).
        """
        posts = []

        # Method 1: Query database for scheduled posts
        try:
            with self.db._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, platform, post_path, week_folder, scheduled_at as scheduled_time, status
                    FROM scheduled_posts
                    WHERE scheduled_at >= ? AND scheduled_at < ?
                    ORDER BY scheduled_at
                """, (start.isoformat(), end.isoformat()))

                columns = ['id', 'platform', 'post_path', 'week_folder', 'scheduled_time', 'status']
                posts.extend([dict(zip(columns, row)) for row in cursor.fetchall()])
        except Exception as e:
            print(f"[TelegramBot] Error querying database: {e}")

        # Method 2: Also check schedule.json files for pending posts
        # This catches posts that haven't been approved/imported yet
        try:
            from postall.config import OUTPUT_DIR
            import json
            from pathlib import Path

            output_path = Path(OUTPUT_DIR) if not isinstance(OUTPUT_DIR, Path) else OUTPUT_DIR

            # Find all week folders with schedule.json
            for week_folder in output_path.glob("*_week*/"):
                schedule_file = week_folder / "schedule.json"
                if not schedule_file.exists():
                    continue

                schedule_data = json.loads(schedule_file.read_text(encoding="utf-8"))

                for platform, platform_posts in schedule_data.get("posts", {}).items():
                    for post in platform_posts:
                        scheduled_at_str = post.get("scheduled_at", "")
                        if not scheduled_at_str:
                            continue

                        try:
                            scheduled_at = datetime.fromisoformat(scheduled_at_str)
                            # Check if within the time period
                            if start <= scheduled_at < end:
                                # Check if this post is already in our list (from database)
                                post_path = post.get("post_path", "")
                                already_exists = any(
                                    p.get("post_path") == post_path and p.get("platform") == platform
                                    for p in posts
                                )

                                if not already_exists:
                                    posts.append({
                                        "id": None,
                                        "platform": platform,
                                        "post_path": post_path,
                                        "week_folder": week_folder.name,
                                        "scheduled_time": scheduled_at_str,
                                        "status": post.get("status", "pending")
                                    })
                        except (ValueError, TypeError):
                            continue
        except Exception as e:
            print(f"[TelegramBot] Error reading schedule.json files: {e}")

        # Sort by scheduled time
        posts.sort(key=lambda x: x.get("scheduled_time", ""))
        return posts
