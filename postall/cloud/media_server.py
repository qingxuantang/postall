"""
Media Server for PostAll Cloud

Provides public URLs for generated images to support Instagram API publishing.
Instagram Graph API requires images to be hosted on publicly accessible URLs.

This module:
1. Serves static files from the output directory via HTTP
2. Generates public URLs for local image files
3. Validates and secures file access
"""

import os
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import quote

from postall.config import OUTPUT_DIR, POSTALL_ROOT


# Environment variable for server's public URL
# Example: https://your-server.com:8080 or http://your-ip:8080
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")


class MediaServer:
    """
    Serves media files from the output directory.

    Security measures:
    - Only serves files from allowed directories (output/)
    - Only serves allowed file types (images, markdown)
    - Path traversal prevention
    """

    # Allowed file extensions for serving
    ALLOWED_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.webp',  # Images
        '.mp4', '.mov',  # Video (if needed)
        '.md', '.json',  # Content files
    }

    # MIME type mappings
    MIME_TYPES = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.md': 'text/markdown',
        '.json': 'application/json',
    }

    def __init__(self, base_dir: Path = None):
        """
        Initialize the media server.

        Args:
            base_dir: Base directory for serving files (default: OUTPUT_DIR)
        """
        self.base_dir = Path(base_dir) if base_dir else OUTPUT_DIR
        self.base_dir = self.base_dir.resolve()

    def is_allowed_path(self, file_path: Path) -> bool:
        """
        Check if file path is allowed to be served.

        Prevents path traversal attacks and restricts to allowed directories.
        """
        try:
            resolved = file_path.resolve()
            # Must be within base directory
            resolved.relative_to(self.base_dir)
            return True
        except ValueError:
            return False

    def is_allowed_extension(self, file_path: Path) -> bool:
        """Check if file extension is allowed."""
        return file_path.suffix.lower() in self.ALLOWED_EXTENSIONS

    def get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for file."""
        ext = file_path.suffix.lower()
        return self.MIME_TYPES.get(ext, 'application/octet-stream')

    def get_file(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file content and metadata for serving.

        Args:
            relative_path: Path relative to base_dir (e.g., "2026-01-13_week3/instagram-posts/images/post1.png")

        Returns:
            Dict with 'content', 'mime_type', 'size' or None if not found/not allowed
        """
        # Clean the path (remove leading slashes)
        clean_path = relative_path.lstrip('/')

        # Build full path
        file_path = self.base_dir / clean_path

        # Security checks
        if not self.is_allowed_path(file_path):
            return None

        if not self.is_allowed_extension(file_path):
            return None

        if not file_path.exists() or not file_path.is_file():
            return None

        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            return {
                'content': content,
                'mime_type': self.get_mime_type(file_path),
                'size': len(content),
                'path': str(file_path),
            }
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None

    def generate_public_url(self, local_path: str) -> Optional[str]:
        """
        Generate public URL for a local file path.

        Args:
            local_path: Absolute or relative path to the file

        Returns:
            Public URL or None if SERVER_BASE_URL not configured
        """
        if not SERVER_BASE_URL:
            return None

        local_path = Path(local_path)

        # If absolute path, make it relative to base_dir
        if local_path.is_absolute():
            try:
                relative_path = local_path.resolve().relative_to(self.base_dir)
            except ValueError:
                # File is outside base_dir, try relative to POSTALL_ROOT/output
                try:
                    relative_path = local_path.resolve().relative_to(POSTALL_ROOT / "output")
                except ValueError:
                    return None
        else:
            # Resolve relative path and make it relative to base_dir
            try:
                relative_path = local_path.resolve().relative_to(self.base_dir)
            except ValueError:
                relative_path = local_path

        # URL-encode the path
        url_path = quote(str(relative_path).replace('\\', '/'))

        # Build full URL
        base = SERVER_BASE_URL.rstrip('/')
        return f"{base}/{url_path}"

    def list_images_in_folder(self, folder_path: str) -> list:
        """
        List all images in a folder.

        Args:
            folder_path: Path relative to base_dir

        Returns:
            List of image file paths (relative to base_dir)
        """
        full_path = self.base_dir / folder_path

        if not self.is_allowed_path(full_path):
            return []

        if not full_path.exists() or not full_path.is_dir():
            return []

        images = []
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

        for file in full_path.iterdir():
            if file.is_file() and file.suffix.lower() in image_extensions:
                try:
                    rel_path = file.relative_to(self.base_dir)
                    images.append(str(rel_path))
                except ValueError:
                    pass

        return sorted(images)


def get_public_image_urls(image_paths: list) -> list:
    """
    Convert local image paths to public URLs.

    Args:
        image_paths: List of local file paths

    Returns:
        List of public URLs (empty strings for failed conversions)
    """
    server = MediaServer()
    urls = []

    for path in image_paths:
        url = server.generate_public_url(path)
        urls.append(url if url else "")

    return urls


def check_media_server_config() -> Dict[str, Any]:
    """Check media server configuration status."""
    return {
        "server_base_url_configured": bool(SERVER_BASE_URL),
        "server_base_url": SERVER_BASE_URL if SERVER_BASE_URL else "NOT SET",
        "output_dir": str(OUTPUT_DIR),
        "output_dir_exists": OUTPUT_DIR.exists(),
        "instructions": (
            "To enable public image URLs for Instagram:\n"
            "1. Set SERVER_BASE_URL in .env to your server's public URL\n"
            "   Example: SERVER_BASE_URL=http://YOUR_SERVER_IP:8080\n"
            "2. Ensure port 8080 is accessible from the internet\n"
            "3. Images will be served at /media/{relative_path}"
        ) if not SERVER_BASE_URL else "Media server is configured"
    }


if __name__ == "__main__":
    # Test the media server
    status = check_media_server_config()
    print("Media Server Configuration:")
    for key, value in status.items():
        print(f"  {key}: {value}")
