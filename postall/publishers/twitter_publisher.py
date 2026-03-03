"""
Twitter/X Publisher for PostAll

Uses Twitter API v2 directly via tweepy library.
No MCP server required - works in both local and cloud environments.

Documentation: https://developer.twitter.com/en/docs/twitter-api/tweets/manage-tweets/api-reference

Authentication: OAuth 1.0a User Context
Required credentials:
- TWITTER_API_KEY (Consumer Key)
- TWITTER_API_SECRET (Consumer Secret)
- TWITTER_ACCESS_TOKEN (User Access Token)
- TWITTER_ACCESS_SECRET (User Access Token Secret)
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from postall.config import (
    TWITTER_ENABLED,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_BEARER_TOKEN,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET,
)
from postall.publishers import clean_metadata


class TwitterPublisher:
    """Publish posts to Twitter/X via Twitter API v2."""

    # Twitter character limit
    TWEET_CHAR_LIMIT = 280
    # Thread tweet limit (leaving room for numbering)
    THREAD_TWEET_LIMIT = 270

    def __init__(self):
        """Initialize the Twitter publisher."""
        self.api_key = TWITTER_API_KEY
        self.api_secret = TWITTER_API_SECRET
        self.access_token = TWITTER_ACCESS_TOKEN
        self.access_secret = TWITTER_ACCESS_SECRET
        self.bearer_token = TWITTER_BEARER_TOKEN

        self._client = None
        self._api = None

        # Check configuration
        self._check_configuration()

    def _check_configuration(self):
        """Check if Twitter publishing is properly configured."""
        self.is_configured = False
        self.config_errors = []

        if not TWITTER_ENABLED:
            self.config_errors.append("TWITTER_ENABLED is not set to true")
            return

        if not self.api_key:
            self.config_errors.append("TWITTER_API_KEY is not set")
            return

        if not self.api_secret:
            self.config_errors.append("TWITTER_API_SECRET is not set")
            return

        if not self.access_token:
            self.config_errors.append("TWITTER_ACCESS_TOKEN is not set")
            return

        if not self.access_secret:
            self.config_errors.append("TWITTER_ACCESS_SECRET is not set")
            return

        # Try to import tweepy
        try:
            import tweepy
        except ImportError:
            self.config_errors.append(
                "tweepy library not installed. Run: pip install tweepy"
            )
            return

        self.is_configured = True

    def _get_client(self):
        """Get or create Tweepy Client for API v2."""
        if self._client is None:
            import tweepy

            self._client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret,
                bearer_token=self.bearer_token,
                wait_on_rate_limit=False  # Don't sleep on rate limit - let daemon continue with other posts
            )

        return self._client

    def _get_api(self):
        """Get or create Tweepy API for media uploads (API v1.1)."""
        if self._api is None:
            import tweepy

            auth = tweepy.OAuth1UserHandler(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret
            )
            self._api = tweepy.API(auth)

        return self._api

    def check_status(self) -> Dict[str, Any]:
        """Check Twitter publisher status and configuration."""
        status = {
            "enabled": TWITTER_ENABLED,
            "configured": self.is_configured,
            "has_api_key": bool(self.api_key),
            "has_api_secret": bool(self.api_secret),
            "has_access_token": bool(self.access_token),
            "has_access_secret": bool(self.access_secret),
            "has_bearer_token": bool(self.bearer_token),
            "errors": self.config_errors
        }

        # Test API connection if configured
        if self.is_configured:
            try:
                client = self._get_client()
                me = client.get_me()
                if me and me.data:
                    status["api_connection"] = True
                    status["username"] = me.data.username
                    status["user_id"] = me.data.id
                else:
                    status["api_connection"] = False
            except Exception as e:
                status["api_connection"] = False
                status["connection_error"] = str(e)

        return status

    def _upload_media(self, media_path: str) -> Optional[str]:
        """
        Upload media file and return media_id.

        Args:
            media_path: Path to the media file

        Returns:
            Media ID string or None if failed
        """
        path = Path(media_path)
        if not path.exists():
            print(f"Media file not found: {media_path}")
            return None

        try:
            api = self._get_api()
            media = api.media_upload(filename=str(path))
            return str(media.media_id)
        except Exception as e:
            print(f"Media upload failed: {e}")
            return None

    def _split_into_thread(self, content: str) -> List[str]:
        """
        Split long content into multiple tweets for a thread.

        Args:
            content: Full content that may exceed character limit

        Returns:
            List of tweet texts
        """
        if len(content) <= self.TWEET_CHAR_LIMIT:
            return [content]

        tweets = []
        paragraphs = content.split('\n\n')
        current_tweet = ""

        for para in paragraphs:
            # If paragraph itself is too long, split by sentences
            if len(para) > self.THREAD_TWEET_LIMIT:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    if len(current_tweet) + len(sentence) + 1 <= self.THREAD_TWEET_LIMIT:
                        current_tweet += (" " if current_tweet else "") + sentence
                    else:
                        if current_tweet:
                            tweets.append(current_tweet.strip())
                        current_tweet = sentence
            else:
                if len(current_tweet) + len(para) + 2 <= self.THREAD_TWEET_LIMIT:
                    current_tweet += ("\n\n" if current_tweet else "") + para
                else:
                    if current_tweet:
                        tweets.append(current_tweet.strip())
                    current_tweet = para

        if current_tweet:
            tweets.append(current_tweet.strip())

        # Add thread numbering if more than one tweet
        if len(tweets) > 1:
            tweets = [f"{tweet} ({i+1}/{len(tweets)})" for i, tweet in enumerate(tweets)]

        return tweets

    def publish(
        self,
        content: str,
        media_paths: Optional[List[str]] = None,
        as_thread: bool = True
    ) -> Dict[str, Any]:
        """
        Publish a tweet with optional media.

        Args:
            content: Tweet text (will be split into thread if > 280 chars)
            media_paths: Optional list of image paths (max 4)
            as_thread: If True, split long content into thread

        Returns:
            Dictionary with success status, tweet ID, URL, etc.
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": f"Twitter not configured: {'; '.join(self.config_errors)}"
            }

        # Clean metadata before publishing
        content = clean_metadata(content, 'twitter')

        try:
            client = self._get_client()

            # Handle media uploads
            media_ids = []
            if media_paths:
                for path in media_paths[:4]:  # Twitter max 4 images
                    if Path(path).exists():
                        media_id = self._upload_media(path)
                        if media_id:
                            media_ids.append(media_id)
                            print(f"   Uploaded media: {Path(path).name}")

            # Split into thread if needed
            if as_thread and len(content) > self.TWEET_CHAR_LIMIT:
                tweets = self._split_into_thread(content)
            else:
                # Truncate if too long
                tweets = [content[:self.TWEET_CHAR_LIMIT]]

            # Post tweet(s)
            first_tweet_id = None
            last_tweet_id = None
            tweet_ids = []

            for i, tweet_text in enumerate(tweets):
                # Only attach media to first tweet
                tweet_media_ids = media_ids if i == 0 and media_ids else None

                # Reply to previous tweet if in thread
                reply_to = last_tweet_id if last_tweet_id else None

                response = client.create_tweet(
                    text=tweet_text,
                    media_ids=tweet_media_ids,
                    in_reply_to_tweet_id=reply_to
                )

                if response and response.data:
                    tweet_id = response.data['id']
                    tweet_ids.append(tweet_id)

                    if first_tweet_id is None:
                        first_tweet_id = tweet_id
                    last_tweet_id = tweet_id

                    print(f"   Posted tweet {i+1}/{len(tweets)}: {tweet_id}")
                else:
                    return {
                        "success": False,
                        "error": f"Failed to post tweet {i+1}"
                    }

            # Get username for URL
            username = "i"  # Default to generic URL format
            try:
                me = client.get_me()
                if me and me.data:
                    username = me.data.username
            except:
                pass

            return {
                "success": True,
                "postId": first_tweet_id,
                "tweet_ids": tweet_ids,
                "is_thread": len(tweets) > 1,
                "tweet_count": len(tweets),
                "url": f"https://twitter.com/{username}/status/{first_tweet_id}"
            }

        except Exception as e:
            error_msg = str(e)

            # Handle common errors
            if "401" in error_msg or "Unauthorized" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Authentication failed. Check your API credentials."
                }
            elif "403" in error_msg or "Forbidden" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Access forbidden. Your app may need elevated access or the tweet may be duplicate."
                }
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Rate limit exceeded. Try again later."
                }
            elif "duplicate" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Duplicate tweet. Twitter doesn't allow identical tweets."
                }

            return {
                "success": False,
                "error": error_msg
            }

    def publish_with_images(
        self,
        content: str,
        image_folder: Path
    ) -> Dict[str, Any]:
        """
        Publish a tweet with images from a folder.

        Args:
            content: Tweet text
            image_folder: Path to folder containing images

        Returns:
            Publish result
        """
        image_paths = []
        if image_folder.exists():
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.gif"]:
                image_paths.extend([str(p) for p in image_folder.glob(ext)])

        # Limit to 4 images
        image_paths = image_paths[:4]

        return self.publish(content, media_paths=image_paths if image_paths else None)

    def delete_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """
        Delete a tweet.

        Args:
            tweet_id: ID of the tweet to delete

        Returns:
            Result dictionary
        """
        if not self.is_configured:
            return {"success": False, "error": "Twitter not configured"}

        try:
            client = self._get_client()
            response = client.delete_tweet(tweet_id)

            if response and response.data and response.data.get('deleted'):
                return {"success": True, "deleted": True}
            else:
                return {"success": False, "error": "Tweet not deleted"}

        except Exception as e:
            return {"success": False, "error": str(e)}


def check_twitter_status():
    """Check and print Twitter publisher status."""
    print("\n Twitter Publisher Status Check\n")
    print("=" * 50)

    try:
        publisher = TwitterPublisher()
        status = publisher.check_status()

        print(f"Enabled: {'Yes' if status['enabled'] else 'No'}")
        print(f"Configured: {'Yes' if status['configured'] else 'No'}")
        print(f"API Key: {'Set' if status['has_api_key'] else 'Not set'}")
        print(f"API Secret: {'Set' if status['has_api_secret'] else 'Not set'}")
        print(f"Access Token: {'Set' if status['has_access_token'] else 'Not set'}")
        print(f"Access Secret: {'Set' if status['has_access_secret'] else 'Not set'}")
        print(f"Bearer Token: {'Set' if status['has_bearer_token'] else 'Not set'}")

        if status.get('api_connection'):
            print(f"\nAPI Connection: Connected")
            print(f"Username: @{status.get('username', 'unknown')}")
            print(f"User ID: {status.get('user_id', 'unknown')}")
        elif status['configured']:
            print(f"\nAPI Connection: Failed")
            if status.get('connection_error'):
                print(f"Error: {status['connection_error']}")

        if status['errors']:
            print("\nConfiguration Errors:")
            for error in status['errors']:
                print(f"  - {error}")

        if not status['configured']:
            print("\n To configure Twitter publishing:")
            print("  1. Go to https://developer.twitter.com/en/portal/dashboard")
            print("  2. Create a project and app (Free tier allows posting)")
            print("  3. Generate API Key, API Secret, Access Token, Access Secret")
            print("  4. Set environment variables in PostAll/.env:")
            print("     TWITTER_ENABLED=true")
            print("     TWITTER_API_KEY=your_api_key")
            print("     TWITTER_API_SECRET=your_api_secret")
            print("     TWITTER_ACCESS_TOKEN=your_access_token")
            print("     TWITTER_ACCESS_SECRET=your_access_secret")
            print("     TWITTER_BEARER_TOKEN=your_bearer_token (optional)")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_twitter_status()
