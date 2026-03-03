"""
Content Validator - Check if content already exists for next week
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple, List

from postall.config import (
    OUTPUT_DIR, MARKETING_DIR, get_platforms,
    get_next_week_folder_name
)


def check_content_exists() -> bool:
    """
    Check if next week's content already exists.

    Checks both:
    1. Output directory (PostAll-generated content)
    2. Marketing directory (manually created or copied content)

    Returns:
        True if content exists, False otherwise
    """

    next_week = get_next_week_folder_name()

    # Check 1: Output directory
    output_path = OUTPUT_DIR / next_week
    if output_path.exists() and any(output_path.iterdir()):
        return True

    # Check 2: Marketing directory for each platform
    # Look for files matching next week's date pattern
    date_prefix = next_week.split("_")[0]  # YYYY-MM-DD
    week_suffix = next_week.split("_")[1]  # weekN

    platforms_with_content = 0

    for platform_key, platform_info in get_platforms().items():
        folder_name = platform_info["output_folder"]
        platform_path = MARKETING_DIR / folder_name

        if platform_path.exists():
            # Check for files with matching date or week number
            matching_files = (
                list(platform_path.glob(f"*{date_prefix}*")) +
                list(platform_path.glob(f"*{week_suffix}*"))
            )

            # Also check subdirectories (e.g., Dec22_Post1/)
            for subdir in platform_path.iterdir():
                if subdir.is_dir():
                    if date_prefix in subdir.name or week_suffix in subdir.name:
                        matching_files.append(subdir)

            if matching_files:
                platforms_with_content += 1

    # If at least half the platforms have content, consider it "exists"
    return platforms_with_content >= len(get_platforms()) // 2


def get_existing_content_status() -> dict:
    """
    Get detailed status of existing content for next week.

    Returns:
        Dictionary with platform status
    """
    next_week = get_next_week_folder_name()
    date_prefix = next_week.split("_")[0]
    week_suffix = next_week.split("_")[1]

    status = {
        "next_week": next_week,
        "platforms": {}
    }

    for platform_key, platform_info in get_platforms().items():
        folder_name = platform_info["output_folder"]
        platform_path = MARKETING_DIR / folder_name

        platform_status = {
            "exists": False,
            "files": [],
            "path": str(platform_path)
        }

        if platform_path.exists():
            # Find matching files
            for item in platform_path.iterdir():
                if date_prefix in item.name or week_suffix in item.name:
                    platform_status["files"].append(item.name)
                    platform_status["exists"] = True

        status["platforms"][platform_key] = platform_status

    return status


def get_last_generated_week() -> Tuple[str, datetime]:
    """
    Find the most recently generated week.

    Returns:
        Tuple of (folder_name, date) or (None, None) if no content
    """
    if not OUTPUT_DIR.exists():
        return None, None

    # Get all week folders sorted by date
    week_folders = []
    for folder in OUTPUT_DIR.iterdir():
        if folder.is_dir() and "_week" in folder.name:
            try:
                date_str = folder.name.split("_")[0]
                date = datetime.strptime(date_str, "%Y-%m-%d")
                week_folders.append((folder.name, date))
            except ValueError:
                continue

    if not week_folders:
        return None, None

    # Sort by date descending
    week_folders.sort(key=lambda x: x[1], reverse=True)
    return week_folders[0]
