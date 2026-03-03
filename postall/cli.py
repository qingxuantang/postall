#!/usr/bin/env python3
"""
PostAll Command Line Interface

A brand-agnostic content generation and publishing system.

Usage:
    postall --project /path/to/project.yaml generate
    postall --project /path/to/project.yaml publish
    postall --project /path/to/project.yaml daemon
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from postall import (
    __version__,
    init_project,
    get_current_project,
    get_project_info,
    create_example_config
)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="postall",
        description="PostAll: Automated Social Operation Protocol - Weekly Content Creation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate content for a project
  postall --project ./my-project/project.yaml generate

  # Start the daemon for automated publishing
  postall --project ./my-project/project.yaml daemon

  # Create a new project from template
  postall init ./new-project

  # Show project information
  postall --project ./my-project/project.yaml info
        """
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"postall {__version__}"
    )

    parser.add_argument(
        "--project", "-p",
        type=str,
        help="Path to project configuration YAML file"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new project")
    init_parser.add_argument("path", type=str, help="Path for new project")

    # info command
    info_parser = subparsers.add_parser("info", help="Show project information")

    # generate command
    gen_parser = subparsers.add_parser("generate", help="Generate content")
    gen_parser.add_argument(
        "--platforms", "-P",
        nargs="+",
        help="Platforms to generate content for"
    )
    gen_parser.add_argument(
        "--week", "-w",
        type=int,
        help="Week number (defaults to next week)"
    )
    gen_parser.add_argument(
        "--with-images",
        action="store_true",
        help="Also generate images"
    )
    gen_parser.add_argument(
        "--with-review",
        action="store_true",
        help="Run content director review after generation"
    )

    # generate-images command
    img_parser = subparsers.add_parser("generate-images", help="Generate images for existing content")
    img_parser.add_argument(
        "--week", "-w",
        type=str,
        help="Week folder name or path"
    )
    img_parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip images that already exist"
    )

    # publish command
    pub_parser = subparsers.add_parser("publish", help="Publish scheduled content")
    pub_parser.add_argument(
        "--platform", "-P",
        type=str,
        help="Specific platform to publish"
    )
    pub_parser.add_argument(
        "--force",
        action="store_true",
        help="Force publish even if not scheduled"
    )

    # daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Start the cloud daemon")
    daemon_parser.add_argument(
        "--check-interval", "-i",
        type=int,
        default=15,
        help="Check interval in minutes (default: 15)"
    )

    # director command
    dir_parser = subparsers.add_parser("director-review", help="Run content director review")
    dir_parser.add_argument(
        "--week", "-w",
        type=str,
        help="Week folder to review"
    )
    dir_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    # status commands
    subparsers.add_parser("status", help="Show system status")
    subparsers.add_parser("schedule", help="Show publishing schedule")

    args = parser.parse_args()

    # Handle commands that don't need a project
    if args.command == "init":
        return cmd_init(args.path)

    if not args.command:
        parser.print_help()
        return 0

    # Load project if specified
    if args.project:
        try:
            project = init_project(args.project)
            print(f"✓ Loaded project: {project.project_name}")
        except FileNotFoundError:
            print(f"✗ Project config not found: {args.project}")
            return 1
        except Exception as e:
            print(f"✗ Error loading project: {e}")
            return 1
    else:
        # Check for project.yaml in current directory
        local_config = Path("project.yaml")
        if local_config.exists():
            try:
                project = init_project(str(local_config))
                print(f"✓ Loaded project: {project.project_name}")
            except Exception as e:
                print(f"✗ Error loading project: {e}")
                return 1
        else:
            print("⚠ No project specified. Use --project or create project.yaml in current directory.")
            print("  Run 'postall init ./my-project' to create a new project.")
            return 1

    # Apply project.yaml scheduling settings (timezone, generation day/time)
    # to module globals — ensures single source of truth in project.yaml
    from postall.config import apply_project_config
    apply_project_config()

    # Execute command
    if args.command == "info":
        return cmd_info()
    elif args.command == "generate":
        return cmd_generate(args)
    elif args.command == "generate-images":
        return cmd_generate_images(args)
    elif args.command == "publish":
        return cmd_publish(args)
    elif args.command == "daemon":
        return cmd_daemon(args)
    elif args.command == "director-review":
        return cmd_director_review(args)
    elif args.command == "status":
        return cmd_status()
    elif args.command == "schedule":
        return cmd_schedule()
    else:
        parser.print_help()
        return 0


def cmd_init(path: str) -> int:
    """Initialize a new project."""
    project_path = Path(path)

    if project_path.exists() and any(project_path.iterdir()):
        print(f"✗ Directory {path} already exists and is not empty")
        return 1

    # Create directory structure
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "output").mkdir(exist_ok=True)
    (project_path / "prompts").mkdir(exist_ok=True)
    (project_path / "assets").mkdir(exist_ok=True)
    (project_path / "assets" / "product_images").mkdir(exist_ok=True)
    (project_path / "assets" / "brand").mkdir(exist_ok=True)

    # Create project.yaml from template
    config_content = create_example_config()
    (project_path / "project.yaml").write_text(config_content)

    # Create .env template
    env_template = """# PostAll Environment Variables
# Copy this file to .env and fill in your values

# AI Providers (at least one required)
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Twitter/X
TWITTER_ENABLED=false
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=

# LinkedIn
LINKEDIN_ENABLED=false
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_PERSON_URN=

# Instagram (requires Meta Business setup)
INSTAGRAM_ENABLED=false
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_ACCOUNT_ID=

# Pinterest
PINTEREST_ENABLED=false
PINTEREST_ACCESS_TOKEN=
PINTEREST_BOARD_ID=

# Threads
THREADS_ENABLED=false
THREADS_ACCESS_TOKEN=
THREADS_USER_ID=

# Telegram Bot (for notifications)
TELEGRAM_BOT_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Timezone
TIMEZONE=America/Los_Angeles
"""
    (project_path / ".env.template").write_text(env_template)

    # Create .gitignore
    gitignore = """.env
output/
logs/
__pycache__/
*.pyc
.DS_Store
"""
    (project_path / ".gitignore").write_text(gitignore)

    print(f"✓ Created new project at {path}")
    print(f"\nNext steps:")
    print(f"  1. cd {path}")
    print(f"  2. Edit project.yaml with your brand details")
    print(f"  3. Copy .env.template to .env and add your API keys")
    print(f"  4. Run: postall generate")
    return 0


def cmd_info() -> int:
    """Show project information."""
    info = get_project_info()

    print("\n=== Project Information ===")
    print(f"Project ID:    {info['project_id']}")
    print(f"Project Name:  {info['project_name']}")
    print(f"Brand:         {info['brand_name']}")
    print(f"Output Dir:    {info['output_dir']}")
    print(f"Timezone:      {info['timezone']}")
    print(f"\nEnabled Platforms:")
    for platform in info['enabled_platforms']:
        print(f"  • {platform}")

    return 0


def cmd_generate(args) -> int:
    """Generate content."""
    print("\n=== Content Generation ===")

    # Import here to avoid circular imports
    from postall.config import get_output_dir, get_enabled_platforms

    platforms = args.platforms or get_enabled_platforms()
    print(f"Platforms: {', '.join(platforms)}")
    print(f"Output: {get_output_dir()}")

    # TODO: Implement actual generation logic
    print("\n[Generation logic to be implemented]")
    print("This will call the content executors and generators.")

    return 0


def cmd_generate_images(args) -> int:
    """Generate images for existing content."""
    print("\n=== Image Generation ===")
    print(f"Week: {args.week or 'current'}")
    print(f"Skip existing: {args.skip_existing}")

    # TODO: Implement actual image generation logic
    print("\n[Image generation logic to be implemented]")

    return 0


def cmd_publish(args) -> int:
    """Publish scheduled content."""
    print("\n=== Content Publishing ===")

    # TODO: Implement actual publishing logic
    print("\n[Publishing logic to be implemented]")

    return 0


def cmd_daemon(args) -> int:
    """Start the cloud daemon."""
    import asyncio
    from postall.cloud.daemon import CloudDaemon

    daemon = CloudDaemon(
        check_interval_minutes=args.check_interval,
    )
    asyncio.run(daemon.start())

    return 0


def cmd_director_review(args) -> int:
    """Run content director review."""
    print("\n=== Content Director Review ===")
    print(f"Week: {args.week or 'current'}")
    print(f"Dry run: {args.dry_run}")

    # TODO: Implement actual director review logic
    print("\n[Director review logic to be implemented]")

    return 0


def cmd_status() -> int:
    """Show system status."""
    print("\n=== System Status ===")

    from postall.config import (
        ANTHROPIC_API_KEY, GEMINI_API_KEY,
        TWITTER_ENABLED, LINKEDIN_ENABLED,
        INSTAGRAM_ENABLED, PINTEREST_ENABLED,
        TELEGRAM_BOT_ENABLED
    )

    print("\nAI Providers:")
    print(f"  Claude:  {'✓ Configured' if ANTHROPIC_API_KEY else '✗ Not configured'}")
    print(f"  Gemini:  {'✓ Configured' if GEMINI_API_KEY else '✗ Not configured'}")

    print("\nPlatforms:")
    print(f"  Twitter:   {'✓ Enabled' if TWITTER_ENABLED else '○ Disabled'}")
    print(f"  LinkedIn:  {'✓ Enabled' if LINKEDIN_ENABLED else '○ Disabled'}")
    print(f"  Instagram: {'✓ Enabled' if INSTAGRAM_ENABLED else '○ Disabled'}")
    print(f"  Pinterest: {'✓ Enabled' if PINTEREST_ENABLED else '○ Disabled'}")

    print("\nNotifications:")
    print(f"  Telegram:  {'✓ Enabled' if TELEGRAM_BOT_ENABLED else '○ Disabled'}")

    return 0


def cmd_schedule() -> int:
    """Show publishing schedule."""
    print("\n=== Publishing Schedule ===")

    # TODO: Implement schedule display
    print("\n[Schedule display logic to be implemented]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
