"""
PostAll: Automated Social Operation Protocol - Weekly Content Creation

A brand-agnostic, project-based content generation and publishing system
for social media marketing automation.

Features:
- Multi-platform content generation (Instagram, Twitter, LinkedIn, Pinterest, Threads)
- AI-powered content creation (Claude, Gemini)
- AI image generation with brand consistency
- Content Director for quality review
- 24/7 cloud daemon for automated publishing
- Telegram bot for monitoring and control

Usage:
    from postall import init_project, generate_content

    # Initialize with your project config
    project = init_project("path/to/your/project.yaml")

    # Generate content
    generate_content(platforms=["instagram", "twitter"])

For CLI usage:
    postall --project /path/to/project.yaml generate --platforms instagram twitter
"""

__version__ = "3.0.0"
__author__ = "PostAll Contributors"
__license__ = "MIT"

from postall.project_config import (
    ProjectConfig,
    BrandConfig,
    ProductConfig,
    ContentStrategy,
    load_project,
    init_project,
    get_current_project,
    set_current_project,
    create_example_config
)

from postall.config import (
    get_brand_name,
    get_brand_colors,
    get_brand_website,
    get_brand_style,
    get_brand_tagline,
    get_copyright_text,
    get_platforms,
    get_content_pillars,
    get_enabled_platforms,
    is_platform_enabled,
    get_project_info,
    get_output_dir,
    get_prompts_dir
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",

    # Project configuration
    "ProjectConfig",
    "BrandConfig",
    "ProductConfig",
    "ContentStrategy",
    "load_project",
    "init_project",
    "get_current_project",
    "set_current_project",
    "create_example_config",

    # Dynamic configuration
    "get_brand_name",
    "get_brand_colors",
    "get_brand_website",
    "get_brand_style",
    "get_brand_tagline",
    "get_copyright_text",
    "get_platforms",
    "get_content_pillars",
    "get_enabled_platforms",
    "is_platform_enabled",
    "get_project_info",
    "get_output_dir",
    "get_prompts_dir"
]
