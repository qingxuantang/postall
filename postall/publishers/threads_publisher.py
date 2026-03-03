"""
Threads Publisher for PostAll

Uses Threads API (via Meta) for programmatic content publishing.
Documentation: https://developers.facebook.com/docs/threads

Requirements:
- Threads account
- Meta App with threads_basic and threads_content_publish permissions
- App must pass Meta App Review for content publishing

Authentication: OAuth 2.0 via Meta
Required permissions: threads_basic, threads_content_publish
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from postall.config import (
    THREADS_ACCESS_TOKEN,
    THREADS_USER_ID,
    META_APP_ID,
    META_APP_SECRET,
    THREADS_ENABLED,
    POSTALL_ROOT
)
from postall.publishers import clean_metadata


class ThreadsPublisher:
    """Publish posts to Threads via Threads API."""

    # Threads API base URL
    API_BASE = "https://graph.threads.net/v1.0"

    # Threads content limits
    TEXT_MAX_LENGTH = 500
    MEDIA_MAX_SIZE_MB = 8
    CAROUSEL_MAX_ITEMS = 10

    # Supported media types
    SUPPORTED_IMAGE_TYPES = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    SUPPORTED_VIDEO_TYPES = ['.mp4', '.mov']

    def __init__(self):
        """Initialize the Threads publisher."""
        self.access_token = THREADS_ACCESS_TOKEN
        self.user_id = THREADS_USER_ID
        self.app_id = META_APP_ID
        self.app_secret = META_APP_SECRET

        # Token file for storing refreshed tokens
        self.token_file = POSTALL_ROOT / ".threads_tokens.json"

        # Load saved tokens if available
        self._load_saved_tokens()

        # Check configuration
        self._check_configuration()

    def _check_configuration(self):
        """Check if Threads publishing is properly configured."""
        self.is_configured = False
        self.config_errors = []

        if not THREADS_ENABLED:
            self.config_errors.append("THREADS_ENABLED is not set to true")
            return

        if not self.access_token:
            self.config_errors.append("THREADS_ACCESS_TOKEN is not set")
            return

        if not self.user_id:
            self.config_errors.append("THREADS_USER_ID is not set")
            return

        # Validate token format
        if len(self.access_token) < 10:
            self.config_errors.append("THREADS_ACCESS_TOKEN appears invalid (too short)")
            return

        self.is_configured = True

    def _load_saved_tokens(self):
        """Load tokens from saved file if available."""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    if not self.access_token and tokens.get("access_token"):
                        self.access_token = tokens["access_token"]
                    if not self.user_id and tokens.get("user_id"):
                        self.user_id = tokens["user_id"]
            except (json.JSONDecodeError, IOError):
                pass

    def _save_tokens(self):
        """Save tokens to file for persistence."""
        try:
            with open(self.token_file, 'w') as f:
                json.dump({
                    "access_token": self.access_token,
                    "user_id": self.user_id,
                    "updated_at": datetime.now().isoformat()
                }, f)
        except IOError as e:
            print(f"Warning: Could not save Threads tokens: {e}")

    def check_status(self) -> Dict[str, Any]:
        """Check Threads publisher status and configuration."""
        status = {
            "enabled": THREADS_ENABLED,
            "configured": self.is_configured,
            "has_access_token": bool(self.access_token),
            "user_id": self.user_id,
            "errors": self.config_errors
        }

        # Test API connection if configured
        if self.is_configured:
            try:
                # Get Threads user profile
                url = f"{self.API_BASE}/{self.user_id}"
                params = {
                    "fields": "id,username,threads_profile_picture_url,threads_biography",
                    "access_token": self.access_token
                }
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    status["api_connection"] = True
                    status["username"] = data.get("username")
                    status["biography"] = data.get("threads_biography")
                else:
                    status["api_connection"] = False
                    error = response.json().get("error", {})
                    status["api_error"] = error.get("message", "Unknown error")
            except Exception as e:
                status["api_connection"] = False
                status["api_error"] = str(e)

        return status

    def refresh_access_token(self) -> bool:
        """
        Refresh the access token.

        Threads tokens can be long-lived (60 days).
        Use the token refresh endpoint to extend validity.

        Returns:
            True if refresh successful, False otherwise
        """
        url = f"{self.API_BASE}/refresh_access_token"

        params = {
            "grant_type": "th_refresh_token",
            "access_token": self.access_token
        }

        try:
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self._save_tokens()
                print("Threads access token refreshed successfully")
                return True
            else:
                print(f"Token refresh failed: {response.text}")
                return False

        except requests.RequestException as e:
            print(f"Token refresh error: {e}")
            return False

    def _create_text_container(self, text: str) -> Optional[str]:
        """
        Create a text-only media container.

        Args:
            text: The post text (max 500 chars)

        Returns:
            Container ID or None if failed
        """
        url = f"{self.API_BASE}/{self.user_id}/threads"

        params = {
            "media_type": "TEXT",
            "text": text[:self.TEXT_MAX_LENGTH],
            "access_token": self.access_token
        }

        try:
            response = requests.post(url, params=params, timeout=60)

            if response.status_code == 200:
                return response.json().get("id")
            else:
                error = response.json().get("error", {})
                print(f"Failed to create text container: {error.get('message', 'Unknown error')}")
                return None

        except requests.RequestException as e:
            print(f"Error creating text container: {e}")
            return None

    def _create_image_container(
        self,
        image_url: str,
        text: str = ""
    ) -> Optional[str]:
        """
        Create an image media container.

        Args:
            image_url: Public URL of the image
            text: Optional caption text

        Returns:
            Container ID or None if failed
        """
        url = f"{self.API_BASE}/{self.user_id}/threads"

        params = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "access_token": self.access_token
        }

        if text:
            params["text"] = text[:self.TEXT_MAX_LENGTH]

        try:
            response = requests.post(url, params=params, timeout=60)

            if response.status_code == 200:
                return response.json().get("id")
            else:
                error = response.json().get("error", {})
                print(f"Failed to create image container: {error.get('message', 'Unknown error')}")
                return None

        except requests.RequestException as e:
            print(f"Error creating image container: {e}")
            return None

    def _create_carousel_container(
        self,
        children_ids: List[str],
        text: str = ""
    ) -> Optional[str]:
        """
        Create a carousel container from multiple media containers.

        Args:
            children_ids: List of media container IDs (image containers)
            text: Optional caption text

        Returns:
            Carousel container ID or None if failed
        """
        url = f"{self.API_BASE}/{self.user_id}/threads"

        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "access_token": self.access_token
        }

        if text:
            params["text"] = text[:self.TEXT_MAX_LENGTH]

        try:
            response = requests.post(url, params=params, timeout=60)

            if response.status_code == 200:
                return response.json().get("id")
            else:
                error = response.json().get("error", {})
                print(f"Failed to create carousel container: {error.get('message', 'Unknown error')}")
                return None

        except requests.RequestException as e:
            print(f"Error creating carousel container: {e}")
            return None

    def _check_container_status(self, container_id: str, max_attempts: int = 30) -> bool:
        """
        Check if a media container is ready for publishing.

        Args:
            container_id: The container ID to check
            max_attempts: Maximum number of polling attempts

        Returns:
            True if ready, False if failed or timeout
        """
        url = f"{self.API_BASE}/{container_id}"
        params = {
            "fields": "status",
            "access_token": self.access_token
        }

        for attempt in range(max_attempts):
            try:
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")

                    if status == "FINISHED":
                        return True
                    elif status == "ERROR":
                        print(f"Container processing failed")
                        return False
                    elif status in ["IN_PROGRESS", "PUBLISHED"]:
                        time.sleep(2)
                        continue
                    else:
                        time.sleep(2)
                        continue
                else:
                    print(f"Failed to check container status: {response.text}")
                    return False

            except requests.RequestException as e:
                print(f"Error checking container status: {e}")
                time.sleep(2)

        print("Container processing timeout")
        return False

    def _publish_container(self, container_id: str) -> Optional[Dict[str, Any]]:
        """
        Publish a media container to Threads.

        Args:
            container_id: The container ID to publish

        Returns:
            Response dict with post ID or None if failed
        """
        url = f"{self.API_BASE}/{self.user_id}/threads_publish"

        params = {
            "creation_id": container_id,
            "access_token": self.access_token
        }

        try:
            response = requests.post(url, params=params, timeout=60)

            if response.status_code == 200:
                return response.json()
            else:
                error = response.json().get("error", {})
                print(f"Failed to publish: {error.get('message', 'Unknown error')}")
                return None

        except requests.RequestException as e:
            print(f"Error publishing container: {e}")
            return None

    def publish(
        self,
        content: str,
        media_urls: Optional[List[str]] = None,
        is_carousel: bool = False
    ) -> Dict[str, Any]:
        """
        Publish a post to Threads.

        Args:
            content: Post text (max 500 chars)
            media_urls: Optional list of public image URLs
            is_carousel: Whether to post as carousel

        Returns:
            Dictionary with success status, post ID, URL, etc.
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": f"Threads not configured: {'; '.join(self.config_errors)}"
            }

        # Clean metadata before publishing
        content = clean_metadata(content, 'threads')

        # Truncate content
        text = content[:self.TEXT_MAX_LENGTH]

        try:
            container_id = None

            if media_urls and len(media_urls) > 1 and is_carousel:
                # Create carousel post
                children_ids = []

                for url in media_urls[:self.CAROUSEL_MAX_ITEMS]:
                    # Create image container for each (without text for carousel items)
                    child_id = self._create_image_container(image_url=url)
                    if child_id:
                        # Wait for container to be ready
                        if self._check_container_status(child_id):
                            children_ids.append(child_id)

                if not children_ids:
                    return {
                        "success": False,
                        "error": "Failed to create any media containers"
                    }

                # Create carousel container with text
                container_id = self._create_carousel_container(children_ids, text)

            elif media_urls and len(media_urls) > 0:
                # Single image post
                container_id = self._create_image_container(media_urls[0], text)

            else:
                # Text-only post
                container_id = self._create_text_container(text)

            if not container_id:
                return {
                    "success": False,
                    "error": "Failed to create media container"
                }

            # Wait for container to be ready
            if not self._check_container_status(container_id):
                return {
                    "success": False,
                    "error": "Container failed processing"
                }

            # Publish
            result = self._publish_container(container_id)

            if result and result.get("id"):
                post_id = result["id"]
                return {
                    "success": True,
                    "postId": post_id,
                    "url": f"https://www.threads.net/@{self.user_id}/post/{post_id}",
                    "mediaCount": len(media_urls) if media_urls else 0
                }
            else:
                return {
                    "success": False,
                    "error": "Publishing failed - no post ID returned"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }

    def publish_text(self, content: str) -> Dict[str, Any]:
        """
        Publish a text-only post to Threads.

        Args:
            content: Post text (max 500 chars)

        Returns:
            Publish result
        """
        return self.publish(content)

    def publish_with_image(
        self,
        content: str,
        image_url: str
    ) -> Dict[str, Any]:
        """
        Publish a post with a single image.

        Args:
            content: Post text
            image_url: Public URL of the image

        Returns:
            Publish result
        """
        return self.publish(content, media_urls=[image_url])


def check_threads_status():
    """Check and print Threads publisher status."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()

    console.print(Panel(
        "Threads Publisher Status\nChecking configuration...",
        title="",
        border_style="purple"
    ))

    try:
        publisher = ThreadsPublisher()
        status = publisher.check_status()

        table = Table(title="Threads Configuration Status")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Enabled", "Yes" if status['enabled'] else "No")
        table.add_row("Configured", "Yes" if status['configured'] else "No")
        table.add_row("Access Token", "Set" if status['has_access_token'] else "Not set")
        table.add_row("User ID", status.get('user_id') or "Not set")

        if status.get('api_connection'):
            table.add_row("API Connection", "Connected")
            if status.get('username'):
                table.add_row("Username", f"@{status['username']}")
        elif status['configured']:
            table.add_row("API Connection", "Failed")
            if status.get('api_error'):
                table.add_row("Error", status['api_error'])

        console.print(table)

        if status['errors']:
            console.print("\n[red]Errors:[/red]")
            for error in status['errors']:
                console.print(f"  [red]x[/red] {error}")

        if not status['configured']:
            console.print(Panel(
                """[bold]Setup Instructions:[/bold]

1. Go to https://developers.facebook.com/apps
2. Create a new app or select existing
3. Add 'Threads API' product to your app
4. Generate a User Access Token with permissions:
   - threads_basic
   - threads_content_publish
5. Get your Threads User ID from the API
6. Set environment variables in PostAll/.env:
   THREADS_ENABLED=true
   THREADS_ACCESS_TOKEN=your_token
   THREADS_USER_ID=your_user_id

[yellow]Note: App Review required for threads_content_publish permission![/yellow]

[bold]Get User ID via API:[/bold]
curl "https://graph.threads.net/v1.0/me?access_token=YOUR_TOKEN"

Token validity: 60 days (use refresh endpoint to extend)""",
                title="To Configure Threads Publishing",
                border_style="yellow"
            ))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    check_threads_status()
