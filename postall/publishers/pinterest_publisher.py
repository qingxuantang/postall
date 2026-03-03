"""
Pinterest Publisher for PostAll

Uses Pinterest API v5 for programmatic pin creation.
Documentation: https://developers.pinterest.com/docs/api/v5/

Authentication: OAuth 2.0 with refresh tokens
Required scopes: boards:read, boards:write, pins:read, pins:write
"""

import os
import json
import base64
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from postall.config import (
    PINTEREST_ACCESS_TOKEN,
    PINTEREST_REFRESH_TOKEN,
    PINTEREST_APP_ID,
    PINTEREST_APP_SECRET,
    PINTEREST_BOARD_ID,
    PINTEREST_ENABLED,
    POSTALL_ROOT
)
from postall.publishers import clean_metadata


class PinterestPublisher:
    """Publish pins to Pinterest via Pinterest API v5."""

    # Pinterest API base URL
    API_BASE = "https://api.pinterest.com/v5"

    # Pinterest content limits
    TITLE_MAX_LENGTH = 100
    DESCRIPTION_MAX_LENGTH = 800
    ALT_TEXT_MAX_LENGTH = 500
    LINK_MAX_LENGTH = 2048

    def __init__(self):
        """Initialize the Pinterest publisher."""
        self.access_token = PINTEREST_ACCESS_TOKEN
        self.refresh_token = PINTEREST_REFRESH_TOKEN
        self.app_id = PINTEREST_APP_ID
        self.app_secret = PINTEREST_APP_SECRET
        self.default_board_id = PINTEREST_BOARD_ID

        # Token file for storing refreshed tokens
        self.token_file = POSTALL_ROOT / ".pinterest_tokens.json"

        # Load saved tokens if available
        self._load_saved_tokens()

        # Check configuration
        self._check_configuration()

    def _check_configuration(self):
        """Check if Pinterest publishing is properly configured."""
        self.is_configured = False
        self.config_errors = []

        if not PINTEREST_ENABLED:
            self.config_errors.append("PINTEREST_ENABLED is not set to true")
            return

        if not self.access_token:
            self.config_errors.append("PINTEREST_ACCESS_TOKEN is not set")
            return

        if not self.default_board_id:
            self.config_errors.append("PINTEREST_BOARD_ID is not set (required for pin destination)")
            return

        # Validate token format (should be a non-empty string)
        if len(self.access_token) < 10:
            self.config_errors.append("PINTEREST_ACCESS_TOKEN appears invalid (too short)")
            return

        self.is_configured = True

    def _load_saved_tokens(self):
        """Load tokens from saved file if available."""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    # Use saved tokens if env vars are not set
                    if not self.access_token and tokens.get("access_token"):
                        self.access_token = tokens["access_token"]
                    if not self.refresh_token and tokens.get("refresh_token"):
                        self.refresh_token = tokens["refresh_token"]
            except (json.JSONDecodeError, IOError):
                pass

    def _save_tokens(self):
        """Save tokens to file for persistence."""
        try:
            with open(self.token_file, 'w') as f:
                json.dump({
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "updated_at": datetime.now().isoformat()
                }, f)
        except IOError as e:
            print(f"Warning: Could not save Pinterest tokens: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using the refresh token.

        Pinterest access tokens expire, so this method can be used to get a new one.

        Returns:
            True if refresh successful, False otherwise
        """
        if not self.refresh_token or not self.app_id or not self.app_secret:
            print("Cannot refresh token: Missing refresh_token, app_id, or app_secret")
            return False

        url = "https://api.pinterest.com/v5/oauth/token"

        # Create Basic auth header
        auth_str = f"{self.app_id}:{self.app_secret}"
        auth_bytes = base64.b64encode(auth_str.encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_bytes}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=30)

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                # Pinterest returns a new refresh token too
                if token_data.get("refresh_token"):
                    self.refresh_token = token_data["refresh_token"]

                self._save_tokens()
                print("Pinterest access token refreshed successfully")
                return True
            else:
                print(f"Token refresh failed: {response.status_code} - {response.text}")
                return False

        except requests.RequestException as e:
            print(f"Token refresh error: {e}")
            return False

    def get_boards(self) -> List[Dict]:
        """
        Get list of boards for the authenticated user.

        Returns:
            List of board dictionaries with id, name, etc.
        """
        url = f"{self.API_BASE}/boards"

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("items", [])
            elif response.status_code == 401:
                # Token might be expired, try refresh
                if self.refresh_access_token():
                    return self.get_boards()  # Retry with new token
                return []
            else:
                print(f"Failed to get boards: {response.status_code}")
                return []

        except requests.RequestException as e:
            print(f"Error fetching boards: {e}")
            return []

    def check_status(self) -> Dict[str, Any]:
        """Check Pinterest publisher status and configuration."""
        status = {
            "enabled": PINTEREST_ENABLED,
            "configured": self.is_configured,
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "has_app_credentials": bool(self.app_id and self.app_secret),
            "default_board_id": self.default_board_id,
            "errors": self.config_errors
        }

        # Test API connection if configured
        if self.is_configured:
            try:
                # Try to get user info to verify token
                response = requests.get(
                    f"{self.API_BASE}/user_account",
                    headers=self._get_headers(),
                    timeout=10
                )
                status["api_connection"] = response.status_code == 200
                if response.status_code == 200:
                    user_data = response.json()
                    status["username"] = user_data.get("username")
            except requests.RequestException:
                status["api_connection"] = False

        return status

    def _upload_image(self, image_path: str) -> Optional[str]:
        """
        Upload an image and return the media URL.

        Pinterest API v5 accepts images via:
        1. Public URL (source_type: image_url)
        2. Base64 encoded (source_type: image_base64)

        Since we're working with local files, we'll use base64.

        Args:
            image_path: Path to local image file

        Returns:
            Base64 encoded image string, or None if failed
        """
        path = Path(image_path)
        if not path.exists():
            print(f"Image not found: {image_path}")
            return None

        # Check file size (Pinterest limit is 20MB)
        file_size = path.stat().st_size
        if file_size > 20 * 1024 * 1024:
            print(f"Image too large: {file_size / 1024 / 1024:.1f}MB (max 20MB)")
            return None

        # Read and encode
        try:
            with open(path, 'rb') as f:
                image_data = f.read()

            # Determine content type
            suffix = path.suffix.lower()
            content_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }

            if suffix not in content_types:
                print(f"Unsupported image format: {suffix}")
                return None

            # Return base64 encoded string
            return base64.b64encode(image_data).decode()

        except IOError as e:
            print(f"Error reading image: {e}")
            return None

    def publish(
        self,
        content: str,
        media_paths: Optional[List[str]] = None,
        title: Optional[str] = None,
        link: Optional[str] = None,
        board_id: Optional[str] = None,
        alt_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a pin on Pinterest.

        Args:
            content: Pin description (max 800 chars)
            media_paths: List of image paths (only first one used for standard pins)
            title: Pin title (max 100 chars)
            link: Destination URL (max 2048 chars)
            board_id: Target board ID (uses default if not specified)
            alt_text: Alt text for accessibility (max 500 chars)

        Returns:
            Dictionary with success status, pin ID, URL, etc.
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": f"Pinterest not configured: {'; '.join(self.config_errors)}"
            }

        # Clean metadata before publishing
        content = clean_metadata(content, 'pinterest')

        # Use default board if not specified
        target_board = board_id or self.default_board_id
        if not target_board:
            return {
                "success": False,
                "error": "No board_id specified and no default board configured"
            }

        # Prepare request payload
        payload = {
            "board_id": target_board,
            "description": content[:self.DESCRIPTION_MAX_LENGTH]
        }

        # Add optional fields
        if title:
            payload["title"] = title[:self.TITLE_MAX_LENGTH]

        if link:
            payload["link"] = link[:self.LINK_MAX_LENGTH]

        if alt_text:
            payload["alt_text"] = alt_text[:self.ALT_TEXT_MAX_LENGTH]

        # Handle media
        if media_paths and len(media_paths) > 0:
            image_path = media_paths[0]  # Pinterest standard pins use single image

            # Check if it's a URL or local file
            if image_path.startswith('http://') or image_path.startswith('https://'):
                payload["media_source"] = {
                    "source_type": "image_url",
                    "url": image_path
                }
            else:
                # Local file - use base64
                base64_image = self._upload_image(image_path)
                if base64_image:
                    # Determine content type
                    suffix = Path(image_path).suffix.lower()
                    content_type = {
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png',
                        '.gif': 'image/gif',
                        '.webp': 'image/webp'
                    }.get(suffix, 'image/jpeg')

                    payload["media_source"] = {
                        "source_type": "image_base64",
                        "content_type": content_type,
                        "data": base64_image
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to process image: {image_path}"
                    }
        else:
            # Pinterest requires media for pins
            return {
                "success": False,
                "error": "Pinterest pins require at least one image"
            }

        # Make API request
        url = f"{self.API_BASE}/pins"

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=60  # Longer timeout for image upload
            )

            if response.status_code == 201:
                # Success
                data = response.json()
                pin_id = data.get("id")

                return {
                    "success": True,
                    "postId": pin_id,
                    "url": f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else None,
                    "board_id": target_board,
                    "response": data
                }

            elif response.status_code == 401:
                # Token expired - try refresh
                if self.refresh_access_token():
                    # Retry with new token
                    return self.publish(content, media_paths, title, link, board_id, alt_text)
                else:
                    return {
                        "success": False,
                        "error": "Authentication failed and token refresh unsuccessful"
                    }

            elif response.status_code == 429:
                # Rate limited
                return {
                    "success": False,
                    "error": "Rate limit exceeded. Please try again later.",
                    "retry_after": response.headers.get("Retry-After")
                }

            else:
                # Other error
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass

                return {
                    "success": False,
                    "error": f"API error {response.status_code}: {error_data.get('message', response.text[:200])}"
                }

        except requests.Timeout:
            return {"success": False, "error": "Request timeout (60s)"}
        except requests.RequestException as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    def publish_with_images(
        self,
        content: str,
        image_folder: Path,
        title: Optional[str] = None,
        link: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish a pin using images from a folder.

        Args:
            content: Pin description
            image_folder: Path to folder containing images
            title: Optional pin title
            link: Optional destination URL

        Returns:
            Publish result
        """
        # Find images in folder
        image_paths = []
        if image_folder.exists():
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"]:
                image_paths.extend([str(p) for p in image_folder.glob(ext)])

        if not image_paths:
            return {
                "success": False,
                "error": f"No images found in {image_folder}"
            }

        # Use first image (Pinterest standard pins support single image)
        return self.publish(
            content=content,
            media_paths=[image_paths[0]],
            title=title,
            link=link
        )

    def create_carousel_pin(
        self,
        items: List[Dict],
        board_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a carousel pin with multiple images (2-5 images).

        Args:
            items: List of dicts with keys: image_path/image_url, title, description, link
            board_id: Target board ID

        Returns:
            Publish result
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": f"Pinterest not configured: {'; '.join(self.config_errors)}"
            }

        if len(items) < 2 or len(items) > 5:
            return {
                "success": False,
                "error": f"Carousel requires 2-5 items, got {len(items)}"
            }

        target_board = board_id or self.default_board_id

        # Build carousel media source
        carousel_items = []
        for item in items:
            carousel_item = {}

            if item.get("image_url"):
                carousel_item["source_type"] = "image_url"
                carousel_item["url"] = item["image_url"]
            elif item.get("image_path"):
                base64_data = self._upload_image(item["image_path"])
                if not base64_data:
                    return {
                        "success": False,
                        "error": f"Failed to process image: {item['image_path']}"
                    }
                carousel_item["source_type"] = "image_base64"
                carousel_item["data"] = base64_data
                suffix = Path(item["image_path"]).suffix.lower()
                carousel_item["content_type"] = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png'
                }.get(suffix, 'image/jpeg')

            if item.get("title"):
                carousel_item["title"] = item["title"][:self.TITLE_MAX_LENGTH]
            if item.get("description"):
                carousel_item["description"] = item["description"][:self.DESCRIPTION_MAX_LENGTH]
            if item.get("link"):
                carousel_item["link"] = item["link"][:self.LINK_MAX_LENGTH]

            carousel_items.append(carousel_item)

        payload = {
            "board_id": target_board,
            "media_source": {
                "source_type": "multiple_image_base64" if items[0].get("image_path") else "multiple_image_urls",
                "items": carousel_items
            }
        }

        url = f"{self.API_BASE}/pins"

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=120
            )

            if response.status_code == 201:
                data = response.json()
                pin_id = data.get("id")
                return {
                    "success": True,
                    "postId": pin_id,
                    "url": f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else None,
                    "type": "carousel"
                }
            else:
                return {
                    "success": False,
                    "error": f"API error {response.status_code}: {response.text[:200]}"
                }

        except Exception as e:
            return {"success": False, "error": str(e)}


def check_pinterest_status():
    """Check and print Pinterest publisher status."""
    print("\n Pinterest Publisher Status Check\n")
    print("=" * 50)

    try:
        publisher = PinterestPublisher()
        status = publisher.check_status()

        print(f"Enabled: {'Yes' if status['enabled'] else 'No'}")
        print(f"Configured: {'Yes' if status['configured'] else 'No'}")
        print(f"Access Token: {'Set' if status['has_access_token'] else 'Not set'}")
        print(f"Refresh Token: {'Set' if status['has_refresh_token'] else 'Not set'}")
        print(f"App Credentials: {'Set' if status['has_app_credentials'] else 'Not set'}")
        print(f"Default Board ID: {status['default_board_id'] or 'Not set'}")

        if status.get('api_connection'):
            print(f"API Connection: Connected")
            if status.get('username'):
                print(f"Username: @{status['username']}")
        elif status['configured']:
            print(f"API Connection: Failed (token may be expired)")

        if status['errors']:
            print("\nConfiguration Errors:")
            for error in status['errors']:
                print(f"  - {error}")

        if not status['configured']:
            print("\n To configure Pinterest publishing:")
            print("  1. Go to https://developers.pinterest.com/apps/")
            print("  2. Create a new app or select existing")
            print("  3. Get your OAuth credentials")
            print("  4. Complete OAuth flow to get access token")
            print("  5. Set environment variables in PostAll/.env:")
            print("     PINTEREST_ENABLED=true")
            print("     PINTEREST_ACCESS_TOKEN=your_access_token")
            print("     PINTEREST_REFRESH_TOKEN=your_refresh_token")
            print("     PINTEREST_APP_ID=your_app_id")
            print("     PINTEREST_APP_SECRET=your_app_secret")
            print("     PINTEREST_BOARD_ID=your_default_board_id")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_pinterest_status()
