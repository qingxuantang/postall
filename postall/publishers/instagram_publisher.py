"""
Instagram Publisher for PostAll

Uses Instagram Graph API (via Meta) for programmatic content publishing.
Documentation: https://developers.facebook.com/docs/instagram-api/guides/content-publishing

Requirements:
- Instagram Business or Creator account
- Connected to a Facebook Page
- Meta App with instagram_basic and instagram_content_publish permissions
- App must pass Meta App Review for content publishing

Authentication: OAuth 2.0 via Meta/Facebook
Required permissions: instagram_basic, instagram_content_publish, pages_read_engagement
"""

import os
import json
import time
import tempfile
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from postall.config import (
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_BUSINESS_ACCOUNT_ID,
    FACEBOOK_PAGE_ID,
    META_APP_ID,
    META_APP_SECRET,
    INSTAGRAM_ENABLED,
    POSTALL_ROOT,
    OUTPUT_DIR
)
from postall.publishers import clean_metadata

# Import media server for URL generation (cloud mode)
try:
    from postall.cloud.media_server import MediaServer, SERVER_BASE_URL
    MEDIA_SERVER_AVAILABLE = True
except ImportError:
    MEDIA_SERVER_AVAILABLE = False
    SERVER_BASE_URL = ""


class InstagramPublisher:
    """Publish posts to Instagram via Instagram Graph API."""

    # Instagram Graph API base URL
    API_BASE = "https://graph.facebook.com/v21.0"

    # Instagram content limits
    CAPTION_MAX_LENGTH = 2200
    HASHTAG_MAX = 30
    CAROUSEL_MAX_ITEMS = 10

    # Supported media types
    SUPPORTED_IMAGE_TYPES = ['.jpg', '.jpeg', '.png', '.gif']
    SUPPORTED_VIDEO_TYPES = ['.mp4', '.mov']

    # Instagram aspect ratio limits
    # Minimum: 4:5 (portrait) = 0.8
    # Maximum: 1.91:1 (landscape) = 1.91
    MIN_ASPECT_RATIO = 0.8   # 4:5
    MAX_ASPECT_RATIO = 1.91  # 1.91:1

    def __init__(self):
        """Initialize the Instagram publisher."""
        self.access_token = INSTAGRAM_ACCESS_TOKEN
        self.ig_user_id = INSTAGRAM_BUSINESS_ACCOUNT_ID
        self.page_id = FACEBOOK_PAGE_ID
        self.app_id = META_APP_ID
        self.app_secret = META_APP_SECRET

        # Token file for storing refreshed tokens
        self.token_file = POSTALL_ROOT / ".instagram_tokens.json"

        # Load saved tokens if available
        self._load_saved_tokens()

        # Check configuration
        self._check_configuration()

    def _check_configuration(self):
        """Check if Instagram publishing is properly configured."""
        self.is_configured = False
        self.config_errors = []

        if not INSTAGRAM_ENABLED:
            self.config_errors.append("INSTAGRAM_ENABLED is not set to true")
            return

        if not self.access_token:
            self.config_errors.append("INSTAGRAM_ACCESS_TOKEN is not set")
            return

        if not self.ig_user_id:
            self.config_errors.append("INSTAGRAM_BUSINESS_ACCOUNT_ID is not set")
            return

        # Validate token format
        if len(self.access_token) < 10:
            self.config_errors.append("INSTAGRAM_ACCESS_TOKEN appears invalid (too short)")
            return

        self.is_configured = True

        # Track temporary files for cleanup
        self._temp_files = []

    def _validate_aspect_ratio(self, image_path: str) -> Tuple[bool, float, str]:
        """
        Check if an image's aspect ratio is valid for Instagram.

        Instagram accepts aspect ratios between 4:5 (0.8) and 1.91:1.

        Args:
            image_path: Path to the image file

        Returns:
            Tuple of (is_valid, aspect_ratio, message)
        """
        if not PIL_AVAILABLE:
            return True, 1.0, "PIL not available, skipping validation"

        try:
            with Image.open(image_path) as img:
                width, height = img.size
                aspect_ratio = width / height

                if aspect_ratio < self.MIN_ASPECT_RATIO:
                    return False, aspect_ratio, f"Image too tall: {aspect_ratio:.3f} (min: {self.MIN_ASPECT_RATIO})"
                elif aspect_ratio > self.MAX_ASPECT_RATIO:
                    return False, aspect_ratio, f"Image too wide: {aspect_ratio:.3f} (max: {self.MAX_ASPECT_RATIO})"
                else:
                    return True, aspect_ratio, f"Valid aspect ratio: {aspect_ratio:.3f}"
        except Exception as e:
            return True, 1.0, f"Could not validate: {e}"

    def _adjust_image_aspect_ratio(self, image_path: str) -> Optional[str]:
        """
        Adjust an image's aspect ratio to fit Instagram's requirements.

        If the image is too tall (ratio < 0.8), adds horizontal padding.
        If the image is too wide (ratio > 1.91), adds vertical padding.
        Uses the dominant edge color for padding to blend naturally.

        Args:
            image_path: Path to the original image

        Returns:
            Path to the adjusted image (temp file), or None if adjustment failed
        """
        if not PIL_AVAILABLE:
            print("    Warning: PIL not available, cannot adjust aspect ratio")
            return None

        try:
            with Image.open(image_path) as img:
                width, height = img.size
                aspect_ratio = width / height

                # Check if adjustment is needed
                if self.MIN_ASPECT_RATIO <= aspect_ratio <= self.MAX_ASPECT_RATIO:
                    return image_path  # No adjustment needed

                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ('RGBA', 'P'):
                    # Create white background for transparent images
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[3])
                    else:
                        background.paste(img)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Determine padding color by sampling edge pixels
                padding_color = self._get_dominant_edge_color(img)

                if aspect_ratio < self.MIN_ASPECT_RATIO:
                    # Image is too tall (narrow), need to add width
                    # Target: 4:5 ratio (0.8)
                    target_ratio = self.MIN_ASPECT_RATIO
                    new_width = int(height * target_ratio)
                    new_height = height

                    # Create new image with padding
                    new_img = Image.new('RGB', (new_width, new_height), padding_color)
                    # Center the original image
                    x_offset = (new_width - width) // 2
                    new_img.paste(img, (x_offset, 0))

                    print(f"    Adjusted: {width}x{height} → {new_width}x{new_height} (added horizontal padding)")

                else:  # aspect_ratio > self.MAX_ASPECT_RATIO
                    # Image is too wide, need to add height
                    # Target: 1.91:1 ratio
                    target_ratio = self.MAX_ASPECT_RATIO
                    new_width = width
                    new_height = int(width / target_ratio)

                    # Create new image with padding
                    new_img = Image.new('RGB', (new_width, new_height), padding_color)
                    # Center the original image
                    y_offset = (new_height - height) // 2
                    new_img.paste(img, (0, y_offset))

                    print(f"    Adjusted: {width}x{height} → {new_width}x{new_height} (added vertical padding)")

                # Save adjusted image in the SAME directory as the original
                # This ensures the media server can generate a URL for it
                original_path = Path(image_path)
                adjusted_filename = f"{original_path.stem}_ig_adjusted.png"
                adjusted_path = original_path.parent / adjusted_filename

                new_img.save(str(adjusted_path), 'PNG', quality=95)
                self._temp_files.append(str(adjusted_path))

                return str(adjusted_path)

        except Exception as e:
            print(f"    Error adjusting image: {e}")
            return None

    def _get_dominant_edge_color(self, img: 'Image.Image') -> Tuple[int, int, int]:
        """
        Get the dominant color from the edges of an image.

        Samples pixels from all edges to determine the best padding color.

        Args:
            img: PIL Image object

        Returns:
            RGB tuple for the dominant edge color
        """
        width, height = img.size
        edge_pixels = []

        # Sample from all four edges
        for x in range(0, width, max(1, width // 20)):
            edge_pixels.append(img.getpixel((x, 0)))  # Top edge
            edge_pixels.append(img.getpixel((x, height - 1)))  # Bottom edge

        for y in range(0, height, max(1, height // 20)):
            edge_pixels.append(img.getpixel((0, y)))  # Left edge
            edge_pixels.append(img.getpixel((width - 1, y)))  # Right edge

        if not edge_pixels:
            return (255, 255, 255)  # Default to white

        # Calculate average color
        r = sum(p[0] for p in edge_pixels) // len(edge_pixels)
        g = sum(p[1] for p in edge_pixels) // len(edge_pixels)
        b = sum(p[2] for p in edge_pixels) // len(edge_pixels)

        return (r, g, b)

    def _cleanup_temp_files(self):
        """Clean up temporary files created during processing."""
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass
        self._temp_files = []

    def _load_saved_tokens(self):
        """Load tokens from saved file if available."""
        self.token_expires_at = None
        self.token_type = None  # 'short_lived' or 'long_lived'

        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    # Only use saved token if env token is not set
                    if not self.access_token and tokens.get("access_token"):
                        self.access_token = tokens["access_token"]
                    if not self.ig_user_id and tokens.get("ig_user_id"):
                        self.ig_user_id = tokens["ig_user_id"]
                    # Load expiration info
                    if tokens.get("expires_at"):
                        self.token_expires_at = datetime.fromisoformat(tokens["expires_at"])
                    self.token_type = tokens.get("token_type", "unknown")
            except (json.JSONDecodeError, IOError, ValueError):
                pass

    def _save_tokens(self, expires_in_seconds: int = None, token_type: str = None):
        """
        Save tokens to file for persistence.

        Args:
            expires_in_seconds: Token validity in seconds (e.g., 5184000 for 60 days)
            token_type: 'short_lived' or 'long_lived'
        """
        try:
            data = {
                "access_token": self.access_token,
                "ig_user_id": self.ig_user_id,
                "updated_at": datetime.now().isoformat()
            }

            if expires_in_seconds:
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
                data["expires_at"] = self.token_expires_at.isoformat()
                data["expires_in_seconds"] = expires_in_seconds
            elif self.token_expires_at:
                data["expires_at"] = self.token_expires_at.isoformat()

            if token_type:
                self.token_type = token_type
                data["token_type"] = token_type
            elif self.token_type:
                data["token_type"] = self.token_type

            with open(self.token_file, 'w') as f:
                json.dump(data, f, indent=2)

        except IOError as e:
            print(f"Warning: Could not save Instagram tokens: {e}")

    def get_token_status(self) -> Dict[str, Any]:
        """
        Get current token status including expiration info.

        Returns:
            Dictionary with token status information
        """
        status = {
            "has_token": bool(self.access_token),
            "token_type": self.token_type or "unknown",
            "has_app_credentials": bool(self.app_id and self.app_secret),
        }

        if self.token_expires_at:
            now = datetime.now()
            status["expires_at"] = self.token_expires_at.isoformat()
            status["is_expired"] = now > self.token_expires_at

            if not status["is_expired"]:
                remaining = self.token_expires_at - now
                status["days_remaining"] = remaining.days
                status["expires_in_human"] = f"{remaining.days} days, {remaining.seconds // 3600} hours"
                status["needs_refresh"] = remaining.days < 7  # Refresh if less than 7 days left
            else:
                status["days_remaining"] = 0
                status["expires_in_human"] = "EXPIRED"
                status["needs_refresh"] = True
        else:
            status["expires_at"] = "unknown"
            status["is_expired"] = "unknown"
            status["needs_refresh"] = "unknown"

        return status

    def exchange_for_long_lived_token(self) -> Dict[str, Any]:
        """
        Exchange a short-lived token for a long-lived token (60 days).

        Requires META_APP_ID and META_APP_SECRET to be set in .env.

        Returns:
            Dictionary with success status and new token info
        """
        if not self.app_id or not self.app_secret:
            return {
                "success": False,
                "error": "META_APP_ID and META_APP_SECRET are required for token exchange. Set them in .env"
            }

        if not self.access_token:
            return {
                "success": False,
                "error": "No access token to exchange"
            }

        url = f"{self.API_BASE}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "fb_exchange_token": self.access_token
        }

        try:
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                new_token = data.get("access_token")
                expires_in = data.get("expires_in", 5184000)  # Default 60 days

                if new_token:
                    # Update and save the new token
                    old_token = self.access_token
                    self.access_token = new_token
                    self._save_tokens(expires_in_seconds=expires_in, token_type="long_lived")

                    return {
                        "success": True,
                        "message": "Token exchanged successfully",
                        "expires_in_days": expires_in // 86400,
                        "expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
                        "token_changed": old_token != new_token
                    }
                else:
                    return {
                        "success": False,
                        "error": "No token returned from API"
                    }
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                return {
                    "success": False,
                    "error": f"Token exchange failed: {error_msg}"
                }

        except requests.RequestException as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }

    def refresh_long_lived_token(self) -> Dict[str, Any]:
        """
        Refresh a long-lived token before it expires.

        Long-lived tokens can be refreshed if they are:
        - At least 24 hours old
        - Not yet expired

        The refreshed token is valid for another 60 days.

        Returns:
            Dictionary with success status and new token info
        """
        # Check token status first
        token_status = self.get_token_status()

        if token_status.get("is_expired") == True:
            return {
                "success": False,
                "error": "Token has already expired. You need to generate a new token from Graph API Explorer."
            }

        # Same API call as exchange - works for both short and long-lived tokens
        return self.exchange_for_long_lived_token()

    def auto_refresh_if_needed(self) -> Dict[str, Any]:
        """
        Automatically refresh token if it's close to expiration.

        Called internally before API operations to ensure token validity.

        Returns:
            Dictionary with refresh status (or skip if not needed)
        """
        token_status = self.get_token_status()

        # Skip if we don't have app credentials
        if not token_status["has_app_credentials"]:
            return {
                "skipped": True,
                "reason": "No app credentials for auto-refresh"
            }

        # Skip if token status is unknown
        if token_status.get("needs_refresh") == "unknown":
            return {
                "skipped": True,
                "reason": "Token expiration unknown"
            }

        # Skip if token doesn't need refresh
        if not token_status.get("needs_refresh"):
            return {
                "skipped": True,
                "reason": f"Token valid for {token_status.get('days_remaining', 'unknown')} more days"
            }

        # Token is expired
        if token_status.get("is_expired"):
            return {
                "skipped": True,
                "reason": "Token expired - manual renewal required"
            }

        # Try to refresh
        print("Instagram token expires soon, attempting auto-refresh...")
        result = self.refresh_long_lived_token()

        if result.get("success"):
            print(f"Token refreshed successfully. Valid for {result.get('expires_in_days', 60)} more days.")
        else:
            print(f"Token refresh failed: {result.get('error')}")

        return result

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            "Content-Type": "application/json"
        }

    def check_status(self) -> Dict[str, Any]:
        """Check Instagram publisher status and configuration."""
        status = {
            "enabled": INSTAGRAM_ENABLED,
            "configured": self.is_configured,
            "has_access_token": bool(self.access_token),
            "ig_user_id": self.ig_user_id,
            "page_id": self.page_id,
            "errors": self.config_errors
        }

        # Add token status
        token_status = self.get_token_status()
        status["token_status"] = token_status

        # Test API connection if configured
        if self.is_configured:
            try:
                # Test with just ID field first (minimal permissions)
                url = f"{self.API_BASE}/{self.ig_user_id}"
                params = {
                    "fields": "id",
                    "access_token": self.access_token
                }
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    status["api_connection"] = True
                    status["account_id"] = data.get("id")

                    # Try to get username separately (may fail due to permissions)
                    try:
                        url2 = f"{self.API_BASE}/{self.ig_user_id}"
                        params2 = {"fields": "username", "access_token": self.access_token}
                        resp2 = requests.get(url2, params=params2, timeout=10)
                        if resp2.status_code == 200:
                            status["username"] = resp2.json().get("username")
                    except:
                        pass
                else:
                    status["api_connection"] = False
                    error_data = response.json()
                    status["api_error"] = error_data.get("error", {}).get("message", "Unknown error")
                    status["error_code"] = error_data.get("error", {}).get("code")
            except Exception as e:
                status["api_connection"] = False
                status["api_error"] = str(e)

        return status

    def _create_media_container(
        self,
        image_url: str,
        caption: str = "",
        is_carousel_item: bool = False
    ) -> Optional[str]:
        """
        Create a media container for an image.

        Instagram requires images to be hosted on a public URL.

        Args:
            image_url: Public URL of the image
            caption: Post caption (only for non-carousel items)
            is_carousel_item: Whether this is part of a carousel

        Returns:
            Container ID or None if failed
        """
        url = f"{self.API_BASE}/{self.ig_user_id}/media"

        params = {
            "image_url": image_url,
            "access_token": self.access_token
        }

        if is_carousel_item:
            params["is_carousel_item"] = "true"
        else:
            params["caption"] = caption[:self.CAPTION_MAX_LENGTH]

        try:
            response = requests.post(url, params=params, timeout=60)

            if response.status_code == 200:
                return response.json().get("id")
            else:
                error = response.json().get("error", {})
                print(f"Failed to create media container: {error.get('message', 'Unknown error')}")
                return None

        except requests.RequestException as e:
            print(f"Error creating media container: {e}")
            return None

    def _create_carousel_container(
        self,
        children_ids: List[str],
        caption: str = ""
    ) -> Optional[str]:
        """
        Create a carousel container from multiple media containers.

        Args:
            children_ids: List of media container IDs
            caption: Post caption

        Returns:
            Carousel container ID or None if failed
        """
        url = f"{self.API_BASE}/{self.ig_user_id}/media"

        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption[:self.CAPTION_MAX_LENGTH],
            "access_token": self.access_token
        }

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

        Instagram processes media asynchronously. We need to poll until ready.

        Args:
            container_id: The container ID to check
            max_attempts: Maximum number of polling attempts

        Returns:
            True if ready, False if failed or timeout
        """
        url = f"{self.API_BASE}/{container_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self.access_token
        }

        for attempt in range(max_attempts):
            try:
                response = requests.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    status_code = data.get("status_code")

                    if status_code == "FINISHED":
                        return True
                    elif status_code == "ERROR":
                        print(f"Container processing failed: {data.get('status')}")
                        return False
                    elif status_code in ["IN_PROGRESS", "PUBLISHED"]:
                        # Still processing, wait and retry
                        time.sleep(2)
                        continue
                    else:
                        # Unknown status, wait and retry
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
        Publish a media container to Instagram.

        Args:
            container_id: The container ID to publish

        Returns:
            Response dict with media ID or None if failed
        """
        url = f"{self.API_BASE}/{self.ig_user_id}/media_publish"

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

    def validate_token_before_publish(self) -> Dict[str, Any]:
        """Validate token status before attempting to publish."""
        token_status = self.get_token_status()

        if token_status.get("is_expired") == True:
            return {
                "valid": False,
                "error": "Instagram access token has EXPIRED",
                "token_expired": True,
                "error_detail": (
                    f"Token expired at: {token_status.get('expires_at', 'unknown')}\n\n"
                    "To fix:\n"
                    "1. Go to https://developers.facebook.com/tools/explorer/\n"
                    "2. Generate a new User Access Token\n"
                    "3. Select permissions: instagram_basic, instagram_content_publish, pages_read_engagement\n"
                    "4. Update INSTAGRAM_ACCESS_TOKEN in .env\n"
                    "5. Exchange for long-lived token"
                ),
                "token_status": token_status
            }

        # Try auto-refresh if needed
        if token_status.get("needs_refresh") and token_status.get("has_app_credentials"):
            refresh_result = self.auto_refresh_if_needed()
            if refresh_result.get("success"):
                return {"valid": True, "refreshed": True}

        return {"valid": True}

    def publish(
        self,
        content: str,
        media_urls: Optional[List[str]] = None,
        is_carousel: bool = False
    ) -> Dict[str, Any]:
        """
        Publish a post to Instagram.

        Note: Instagram requires images to be hosted on PUBLIC URLs.
        Local files must be uploaded to a public server first.

        Args:
            content: Post caption
            media_urls: List of public image URLs (required)
            is_carousel: Whether to post as carousel (multiple images)

        Returns:
            Dictionary with success status, post ID, URL, etc.
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": f"Instagram not configured: {'; '.join(self.config_errors)}"
            }

        # Clean metadata before publishing
        content = clean_metadata(content, 'instagram')

        # Validate token before publishing
        token_check = self.validate_token_before_publish()
        if not token_check.get("valid"):
            return {
                "success": False,
                "error": token_check.get("error", "Token validation failed"),
                "token_expired": token_check.get("token_expired", False),
                "error_detail": token_check.get("error_detail", "")
            }

        if not media_urls or len(media_urls) == 0:
            return {
                "success": False,
                "error": "Instagram requires at least one image URL"
            }

        # Truncate caption
        caption = content[:self.CAPTION_MAX_LENGTH]

        try:
            if is_carousel and len(media_urls) > 1:
                # Create carousel post
                children_ids = []

                for url in media_urls[:self.CAROUSEL_MAX_ITEMS]:
                    container_id = self._create_media_container(
                        image_url=url,
                        is_carousel_item=True
                    )
                    if container_id:
                        children_ids.append(container_id)

                if not children_ids:
                    return {
                        "success": False,
                        "error": "Failed to create any media containers"
                    }

                # Wait for all containers to be ready
                for container_id in children_ids:
                    if not self._check_container_status(container_id):
                        return {
                            "success": False,
                            "error": f"Container {container_id} failed processing"
                        }

                # Create carousel container
                carousel_id = self._create_carousel_container(children_ids, caption)
                if not carousel_id:
                    return {
                        "success": False,
                        "error": "Failed to create carousel container"
                    }

                # Wait for carousel to be ready
                if not self._check_container_status(carousel_id):
                    return {
                        "success": False,
                        "error": "Carousel container failed processing"
                    }

                # Publish carousel
                result = self._publish_container(carousel_id)

            else:
                # Single image post
                container_id = self._create_media_container(
                    image_url=media_urls[0],
                    caption=caption
                )

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
                media_id = result["id"]
                return {
                    "success": True,
                    "postId": media_id,
                    "url": f"https://www.instagram.com/p/{media_id}/",
                    "mediaCount": len(media_urls) if is_carousel else 1
                }
            else:
                return {
                    "success": False,
                    "error": "Publishing failed - no media ID returned"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }

    def get_instagram_user_id(self) -> Optional[str]:
        """
        Get the Instagram Business Account ID from a Facebook Page.

        This is useful during initial setup.

        Returns:
            Instagram Business Account ID or None
        """
        if not self.page_id:
            print("FACEBOOK_PAGE_ID is required to get Instagram account ID")
            return None

        url = f"{self.API_BASE}/{self.page_id}"
        params = {
            "fields": "instagram_business_account",
            "access_token": self.access_token
        }

        try:
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                ig_account = data.get("instagram_business_account", {})
                return ig_account.get("id")
            else:
                print(f"Failed to get IG account: {response.text}")
                return None

        except requests.RequestException as e:
            print(f"Error getting IG account: {e}")
            return None

    def convert_local_to_public_urls(self, local_paths: List[str]) -> List[str]:
        """
        Convert local file paths to public URLs using the media server.

        This enables publishing local images through the PostAll server.
        Requires SERVER_BASE_URL to be configured in .env.

        Args:
            local_paths: List of local file paths (absolute or relative to output/)

        Returns:
            List of public URLs (empty strings for failed conversions)
        """
        if not MEDIA_SERVER_AVAILABLE:
            print("Warning: Media server module not available")
            return [""] * len(local_paths)

        if not SERVER_BASE_URL:
            print("Warning: SERVER_BASE_URL not configured in .env")
            print("Set SERVER_BASE_URL=http://your-server:8080 to enable local image publishing")
            return [""] * len(local_paths)

        media_server = MediaServer()
        urls = []

        for path in local_paths:
            url = media_server.generate_public_url(path)
            if url:
                urls.append(url)
                print(f"   Generated URL: {url}")
            else:
                urls.append("")
                print(f"   Warning: Could not generate URL for {path}")

        return urls

    def publish_local_images(
        self,
        content: str,
        local_image_paths: List[str],
        is_carousel: bool = False
    ) -> Dict[str, Any]:
        """
        Publish a post with local images (converts to public URLs automatically).

        This is the preferred method for cloud deployments where images are
        generated and stored locally on the server.

        Automatically validates and adjusts image aspect ratios to meet
        Instagram's requirements (4:5 to 1.91:1).

        Args:
            content: Post caption
            local_image_paths: List of local image file paths
            is_carousel: Whether to post as carousel (multiple images)

        Returns:
            Dictionary with success status, post ID, URL, etc.
        """
        if not local_image_paths:
            return {
                "success": False,
                "error": "No image paths provided"
            }

        # Check if SERVER_BASE_URL is configured
        if not SERVER_BASE_URL:
            return {
                "success": False,
                "error": "SERVER_BASE_URL not configured. Set SERVER_BASE_URL in .env to your server's public URL (e.g., http://your-server:8080)"
            }

        # Validate and adjust image aspect ratios
        adjusted_paths = []
        for path in local_image_paths:
            is_valid, ratio, message = self._validate_aspect_ratio(path)

            if is_valid:
                adjusted_paths.append(path)
                print(f"   Image OK: {Path(path).name} ({message})")
            else:
                print(f"   Image needs adjustment: {Path(path).name} ({message})")
                adjusted_path = self._adjust_image_aspect_ratio(path)

                if adjusted_path:
                    adjusted_paths.append(adjusted_path)
                else:
                    # Adjustment failed, try original anyway
                    print(f"   Warning: Could not adjust {Path(path).name}, using original")
                    adjusted_paths.append(path)

        # Convert local paths to public URLs
        public_urls = self.convert_local_to_public_urls(adjusted_paths)

        # Filter out empty URLs
        valid_urls = [url for url in public_urls if url]

        if not valid_urls:
            self._cleanup_temp_files()
            return {
                "success": False,
                "error": "Could not convert any local paths to public URLs. Check SERVER_BASE_URL configuration."
            }

        # Publish using standard method
        result = self.publish(
            content=content,
            media_urls=valid_urls,
            is_carousel=is_carousel and len(valid_urls) > 1
        )

        # Clean up temporary files
        self._cleanup_temp_files()

        return result

    def get_image_serving_status(self) -> Dict[str, Any]:
        """Check if image serving is properly configured for Instagram."""
        return {
            "media_server_available": MEDIA_SERVER_AVAILABLE,
            "server_base_url_configured": bool(SERVER_BASE_URL),
            "server_base_url": SERVER_BASE_URL if SERVER_BASE_URL else "NOT SET",
            "output_dir": str(OUTPUT_DIR),
            "ready_for_local_images": MEDIA_SERVER_AVAILABLE and bool(SERVER_BASE_URL),
            "setup_instructions": (
                "To publish local images to Instagram:\n"
                "1. Set SERVER_BASE_URL in .env to your server's public URL\n"
                "   Example: SERVER_BASE_URL=http://YOUR_SERVER_IP:8080\n"
                "2. Ensure port 8080 is accessible from the internet\n"
                "3. Use publish_local_images() method with local file paths"
            ) if not (MEDIA_SERVER_AVAILABLE and SERVER_BASE_URL) else "Ready to publish local images"
        }


def check_instagram_status():
    """Check and print Instagram publisher status."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()

    console.print(Panel(
        "Instagram Publisher Status\nChecking configuration...",
        title="",
        border_style="blue"
    ))

    try:
        publisher = InstagramPublisher()
        status = publisher.check_status()

        table = Table(title="Instagram Configuration Status")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Enabled", "Yes" if status['enabled'] else "No")
        table.add_row("Configured", "Yes" if status['configured'] else "No")
        table.add_row("Access Token", "Set" if status['has_access_token'] else "Not set")
        table.add_row("IG User ID", status.get('ig_user_id') or "Not set")
        table.add_row("Page ID", status.get('page_id') or "Not set")

        if status.get('api_connection'):
            table.add_row("API Connection", "Connected")
            if status.get('username'):
                table.add_row("Username", f"@{status['username']}")
            if status.get('account_id'):
                table.add_row("Account ID", str(status['account_id']))
        elif status['configured']:
            table.add_row("API Connection", "Failed")
            if status.get('api_error'):
                table.add_row("Error", status['api_error'])

        console.print(table)

        # Show token status
        token_status = status.get('token_status', {})
        console.print("")
        table_token = Table(title="Access Token Status")
        table_token.add_column("Setting", style="cyan")
        table_token.add_column("Value", style="green")

        table_token.add_row("Token Type", token_status.get('token_type', 'unknown'))
        table_token.add_row("Has App Credentials", "Yes" if token_status.get('has_app_credentials') else "No")

        expires_at = token_status.get('expires_at', 'unknown')
        is_expired = token_status.get('is_expired')

        if is_expired == True:
            table_token.add_row("Status", "[red]EXPIRED[/red]")
            table_token.add_row("Expires At", expires_at)
        elif is_expired == False:
            days_remaining = token_status.get('days_remaining', 0)
            if days_remaining < 7:
                table_token.add_row("Status", f"[yellow]Expires soon ({days_remaining} days)[/yellow]")
            else:
                table_token.add_row("Status", f"[green]Valid ({days_remaining} days remaining)[/green]")
            table_token.add_row("Expires At", expires_at)
        else:
            table_token.add_row("Status", "[yellow]Unknown (no expiration info)[/yellow]")

        console.print(table_token)

        # Show token management instructions if needed
        if is_expired == True:
            console.print(Panel(
                """[bold red]Token Expired![/bold red]

Your Instagram access token has expired. To fix:

[bold]Option 1: Generate new token from Graph API Explorer[/bold]
1. Go to https://developers.facebook.com/tools/explorer/
2. Select your app
3. Select permissions: instagram_basic, instagram_content_publish, pages_read_engagement
4. Select your Page and generate token
5. Update INSTAGRAM_ACCESS_TOKEN in .env

[bold]Option 2: Exchange for long-lived token (recommended)[/bold]
After getting a new token, immediately exchange it for a long-lived token (60 days):

  from postall.publishers.instagram_publisher import InstagramPublisher
  pub = InstagramPublisher()
  result = pub.exchange_for_long_lived_token()
  print(result)

This requires META_APP_ID and META_APP_SECRET in .env.""",
                title="Token Expired",
                border_style="red"
            ))
        elif token_status.get('needs_refresh') == True and not is_expired:
            console.print(Panel(
                f"""[bold yellow]Token Expires Soon![/bold yellow]

Your token expires in {token_status.get('days_remaining', 0)} days.

To refresh (requires META_APP_ID and META_APP_SECRET):

  from postall.publishers.instagram_publisher import InstagramPublisher
  pub = InstagramPublisher()
  result = pub.refresh_long_lived_token()
  print(result)""",
                title="Token Refresh Recommended",
                border_style="yellow"
            ))
        elif token_status.get('token_type') == 'unknown' and token_status.get('has_app_credentials'):
            console.print(Panel(
                """[bold]Tip: Exchange for Long-Lived Token[/bold]

Your token expiration is unknown. If you have a short-lived token (1-2 hours),
exchange it for a long-lived token (60 days):

  from postall.publishers.instagram_publisher import InstagramPublisher
  pub = InstagramPublisher()
  result = pub.exchange_for_long_lived_token()
  print(result)""",
                title="Token Management",
                border_style="blue"
            ))

        # Show image serving status
        image_status = publisher.get_image_serving_status()
        console.print("")
        table2 = Table(title="Image Serving Status (for local images)")
        table2.add_column("Setting", style="cyan")
        table2.add_column("Value", style="green")

        table2.add_row("Media Server Available", "Yes" if image_status['media_server_available'] else "No")
        table2.add_row("SERVER_BASE_URL", image_status['server_base_url'])
        table2.add_row("Ready for Local Images", "Yes" if image_status['ready_for_local_images'] else "No")

        console.print(table2)

        if not image_status['ready_for_local_images']:
            console.print(Panel(
                f"[yellow]{image_status['setup_instructions']}[/yellow]",
                title="Local Image Setup",
                border_style="yellow"
            ))

        if status['errors']:
            console.print("\n[red]Errors:[/red]")
            for error in status['errors']:
                console.print(f"  [red]x[/red] {error}")

        if not status['configured']:
            console.print(Panel(
                """[bold]Setup Instructions:[/bold]

1. Go to https://developers.facebook.com/apps
2. Create a new app (Business type) or select existing
3. Add 'Instagram Graph API' product
4. Connect your Instagram Business/Creator account to a Facebook Page
5. Generate a User Access Token with permissions:
   - instagram_basic
   - instagram_content_publish
   - pages_read_engagement
6. Get your Instagram Business Account ID from the Page
7. Set environment variables in PostAll/.env:
   INSTAGRAM_ENABLED=true
   INSTAGRAM_ACCESS_TOKEN=your_token
   INSTAGRAM_BUSINESS_ACCOUNT_ID=your_ig_id
   FACEBOOK_PAGE_ID=your_page_id (optional)
   META_APP_ID=your_app_id (for token refresh)
   META_APP_SECRET=your_app_secret (for token refresh)

[yellow]Note: App Review required for instagram_content_publish permission![/yellow]

[bold]Token Lifecycle:[/bold]
- Short-lived tokens: ~1-2 hours (from Graph API Explorer)
- Long-lived tokens: 60 days (exchange short-lived token)
- Refresh: Can refresh long-lived tokens before expiry""",
                title="To Configure Instagram Publishing",
                border_style="yellow"
            ))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_instagram_status()
