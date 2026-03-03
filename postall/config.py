import re
"""
Configuration management for PostAll (Standalone Version)

This module provides configuration that can work:
1. With a project configuration file (recommended for multi-project use)
2. With environment variables (backwards compatible)
3. With a combination of both

Environment variables override project config values.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
PACKAGE_DIR = Path(__file__).parent
load_dotenv(PACKAGE_DIR.parent / ".env")

# Import project configuration system
from postall.project_config import (
    ProjectConfig,
    get_current_project,
    set_current_project,
    load_project,
    init_project
)


# ================================
# PATH CONFIGURATION
# ================================

def get_postall_root() -> Path:
    """Get the PostAll package root directory."""
    return PACKAGE_DIR.parent


def get_project_root() -> Path:
    """Get the current project root directory."""
    project = get_current_project()
    if project and project.project_root:
        return project.project_root
    return Path(os.getenv("PROJECT_ROOT", str(get_postall_root())))


def get_output_dir() -> Path:
    """Get the output directory for generated content."""
    project = get_current_project()
    if project and project.output_dir:
        return project.output_dir
    return get_postall_root() / os.getenv("OUTPUT_DIR", "output")


def get_prompts_dir() -> Path:
    """Get the prompts directory."""
    project = get_current_project()
    if project and project.prompts_dir:
        return project.prompts_dir
    return get_postall_root() / os.getenv("PROMPTS_DIR", "prompts")


def get_config_dir() -> Path:
    """Get the config directory."""
    return get_postall_root() / "config"


POSTALL_ROOT = get_postall_root()
CONFIG_DIR = get_config_dir()
LOGS_DIR = POSTALL_ROOT / "logs"
OUTPUT_DIR = get_output_dir()
PROJECT_ROOT = get_project_root()


# ================================
# AI CONFIGURATION
# ================================

CLAUDE_CLI_PATH = os.getenv("CLAUDE_CLI_PATH", "claude")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Vertex AI Configuration (for Imagen 3 image generation)
VERTEX_API_KEY = os.getenv("VERTEX_API_KEY", "")
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "true").lower() == "true"

# OpenAI Configuration (for DALL-E 3 fallback)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# ================================
# SOCIAL MEDIA CREDENTIALS
# ================================

# Twitter/X
TWITTER_ENABLED = os.getenv("TWITTER_ENABLED", "false").lower() == "true"
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
AUTO_PUBLISH_TWITTER = os.getenv("AUTO_PUBLISH_TWITTER", "false").lower() == "true"

# Pinterest
PINTEREST_ENABLED = os.getenv("PINTEREST_ENABLED", "false").lower() == "true"
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "")
PINTEREST_REFRESH_TOKEN = os.getenv("PINTEREST_REFRESH_TOKEN", "")
PINTEREST_APP_ID = os.getenv("PINTEREST_APP_ID", "")
PINTEREST_APP_SECRET = os.getenv("PINTEREST_APP_SECRET", "")
PINTEREST_BOARD_ID = os.getenv("PINTEREST_BOARD_ID", "")

# LinkedIn
LINKEDIN_ENABLED = os.getenv("LINKEDIN_ENABLED", "false").lower() == "true"
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_REFRESH_TOKEN = os.getenv("LINKEDIN_REFRESH_TOKEN", "")
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_PERSON_URN = os.getenv("LINKEDIN_PERSON_URN", "")

# Instagram
INSTAGRAM_ENABLED = os.getenv("INSTAGRAM_ENABLED", "false").lower() == "true"
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")

# Threads
THREADS_ENABLED = os.getenv("THREADS_ENABLED", "false").lower() == "true"
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")



# ================================
# EXECUTION SETTINGS
# ================================

EXECUTION_TIMEOUT = int(os.getenv("EXECUTION_TIMEOUT", "1800"))  # 30 minutes
DEFAULT_SCHEDULE = os.getenv("DEFAULT_SCHEDULE", "Saturday 09:00")
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")


# ================================
# PRODUCT REFERENCE CONFIGURATION
# ================================

PRODUCT_ASSETS_DIR = Path(os.getenv("PRODUCT_ASSETS_DIR", str(POSTALL_ROOT / "products")))
PRODUCT_ASSETS_CONFIG = CONFIG_DIR / "product_assets.yaml"
PRODUCT_REFERENCE_ENABLED = os.getenv("PRODUCT_REFERENCE_ENABLED", "true").lower() == "true"


# ================================
# CLOUD DAEMON CONFIGURATION
# ================================

DAEMON_MODE = os.getenv("DAEMON_MODE", "false").lower() == "true"
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))
HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", "8080"))
SCHEDULE_DB_PATH = os.getenv("SCHEDULE_DB_PATH", "data/schedule.db")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")

# Notifications
NOTIFICATIONS_ENABLED = os.getenv("NOTIFICATIONS_ENABLED", "false").lower() == "true"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_ENABLED = os.getenv("TELEGRAM_BOT_ENABLED", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Generation schedule (defaults — overridden by project.yaml via apply_project_config())
GENERATION_ENABLED = os.getenv("GENERATION_ENABLED", "true").lower() == "true"
GENERATION_DAY = os.getenv("GENERATION_DAY", "saturday").lower()
GENERATION_TIME = os.getenv("GENERATION_TIME", "09:00")
REMINDER_1_DAY = os.getenv("REMINDER_1_DAY", "friday").lower()
REMINDER_1_TIME = os.getenv("REMINDER_1_TIME", "17:00")
REMINDER_2_DAY = os.getenv("REMINDER_2_DAY", "friday").lower()
REMINDER_2_TIME = os.getenv("REMINDER_2_TIME", "19:00")


def apply_project_config():
    """
    Apply project.yaml settings to module globals.

    Call this AFTER init_project() to override env var defaults with
    project.yaml values. This ensures timezone, generation day/time,
    reminder settings, and platform enabled flags only need to be
    configured in project.yaml.
    """
    global TIMEZONE, GENERATION_DAY, GENERATION_TIME
    global REMINDER_1_DAY, REMINDER_1_TIME, REMINDER_2_DAY, REMINDER_2_TIME
    global TWITTER_ENABLED, LINKEDIN_ENABLED, INSTAGRAM_ENABLED
    global PLATFORMS

    project = get_current_project()
    if not project:
        return

    # Timezone from project.yaml (scheduling.timezone)
    if project.timezone and project.timezone != "UTC":
        TIMEZONE = project.timezone

    # Generation schedule from project.yaml (scheduling.generation)
    gen_schedule = project.generation_schedule
    if gen_schedule:
        if gen_schedule.get("day"):
            GENERATION_DAY = gen_schedule["day"].lower()
        if gen_schedule.get("time"):
            GENERATION_TIME = gen_schedule["time"]

    # Platform enabled flags from project.yaml — these override env var defaults
    # so publishers that import TWITTER_ENABLED etc. see the project.yaml values
    if project.platforms:
        platform_to_global = {
            "twitter": "TWITTER_ENABLED",
            "linkedin": "LINKEDIN_ENABLED",
            "instagram": "INSTAGRAM_ENABLED",
            "pinterest": "PINTEREST_ENABLED",
            "threads": "THREADS_ENABLED",
        }
        for platform_key, platform_creds in project.platforms.items():
            global_name = platform_to_global.get(platform_key)
            if global_name:
                globals()[global_name] = platform_creds.enabled

    # Rebuild PLATFORMS dict so it reflects the updated enabled flags
    PLATFORMS = get_platforms()


# ================================
# BRAND CONFIGURATION (Dynamic)
# ================================

def get_brand_name() -> str:
    """Get the brand name from project config or environment."""
    project = get_current_project()
    if project and project.brand.name != "Your Brand":
        return project.brand.name
    return os.getenv("BRAND_NAME", "Your Brand")


def get_brand_colors() -> Dict[str, str]:
    """Get brand colors from project config or defaults."""
    project = get_current_project()
    if project and project.brand.colors:
        return project.brand.colors
    return {
        "primary": os.getenv("BRAND_COLOR_PRIMARY", "#007BFF"),
        "secondary": os.getenv("BRAND_COLOR_SECONDARY", "#6C757D"),
    }


def get_brand_website() -> str:
    """Get brand website from project config or environment."""
    project = get_current_project()
    if project and project.brand.website:
        return project.brand.website
    return os.getenv("BRAND_WEBSITE", "")


def get_brand_style() -> str:
    """Get brand style/voice from project config or environment."""
    project = get_current_project()
    if project and project.brand.style:
        return project.brand.style
    return os.getenv("BRAND_STYLE", "professional yet approachable")


def get_brand_tagline() -> str:
    """Get brand tagline from project config or environment."""
    project = get_current_project()
    if project and project.brand.tagline:
        return project.brand.tagline
    return os.getenv("BRAND_TAGLINE", "")


def get_social_links() -> Dict[str, Dict[str, str]]:
    """Get brand social links from project config."""
    project = get_current_project()
    if project and project.brand.social_links:
        return project.brand.social_links
    return {}


def get_social_links_text(target_platform: str = "") -> str:
    """Format social links for inclusion in content generation prompts.
    
    Platform-specific CTA rules:
    - twitter/linkedin: YouTube link only
    - ai_coach: ALL platforms, with platform-specific tracking suffix
    - other/empty: all links
    """
    links = get_social_links()
    if not links:
        return ""
    
    # Map target_platform to tracking source name
    platform_source_map = {
        'x-tweets': 'twitter',
        'twitter': 'twitter',
        'linkedin-posts': 'linkedin',
        'linkedin': 'linkedin',
        'instagram-posts': 'instagram',
        'instagram': 'instagram',
    }
    
    parts = []
    for link_key, info in links.items():
        label = info.get('label', link_key.title())
        url = info.get('url', '')
        if not url:
            continue
        
        # Platform-specific filtering
        # ai_coach and ai_coach_pro links go on ALL platforms (MANDATORY)
        if link_key in ('ai_coach', 'ai_coach_pro', 'ai_coach_landing'):
            # Add platform-specific tracking to Telegram bot links
            if 't.me/' in url:
                source = platform_source_map.get(target_platform, target_platform or 'unknown')
                # Replace or add ?start= parameter
                if '?start=' in url:
                    url = re.sub(r'\?start=[^&]*', f'?start={source}', url)
                else:
                    url = f'{url}?start={source}'
            parts.append(f"  - {label}: {url}")
        elif target_platform in ('x-tweets', 'twitter', 'linkedin-posts', 'linkedin'):
            # YouTube + AI Coach for Twitter and LinkedIn
            if link_key not in ('youtube',):
                continue
            parts.append(f"  - {label}: {url}")
        else:
            parts.append(f"  - {label}: {url}")
    return "\n".join(parts)


def get_copyright_text() -> str:
    """Get copyright text for branding."""
    project = get_current_project()
    if project:
        return project.get_copyright_text()
    brand = get_brand_name()
    year = os.getenv("COPYRIGHT_YEAR", "2026")
    return f"© {year} {brand}. All Rights Reserved."


# ================================
# PLATFORM CONFIGURATION
# ================================

def get_platforms() -> Dict[str, Dict[str, Any]]:
    """
    Get platform configurations.

    Returns dynamically from project config or defaults.
    """
    project = get_current_project()

    # Default platform configurations
    platforms = {
        "instagram": {
            "name": "Instagram",
            "output_folder": "instagram-posts",
            "max_caption_length": 2200,
            "max_hashtags": 30,
            "image_aspect_ratio": "1:1",
            "posting_times": ["08:00", "12:00", "17:00"],
            "enabled": INSTAGRAM_ENABLED
        },
        "twitter": {
            "name": "Twitter/X",
            "output_folder": "x-tweets",
            "max_length": 280,
            "max_images": 4,
            "posting_times": ["08:00", "12:00", "15:00", "18:00"],
            "enabled": TWITTER_ENABLED
        },
        "linkedin": {
            "name": "LinkedIn",
            "output_folder": "linkedin-posts",
            "max_length": 3000,
            "posting_times": ["07:30", "12:00"],
            "enabled": LINKEDIN_ENABLED
        },
        "pinterest": {
            "name": "Pinterest",
            "output_folder": "pinterest-pins",
            "max_title_length": 100,
            "max_description_length": 500,
            "image_aspect_ratio": "2:3",
            "posting_times": ["20:00"],
            "enabled": PINTEREST_ENABLED
        },
        "threads": {
            "name": "Threads",
            "output_folder": "threads-posts",
            "max_length": 500,
            "posting_times": ["09:00", "18:00"],
            "enabled": THREADS_ENABLED
        },
        "substack": {
            "name": "Substack",
            "output_folder": "substack-posts",
            "posting_times": ["09:00"],
            "enabled": False
        }
    }

    # Override with project config if available
    if project and project.platforms:
        for platform_key, platform_creds in project.platforms.items():
            if platform_key in platforms:
                platforms[platform_key]["enabled"] = platform_creds.enabled
                if platform_creds.language:
                    platforms[platform_key]["language"] = platform_creds.language
                if platform_creds.post_frequency > 0:
                    platforms[platform_key]["post_frequency"] = platform_creds.post_frequency
                if platform_creds.max_length > 0:
                    platforms[platform_key]["max_length"] = platform_creds.max_length

    return platforms


# Alias for backwards compatibility
PLATFORMS = get_platforms()


# ================================
# CONTENT PILLARS (Dynamic)
# ================================

def get_content_pillars() -> Dict[str, int]:
    """Get content pillar distribution from project config."""
    project = get_current_project()
    if project and project.content_strategy.pillars:
        return project.content_strategy.pillars
    return {
        "product_education": 35,
        "industry_insights": 25,
        "tips_productivity": 20,
        "customer_stories": 10,
        "behind_scenes": 5,
        "lead_magnet": 5
    }


# ================================
# UTILITY FUNCTIONS
# ================================

def get_next_week_folder_name() -> str:
    """Get the folder name for next week's content (e.g., '2026-02-08_week6')."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    # Next Monday
    days_ahead = 7 - now.weekday()  # 0=Monday
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = now + timedelta(days=days_ahead)
    week_num = next_monday.isocalendar()[1]
    return f"{next_monday.strftime('%Y-%m-%d')}_week{week_num}"


def get_enabled_platforms() -> list:
    """Get list of enabled platform keys."""
    platforms = get_platforms()
    return [k for k, v in platforms.items() if v.get("enabled", False)]


def get_platform_language(platform: str) -> str:
    """Get the content language for a specific platform (e.g., 'en', 'zh'). Empty string means default."""
    platforms = get_platforms()
    return platforms.get(platform, {}).get("language", "")


def is_platform_enabled(platform: str) -> bool:
    """Check if a specific platform is enabled."""
    platforms = get_platforms()
    return platforms.get(platform, {}).get("enabled", False)


def get_project_info() -> Dict[str, Any]:
    """Get current project information for display/logging."""
    project = get_current_project()
    return {
        "project_id": project.project_id if project else "default",
        "project_name": project.project_name if project else "No Project",
        "brand_name": get_brand_name(),
        "enabled_platforms": get_enabled_platforms(),
        "output_dir": str(get_output_dir()),
        "timezone": TIMEZONE
    }
