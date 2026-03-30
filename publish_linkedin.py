#!/usr/bin/env python3
"""
LinkedIn Publisher with Auto Token Refresh

Usage:
    python3 publish_linkedin.py <content_file> [image_file]
    
This script:
1. Checks if access token is valid
2. Auto-refreshes if expired
3. Publishes to LinkedIn via PostAll Docker container

Prerequisites:
- Set up linkedin_auto_refresh.py with your LinkedIn OAuth credentials
- Initialize tokens with: python3 linkedin_auto_refresh.py --init <access> <refresh>
"""

import os
import sys
import subprocess
from pathlib import Path

# Import the auto-refresh module
sys.path.insert(0, str(Path(__file__).parent))
from linkedin_auto_refresh import get_valid_token


def publish_linkedin(content_file, image_file=None, container_name="postall-tar"):
    """Publish to LinkedIn with auto token refresh."""
    
    # Get valid token (auto-refresh if needed)
    access_token = get_valid_token()
    if not access_token:
        print("❌ Failed to get valid LinkedIn token")
        print("   Run: python3 linkedin_auto_refresh.py --init <access_token> <refresh_token>")
        return False
    
    # Build docker command with the token
    cmd = [
        "sudo", "docker", "exec",
        "-e", f"LINKEDIN_ACCESS_TOKEN={access_token}",
        container_name,
        "python", "/tmp/clean_and_publish.py",
        "linkedin",
        content_file
    ]
    
    if image_file:
        cmd.append(image_file)
    
    print(f"📤 Publishing to LinkedIn...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    return result.returncode == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 publish_linkedin.py <content_file> [image_file]")
        print("")
        print("Prerequisites:")
        print("  1. Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in linkedin_auto_refresh.py")
        print("  2. Initialize tokens: python3 linkedin_auto_refresh.py --init <access> <refresh>")
        sys.exit(1)
    
    content_file = sys.argv[1]
    image_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = publish_linkedin(content_file, image_file)
    sys.exit(0 if success else 1)
