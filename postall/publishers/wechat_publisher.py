"""
WeChat Public Account Publisher for PostAll

Uses limyai.com API for publishing to WeChat public accounts.
Adapted from BIP project's wechat_api.py.

API Documentation: https://wx.limyai.com (Open Platform section)
"""

import requests
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from postall.config import (
    WECHAT_ENABLED,
    WECHAT_API_KEY,
    WECHAT_ACCOUNT_ID,
)
from postall.publishers import clean_metadata


def upload_image_to_catbox(image_path: str) -> Optional[str]:
    """Upload an image to catbox.moe and return the URL."""
    file_path = Path(image_path)
    if not file_path.exists():
        return None

    url = "https://catbox.moe/user/api.php"
    try:
        with open(file_path, "rb") as f:
            files = {"fileToUpload": (file_path.name, f)}
            data = {"reqtype": "fileupload"}
            response = requests.post(url, data=data, files=files, timeout=60)

        if response.status_code == 200 and response.text.startswith("https://"):
            return response.text.strip()
        return None
    except Exception:
        return None


class WeChatPublisher:
    """Publish posts to WeChat public accounts via limyai.com API."""

    BASE_URL = "https://wx.limyai.com/api/openapi"
    REQUEST_TIMEOUT = 60

    def __init__(self):
        """Initialize the WeChat publisher."""
        self.api_key = WECHAT_API_KEY
        self.wechat_app_id = WECHAT_ACCOUNT_ID
        self.is_configured = False
        self.config_errors = []

        if not WECHAT_ENABLED:
            self.config_errors.append("WECHAT_ENABLED is not set to true")
            return
        if not self.api_key:
            self.config_errors.append("WECHAT_API_KEY is not set")
            return

        self.is_configured = True
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an API request."""
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.session.request(method, url, timeout=self.REQUEST_TIMEOUT, **kwargs)
            try:
                data = response.json()
            except Exception:
                data = {}

            if response.status_code >= 400:
                error_msg = data.get("error", data.get("message", f"HTTP {response.status_code}"))
                raise Exception(f"API error: {error_msg}")

            if not data.get("success", True):
                error_msg = data.get("message", data.get("error", "Unknown error"))
                raise Exception(f"API error: {error_msg}")

            return data
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")

    def _get_wechat_app_id(self) -> str:
        """Get the WeChat App ID to use for publishing."""
        if self.wechat_app_id:
            return self.wechat_app_id

        # Fetch first available account
        data = self._request("POST", "wechat-accounts")
        accounts = []
        if isinstance(data.get("data"), list):
            accounts = data["data"]
        elif isinstance(data.get("data"), dict):
            nested = data["data"]
            for key in ["accounts", "list", "items"]:
                if isinstance(nested.get(key), list):
                    accounts = nested[key]
                    break

        if not accounts:
            raise ValueError("No WeChat accounts available.")

        first = accounts[0]
        if isinstance(first, dict):
            self.wechat_app_id = first.get("wechatAppid") or first.get("wechatAppId") or first.get("id")
        else:
            self.wechat_app_id = str(first)

        print(f"   Using WeChat account: {self.wechat_app_id}")
        return self.wechat_app_id

    def publish(
        self,
        content: str,
        media_paths: Optional[List[str]] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        cover_image_url: Optional[str] = None,
        author: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Publish content to WeChat public account.

        Args:
            content: Article content (Markdown format)
            media_paths: Optional list of image paths
            title: Article title (max 64 chars)
            summary: Article summary (max 120 chars)
            cover_image_url: Cover image URL
            author: Author name

        Returns:
            Result dictionary
        """
        print("📤 Publishing to WeChat via limyai.com API...")

        if not self.is_configured:
            return {"success": False, "error": "WeChat not configured", "platform": "wechat"}

        # Clean metadata before publishing (wechat keeps ### subheadings)
        content = clean_metadata(content, 'wechat')

        try:
            wechat_app_id = self._get_wechat_app_id()

            # Upload cover image if needed
            if media_paths and not cover_image_url:
                for path in media_paths:
                    url = upload_image_to_catbox(path)
                    if url:
                        cover_image_url = url
                        break

            # Extract title from content if not provided
            if not title:
                for line in content.strip().split('\n'):
                    line = line.strip()
                    if line:
                        title = line.lstrip('#').strip()
                        break
                title = title or "Update"

            if len(title) > 64:
                title = title[:61] + "..."

            payload = {
                "wechatAppid": wechat_app_id,
                "title": title,
                "content": content,
                "contentFormat": "markdown",
                "articleType": "news"
            }

            if summary:
                payload["summary"] = summary[:120]
            if cover_image_url:
                payload["coverImage"] = cover_image_url
            if author:
                payload["author"] = author

            data = self._request("POST", "wechat-publish", json=payload)

            result_data = data.get("data", {})
            print(f"   ✅ Published to WeChat successfully")

            return {
                "success": True,
                "postId": result_data.get("publicationId"),
                "status": result_data.get("status"),
                "platform": "wechat"
            }

        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Failed to publish to WeChat: {error_msg}")
            return {"success": False, "error": error_msg, "platform": "wechat"}
