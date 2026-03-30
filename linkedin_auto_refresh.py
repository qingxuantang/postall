#!/usr/bin/env python3
"""
LinkedIn Token Auto-Refresh Script

Usage:
    python3 linkedin_auto_refresh.py          # Refresh and print new token
    python3 linkedin_auto_refresh.py --test   # Test current token validity
    python3 linkedin_auto_refresh.py --init <access_token> <refresh_token>
    
Tokens are stored in: projects/tar/.linkedin_tokens.json

Setup:
1. Create a LinkedIn App at https://www.linkedin.com/developers/
2. Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET below or as env vars
3. Get initial tokens via OAuth flow
4. Run --init with your tokens
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# Token storage (relative to project)
TOKEN_FILE = Path(__file__).parent / "projects/tar/.linkedin_tokens.json"

# LinkedIn OAuth settings - set these or use environment variables
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "YOUR_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "YOUR_CLIENT_SECRET")


def load_tokens():
    """Load tokens from file."""
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return {}


def save_tokens(tokens):
    """Save tokens to file."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)
    print(f"✅ Tokens saved to {TOKEN_FILE}")


def test_token(access_token):
    """Test if access token is valid."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202506",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    resp = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
    return resp.status_code == 200


def refresh_access_token(refresh_token):
    """Use refresh token to get new access token."""
    if LINKEDIN_CLIENT_ID == "YOUR_CLIENT_ID":
        print("❌ Please set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET")
        return None
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET
    }
    
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if resp.status_code == 200:
        result = resp.json()
        return {
            "access_token": result.get("access_token"),
            "refresh_token": result.get("refresh_token", refresh_token),
            "expires_in": result.get("expires_in", 5184000),  # Default 60 days
            "refreshed_at": datetime.now().isoformat()
        }
    else:
        print(f"❌ Refresh failed: {resp.status_code} - {resp.text}")
        return None


def get_valid_token():
    """Get a valid access token, refreshing if necessary."""
    tokens = load_tokens()
    
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    
    if not access_token and not refresh_token:
        print("❌ No tokens found. Please run --init with your tokens first.")
        return None
    
    # Test current access token
    if access_token and test_token(access_token):
        print("✅ Current access token is valid")
        return access_token
    
    # Try to refresh
    print("🔄 Access token expired, refreshing...")
    if not refresh_token:
        print("❌ No refresh token available")
        return None
    
    new_tokens = refresh_access_token(refresh_token)
    if new_tokens:
        tokens.update(new_tokens)
        save_tokens(tokens)
        print("✅ Token refreshed successfully")
        return new_tokens["access_token"]
    
    return None


def init_tokens(access_token, refresh_token):
    """Initialize tokens from provided values."""
    tokens = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "initialized_at": datetime.now().isoformat()
    }
    save_tokens(tokens)
    return tokens


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--init":
        if len(sys.argv) < 4:
            print("Usage: python3 linkedin_auto_refresh.py --init <access_token> <refresh_token>")
            sys.exit(1)
        init_tokens(sys.argv[2], sys.argv[3])
        print("✅ Tokens initialized")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        tokens = load_tokens()
        if tokens.get("access_token") and test_token(tokens["access_token"]):
            print("✅ Token is valid")
        else:
            print("❌ Token is invalid or expired")
    
    else:
        token = get_valid_token()
        if token:
            print(f"\n✅ Valid access token obtained")
