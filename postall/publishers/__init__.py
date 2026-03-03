"""
Publishers module for PostAll social media posting.

Provides integration with various social media platforms:
- Twitter/X via Node.js MCP server
- Pinterest via Pinterest API v5
- LinkedIn via LinkedIn Posts API
- Instagram via Instagram Graph API (Meta)
- Threads via Threads API (Meta)
- Xiaohongshu via Playwright automation
"""
import re

def clean_metadata(text: str, platform: str = 'generic') -> str:
    """
    Strip all PostAll metadata from content before publishing.
    
    Removes:
    - # Platform Post X - Day Title headers
    - **Post Type:** / **Theme:** / **Day:** / **Generated:** lines
    - **Posting Time:** / **Content Pillar:** lines
    - ### Image Prompt sections and everything after
    - --- horizontal rules
    
    Args:
        text: Raw content with potential metadata
        platform: Platform name (wechat keeps ### subheadings)
    
    Returns:
        Clean content ready for publishing
    """
    # Remove # Title lines (e.g. "# Twitter Post 1 - Monday Tweet")
    text = re.sub(r'^#\s+(?:Twitter|Linkedin|Instagram|Pinterest|Threads)\s+Post.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # Remove ## headers (title lines like "## Tweet - xxx" or "## LinkedIn Post - xxx")
    text = re.sub(r'^##\s+(?:(?:Twitter|Linkedin|Instagram|Pinterest|Threads)\s+)?(?:Tweet|Post|Pin|Thread)\s*[-–—].*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # Remove all metadata lines: **Key:** Value
    text = re.sub(r'^\*\*Post Type:\*\*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*Theme:\*\*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*Day:\*\*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*Generated:\*\*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*Posting Time:\*\*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*Content Pillar:\*\*.*$', '', text, flags=re.MULTILINE)
    # Remove **Thread (N tweets):** format (2026-03-02 fix)
    text = re.sub(r'^\*\*Thread\s*\(\d+\s*tweets?\):\*\*.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # Remove ### Image Prompt and everything after it
    text = re.split(r'###\s*Image Prompt', text, flags=re.IGNORECASE)[0]
    # Remove ### section headers
    text = re.sub(r'^###\s+.*$', '', text, flags=re.MULTILINE)
    # Remove --- horizontal rules
    text = re.sub(r'^---\s*$', '', text, flags=re.MULTILINE)
    # Clean up excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # LinkedIn bug: regular parentheses () cause content truncation
    # Replace with fullwidth parentheses （）for LinkedIn
    if platform.lower() == 'linkedin':
        text = text.replace('(', '（').replace(')', '）')
    
    return text


from .twitter_publisher import TwitterPublisher
from .pinterest_publisher import PinterestPublisher
from .linkedin_publisher import LinkedInPublisher
from .instagram_publisher import InstagramPublisher
from .threads_publisher import ThreadsPublisher

__all__ = [
    "TwitterPublisher",
    "PinterestPublisher",
    "LinkedInPublisher",
    "InstagramPublisher",
    "ThreadsPublisher",
    "clean_metadata"
]
