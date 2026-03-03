"""
LinkedIn Publisher for PostAll

Uses LinkedIn Posts API for programmatic post creation.
Documentation: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api

Authentication: OAuth 2.0 with refresh tokens (tokens expire in 60 days)
Required scopes: w_member_social, openid, profile, email
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from postall.config import (
    LINKEDIN_ACCESS_TOKEN,
    LINKEDIN_REFRESH_TOKEN,
    LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_PERSON_URN,
    LINKEDIN_ENABLED,
    POSTALL_ROOT
)
from postall.publishers import clean_metadata


class LinkedInPublisher:
    """Publish posts to LinkedIn via LinkedIn Posts API."""

    # LinkedIn API base URLs
    API_BASE = "https://api.linkedin.com"
    REST_API = "https://api.linkedin.com/rest"

    # LinkedIn API version (YYYYMM format)
    # Versions are valid for ~12 months. Update when you see NONEXISTENT_VERSION errors.
    # Check https://learn.microsoft.com/en-us/linkedin/marketing/versioning for current versions.
    API_VERSION = "202506"  # Valid version that works

    # LinkedIn content limits
    COMMENTARY_MAX_LENGTH = 3000  # LinkedIn post character limit
    TITLE_MAX_LENGTH = 200
    DESCRIPTION_MAX_LENGTH = 300

    # Rate limits
    MEMBER_DAILY_LIMIT = 150  # Posts per member per day
    APP_DAILY_LIMIT = 100000  # Posts per app per day

    def __init__(self):
        """Initialize the LinkedIn publisher."""
        self.access_token = LINKEDIN_ACCESS_TOKEN
        self.refresh_token = LINKEDIN_REFRESH_TOKEN
        self.client_id = LINKEDIN_CLIENT_ID
        self.client_secret = LINKEDIN_CLIENT_SECRET
        self.person_urn = LINKEDIN_PERSON_URN

        # Token file for storing refreshed tokens
        self.token_file = POSTALL_ROOT / ".linkedin_tokens.json"

        # Load saved tokens if available
        self._load_saved_tokens()

        # Check configuration
        self._check_configuration()

    def _check_configuration(self):
        """Check if LinkedIn publishing is properly configured."""
        self.is_configured = False
        self.config_errors = []

        if not LINKEDIN_ENABLED:
            self.config_errors.append("LINKEDIN_ENABLED is not set to true")
            return

        if not self.access_token:
            self.config_errors.append("LINKEDIN_ACCESS_TOKEN is not set")
            return

        if not self.person_urn:
            self.config_errors.append("LINKEDIN_PERSON_URN is not set (required for post author)")
            return

        # Validate URN format
        if not self.person_urn.startswith("urn:li:person:"):
            self.config_errors.append(
                f"LINKEDIN_PERSON_URN format invalid. Expected 'urn:li:person:xxx', got '{self.person_urn}'"
            )
            return

        # Validate token format
        if len(self.access_token) < 10:
            self.config_errors.append("LINKEDIN_ACCESS_TOKEN appears invalid (too short)")
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
                    if not self.person_urn and tokens.get("person_urn"):
                        self.person_urn = tokens["person_urn"]
            except (json.JSONDecodeError, IOError):
                pass

    def _save_tokens(self):
        """Save tokens to file for persistence."""
        try:
            with open(self.token_file, 'w') as f:
                json.dump({
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "person_urn": self.person_urn,
                    "updated_at": datetime.now().isoformat()
                }, f)
        except IOError as e:
            print(f"Warning: Could not save LinkedIn tokens: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": self.API_VERSION
        }

    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using the refresh token.

        LinkedIn access tokens expire in 60 days.

        Returns:
            True if refresh successful, False otherwise
        """
        if not self.refresh_token or not self.client_id or not self.client_secret:
            print("Cannot refresh token: Missing refresh_token, client_id, or client_secret")
            return False

        url = "https://www.linkedin.com/oauth/v2/accessToken"

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        try:
            response = requests.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                # LinkedIn may return a new refresh token
                if token_data.get("refresh_token"):
                    self.refresh_token = token_data["refresh_token"]

                self._save_tokens()
                print("LinkedIn access token refreshed successfully")
                return True
            else:
                print(f"Token refresh failed: {response.status_code} - {response.text}")
                return False

        except requests.RequestException as e:
            print(f"Token refresh error: {e}")
            return False

    def get_current_member_profile(self) -> Optional[Dict]:
        """
        Get the current authenticated member's profile.

        This retrieves the person URN needed for posting.

        Returns:
            Profile data dict or None if failed
        """
        url = f"{self.REST_API}/me"

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Token might be expired, try refresh
                if self.refresh_access_token():
                    return self.get_current_member_profile()
                return None
            else:
                print(f"Failed to get profile: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            print(f"Error fetching profile: {e}")
            return None

    def check_status(self) -> Dict[str, Any]:
        """Check LinkedIn publisher status and configuration."""
        status = {
            "enabled": LINKEDIN_ENABLED,
            "configured": self.is_configured,
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "has_client_credentials": bool(self.client_id and self.client_secret),
            "person_urn": self.person_urn,
            "api_version": self.API_VERSION,
            "errors": self.config_errors
        }

        # Test API connection if configured
        if self.is_configured:
            try:
                profile = self.get_current_member_profile()
                if profile:
                    status["api_connection"] = True
                    status["member_id"] = profile.get("id")
                    status["member_name"] = f"{profile.get('localizedFirstName', '')} {profile.get('localizedLastName', '')}"
                else:
                    status["api_connection"] = False
            except Exception:
                status["api_connection"] = False

        return status

    def _initialize_image_upload(self, owner_urn: str) -> Optional[Dict]:
        """
        Initialize an image upload to get upload URL and image URN.

        Args:
            owner_urn: The owner URN (person or organization)

        Returns:
            Dict with uploadUrl and image URN, or None if failed
        """
        url = f"{self.REST_API}/images?action=initializeUpload"

        payload = {
            "initializeUploadRequest": {
                "owner": owner_urn
            }
        }

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get("value")
            else:
                print(f"Image upload init failed: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            print(f"Image upload init error: {e}")
            return None

    def _upload_image_binary(self, upload_url: str, image_path: str) -> bool:
        """
        Upload the actual image binary to LinkedIn's upload URL.

        Args:
            upload_url: The URL returned from initializeUpload
            image_path: Path to the local image file

        Returns:
            True if upload successful, False otherwise
        """
        path = Path(image_path)
        if not path.exists():
            print(f"Image not found: {image_path}")
            return False

        # Check file size (LinkedIn limit varies, but generally < 8MB for images)
        file_size = path.stat().st_size
        if file_size > 8 * 1024 * 1024:
            print(f"Image too large: {file_size / 1024 / 1024:.1f}MB (max ~8MB)")
            return False

        # Determine content type
        suffix = path.suffix.lower()
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif'
        }

        content_type = content_types.get(suffix, 'application/octet-stream')

        try:
            with open(path, 'rb') as f:
                image_data = f.read()

            # Upload with minimal headers (LinkedIn's upload URL handles auth)
            response = requests.put(
                upload_url,
                data=image_data,
                headers={
                    "Content-Type": content_type,
                    "Authorization": f"Bearer {self.access_token}"
                },
                timeout=120
            )

            if response.status_code in [200, 201]:
                return True
            else:
                print(f"Image upload failed: {response.status_code} - {response.text[:200]}")
                return False

        except Exception as e:
            print(f"Image upload error: {e}")
            return False

    def upload_image(self, image_path: str) -> Optional[str]:
        """
        Upload an image and return the image URN.

        Args:
            image_path: Path to local image file

        Returns:
            Image URN (urn:li:image:xxx) or None if failed
        """
        # Step 1: Initialize upload
        init_result = self._initialize_image_upload(self.person_urn)
        if not init_result:
            return None

        upload_url = init_result.get("uploadUrl")
        image_urn = init_result.get("image")

        if not upload_url or not image_urn:
            print("Missing uploadUrl or image URN from init response")
            return None

        # Step 2: Upload binary
        if self._upload_image_binary(upload_url, image_path):
            return image_urn
        else:
            return None

    def publish(
        self,
        content: str,
        media_paths: Optional[List[str]] = None,
        link: Optional[str] = None,
        link_title: Optional[str] = None,
        link_description: Optional[str] = None,
        visibility: str = "PUBLIC",
        alt_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a post on LinkedIn.

        Args:
            content: Post commentary/text (max 3000 chars)
            media_paths: List of image paths (first one used)
            link: URL to share as article
            link_title: Title for the link
            link_description: Description for the link
            visibility: "PUBLIC" or "CONNECTIONS"
            alt_text: Alt text for image accessibility

        Returns:
            Dictionary with success status, post ID, URL, etc.
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": f"LinkedIn not configured: {'; '.join(self.config_errors)}"
            }

        # Clean metadata before publishing
        content = clean_metadata(content, 'linkedin')

        # Truncate content if needed
        commentary = content[:self.COMMENTARY_MAX_LENGTH]

        # Build base payload
        payload = {
            "author": self.person_urn,
            "commentary": commentary,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False
        }

        # Handle media (image post)
        if media_paths and len(media_paths) > 0:
            image_path = media_paths[0]  # LinkedIn supports single image for basic posts

            # Check if it's a URL or local file
            if image_path.startswith('http://') or image_path.startswith('https://'):
                # For URLs, we need to download and re-upload to LinkedIn
                # For simplicity, treat as article share if URL provided
                payload["content"] = {
                    "article": {
                        "source": image_path,
                        "title": link_title or "Shared content",
                        "description": link_description or ""
                    }
                }
            else:
                # Local file - upload to LinkedIn
                image_urn = self.upload_image(image_path)
                if image_urn:
                    payload["content"] = {
                        "media": {
                            "id": image_urn
                        }
                    }
                    if alt_text:
                        payload["content"]["media"]["altText"] = alt_text[:300]
                else:
                    return {
                        "success": False,
                        "error": f"Failed to upload image: {image_path}"
                    }

        # Handle link share (article)
        elif link:
            payload["content"] = {
                "article": {
                    "source": link,
                    "title": link_title[:self.TITLE_MAX_LENGTH] if link_title else "",
                    "description": link_description[:self.DESCRIPTION_MAX_LENGTH] if link_description else ""
                }
            }

        # Make API request
        url = f"{self.REST_API}/posts"

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=60
            )

            if response.status_code == 201:
                # Success - get post ID from header
                post_id = response.headers.get("x-restli-id", "")

                # Extract the numeric ID for URL construction
                # Format: urn:li:share:1234567890 or urn:li:ugcPost:1234567890
                activity_id = post_id.split(":")[-1] if post_id else ""

                return {
                    "success": True,
                    "postId": post_id,
                    "url": f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None,
                    "response": response.json() if response.text else {}
                }

            elif response.status_code == 401:
                # Token expired - try refresh
                if self.refresh_access_token():
                    return self.publish(content, media_paths, link, link_title, link_description, visibility, alt_text)
                else:
                    return {
                        "success": False,
                        "error": "Authentication failed and token refresh unsuccessful"
                    }

            elif response.status_code == 429:
                # Rate limited
                return {
                    "success": False,
                    "error": f"Rate limit exceeded (max {self.MEMBER_DAILY_LIMIT}/day). Try again tomorrow.",
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
        link: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish a post using images from a folder.

        Args:
            content: Post text
            image_folder: Path to folder containing images
            link: Optional destination URL

        Returns:
            Publish result
        """
        # Find images in folder
        image_paths = []
        if image_folder.exists():
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.gif"]:
                image_paths.extend([str(p) for p in image_folder.glob(ext)])

        if image_paths:
            # Use first image
            return self.publish(
                content=content,
                media_paths=[image_paths[0]],
                link=link
            )
        else:
            # Text-only post
            return self.publish(content=content, link=link)


def check_linkedin_status():
    """Check and print LinkedIn publisher status."""
    print("\n LinkedIn Publisher Status Check\n")
    print("=" * 50)

    try:
        publisher = LinkedInPublisher()
        status = publisher.check_status()

        print(f"Enabled: {'Yes' if status['enabled'] else 'No'}")
        print(f"Configured: {'Yes' if status['configured'] else 'No'}")
        print(f"Access Token: {'Set' if status['has_access_token'] else 'Not set'}")
        print(f"Refresh Token: {'Set' if status['has_refresh_token'] else 'Not set'}")
        print(f"Client Credentials: {'Set' if status['has_client_credentials'] else 'Not set'}")
        print(f"Person URN: {status['person_urn'] or 'Not set'}")
        print(f"API Version: {status['api_version']}")

        if status.get('api_connection'):
            print(f"API Connection: Connected")
            if status.get('member_name'):
                print(f"Member: {status['member_name']}")
        elif status['configured']:
            print(f"API Connection: Failed (token may be expired)")

        if status['errors']:
            print("\nConfiguration Errors:")
            for error in status['errors']:
                print(f"  - {error}")

        if not status['configured']:
            print("\n To configure LinkedIn publishing:")
            print("  1. Go to https://www.linkedin.com/developers/apps")
            print("  2. Create a new app or select existing")
            print("  3. Add 'Share on LinkedIn' product (grants w_member_social)")
            print("  4. Complete OAuth flow to get access token")
            print("  5. Use /me endpoint to get your person URN")
            print("  6. Set environment variables in PostAll/.env:")
            print("     LINKEDIN_ENABLED=true")
            print("     LINKEDIN_ACCESS_TOKEN=your_access_token")
            print("     LINKEDIN_REFRESH_TOKEN=your_refresh_token")
            print("     LINKEDIN_CLIENT_ID=your_client_id")
            print("     LINKEDIN_CLIENT_SECRET=your_client_secret")
            print("     LINKEDIN_PERSON_URN=urn:li:person:your_id")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_linkedin_status()
