"""
Project Configuration System for PostAll

This module provides a project-based configuration system that allows
PostAll to be used with any brand/product without code changes.

Each project defines:
- Brand information (name, colors, voice)
- Product details (specs, features)
- Platform credentials
- Content strategy
- Output directories

Usage:
    from postall.project_config import ProjectConfig, load_project

    # Load a project configuration
    project = load_project("/path/to/project/config.yaml")

    # Access project settings
    brand_name = project.brand.name
    colors = project.brand.colors
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import yaml


@dataclass
class BrandConfig:
    """Brand-specific configuration."""
    name: str = "Your Brand"
    tagline: str = ""
    website: str = ""
    style: str = "Professional and approachable"

    # Brand colors
    colors: Dict[str, str] = field(default_factory=lambda: {
        "primary": "#007BFF",
        "secondary": "#6C757D",
        "accent": "#28A745",
        "background": "#FFFFFF",
        "text": "#212529"
    })

    # Brand voice characteristics
    voice: Dict[str, Any] = field(default_factory=lambda: {
        "tone": "professional yet friendly",
        "characteristics": ["clear", "helpful", "trustworthy"],
        "avoid": ["aggressive sales", "overpromising", "jargon"]
    })

    # Social links for CTA in posts (e.g., {"youtube": {"url": "...", "label": "..."}, ...})
    social_links: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # Copyright info
    copyright_text: str = ""
    copyright_year: int = 2026


@dataclass
class ProductConfig:
    """Product-specific configuration."""
    name: str = "Your Product"
    type: str = "product"
    description: str = ""

    # Physical attributes (if applicable)
    physical: Dict[str, str] = field(default_factory=dict)

    # Design attributes
    design: Dict[str, Any] = field(default_factory=dict)

    # Keywords for content generation
    keywords: List[str] = field(default_factory=list)

    # Reference images
    reference_images: List[str] = field(default_factory=list)


@dataclass
class PlatformCredentials:
    """Credentials for a social media platform."""
    enabled: bool = False
    language: str = ""  # Platform content language: "en", "zh", or "" for default
    post_frequency: int = 0  # Posts per week (0 = use default 5-7)
    max_length: int = 0  # Max content length in chars (0 = use platform default)
    credentials: Dict[str, str] = field(default_factory=dict)


@dataclass
class ContentStrategy:
    """Content strategy configuration."""
    # Content pillars with percentages
    pillars: Dict[str, int] = field(default_factory=lambda: {
        "product_education": 35,
        "industry_insights": 25,
        "tips_productivity": 20,
        "customer_stories": 10,
        "behind_scenes": 5,
        "lead_magnet": 5
    })

    # Posting schedule preferences
    posting_times: Dict[str, List[str]] = field(default_factory=dict)

    # Content themes
    themes: List[str] = field(default_factory=list)

    # Hashtag strategy
    hashtags: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ProjectConfig:
    """
    Complete project configuration for PostAll.

    A project represents a single brand/product that uses PostAll
    for content generation and publishing.
    """
    # Project metadata
    project_id: str = "default"
    project_name: str = "My Project"
    version: str = "1.0.0"

    # Core configurations
    brand: BrandConfig = field(default_factory=BrandConfig)
    products: Dict[str, ProductConfig] = field(default_factory=dict)
    default_product: str = ""

    # Platform configurations
    platforms: Dict[str, PlatformCredentials] = field(default_factory=dict)

    # Content strategy
    content_strategy: ContentStrategy = field(default_factory=ContentStrategy)

    # Paths
    project_root: Path = field(default_factory=lambda: Path.cwd())
    output_dir: Path = field(default_factory=lambda: Path("output"))
    prompts_dir: Path = field(default_factory=lambda: Path("prompts"))
    assets_dir: Path = field(default_factory=lambda: Path("assets"))

    # Generation settings
    timezone: str = "UTC"
    generation_schedule: Dict[str, str] = field(default_factory=lambda: {
        "day": "saturday",
        "time": "09:00"
    })

    # AI provider preferences
    prefer_gemini: bool = False
    max_daily_api_calls: int = 100

    def get_product(self, product_id: Optional[str] = None) -> Optional[ProductConfig]:
        """Get a product configuration by ID or return default."""
        if product_id and product_id in self.products:
            return self.products[product_id]
        if self.default_product and self.default_product in self.products:
            return self.products[self.default_product]
        if self.products:
            return next(iter(self.products.values()))
        return None

    def get_brand_description(self) -> str:
        """Get a formatted brand description for AI prompts."""
        lines = [
            f"Brand: {self.brand.name}",
            f"Tagline: {self.brand.tagline}" if self.brand.tagline else "",
            f"Website: {self.brand.website}" if self.brand.website else "",
            f"Style: {self.brand.style}",
            f"Voice: {self.brand.voice.get('tone', 'professional')}",
        ]

        colors = self.brand.colors
        if colors:
            color_str = ", ".join([f"{k}: {v}" for k, v in colors.items()])
            lines.append(f"Brand Colors: {color_str}")

        return "\n".join(line for line in lines if line)

    def get_copyright_text(self) -> str:
        """Get formatted copyright text."""
        if self.brand.copyright_text:
            return self.brand.copyright_text
        return f"© {self.brand.copyright_year} {self.brand.name}. All Rights Reserved."

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "version": self.version,
            "brand": {
                "name": self.brand.name,
                "tagline": self.brand.tagline,
                "website": self.brand.website,
                "style": self.brand.style,
                "colors": self.brand.colors,
                "voice": self.brand.voice,
                "copyright_text": self.brand.copyright_text,
                "copyright_year": self.brand.copyright_year
            },
            "products": {
                pid: {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "physical": p.physical,
                    "design": p.design,
                    "keywords": p.keywords
                }
                for pid, p in self.products.items()
            },
            "default_product": self.default_product,
            "content_strategy": {
                "pillars": self.content_strategy.pillars,
                "posting_times": self.content_strategy.posting_times,
                "themes": self.content_strategy.themes,
                "hashtags": self.content_strategy.hashtags
            },
            "timezone": self.timezone,
            "generation_schedule": self.generation_schedule,
            "prefer_gemini": self.prefer_gemini,
            "max_daily_api_calls": self.max_daily_api_calls
        }


def load_project(config_path: str) -> ProjectConfig:
    """
    Load a project configuration from a YAML file.

    Args:
        config_path: Path to the project configuration YAML file

    Returns:
        ProjectConfig instance
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Project config not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    # Create brand config
    brand_data = data.get('brand', {})
    brand = BrandConfig(
        name=brand_data.get('name', 'Your Brand'),
        tagline=brand_data.get('tagline', ''),
        website=brand_data.get('website', ''),
        style=brand_data.get('style', 'Professional and approachable'),
        colors=brand_data.get('colors', {}),
        voice=brand_data.get('voice', {}),
        copyright_text=brand_data.get('copyright_text', ''),
        copyright_year=brand_data.get('copyright_year', 2026),
        social_links=brand_data.get('social_links', {})
    )

    # Create product configs
    products = {}
    for pid, pdata in data.get('products', {}).items():
        products[pid] = ProductConfig(
            name=pdata.get('name', pid),
            type=pdata.get('type', 'product'),
            description=pdata.get('description', ''),
            physical=pdata.get('physical', {}),
            design=pdata.get('design', {}),
            keywords=pdata.get('keywords', []),
            reference_images=pdata.get('reference_images', [])
        )

    # Create content strategy
    strategy_data = data.get('content_strategy', {})
    content_strategy = ContentStrategy(
        pillars=strategy_data.get('pillars', {}),
        posting_times=strategy_data.get('posting_times', {}),
        themes=strategy_data.get('themes', []),
        hashtags=strategy_data.get('hashtags', {})
    )

    # Create platform credentials
    platforms = {}
    for platform, pdata in data.get('platforms', {}).items():
        platforms[platform] = PlatformCredentials(
            enabled=pdata.get('enabled', False),
            language=pdata.get('language', ''),
            post_frequency=pdata.get('post_frequency', 0),
            max_length=pdata.get('max_length', 0),
            credentials=pdata.get('credentials', {})
        )

    # Resolve paths relative to config file
    project_root = config_path.parent

    return ProjectConfig(
        project_id=data.get('project_id', 'default'),
        project_name=data.get('project_name', 'My Project'),
        version=data.get('version', '1.0.0'),
        brand=brand,
        products=products,
        default_product=data.get('default_product', ''),
        platforms=platforms,
        content_strategy=content_strategy,
        project_root=project_root,
        output_dir=project_root / data.get('output_dir', 'output'),
        prompts_dir=project_root / data.get('prompts_dir', 'prompts'),
        assets_dir=project_root / data.get('assets_dir', 'assets'),
        timezone=data.get('scheduling', {}).get('timezone', data.get('timezone', 'UTC')),
        generation_schedule=data.get('scheduling', {}).get('generation', data.get('generation_schedule', {})),
        prefer_gemini=data.get('prefer_gemini', False),
        max_daily_api_calls=data.get('max_daily_api_calls', 100)
    )


def create_example_config() -> str:
    """
    Create an example project configuration YAML.

    Returns:
        YAML string with example configuration
    """
    return '''# PostAll Project Configuration
# This file defines all project-specific settings for content generation

# Project metadata
project_id: my_brand
project_name: "My Brand Content Project"
version: "1.0.0"

# Brand Configuration
brand:
  name: "Your Brand Name"
  tagline: "Your compelling tagline"
  website: "yourbrand.com"
  style: "Professional yet approachable, helpful and trustworthy"

  colors:
    primary: "#007BFF"      # Main brand color
    secondary: "#6C757D"    # Secondary color
    accent: "#28A745"       # Accent/CTA color
    background: "#FFFFFF"   # Background color
    text: "#212529"         # Text color

  voice:
    tone: "professional yet friendly"
    characteristics:
      - "clear"
      - "helpful"
      - "trustworthy"
      - "expert"
    avoid:
      - "aggressive sales language"
      - "overpromising"
      - "technical jargon"
      - "competitor bashing"

  copyright_year: 2026

# Product Definitions
products:
  main_product:
    name: "Your Main Product"
    type: "SaaS/Physical/Digital"
    description: "Brief description of your product and its value proposition"

    physical:  # For physical products
      size: "Standard"
      materials: "Premium quality"

    design:
      style: "Modern, clean"
      special_features:
        - "Feature 1"
        - "Feature 2"
        - "Feature 3"

    keywords:
      - "keyword1"
      - "keyword2"
      - "keyword3"

default_product: main_product

# Content Strategy
content_strategy:
  pillars:
    product_education: 35
    industry_insights: 25
    tips_productivity: 20
    customer_stories: 10
    behind_scenes: 5
    lead_magnet: 5

  themes:
    - "Theme 1"
    - "Theme 2"
    - "Theme 3"

  hashtags:
    instagram:
      - "#YourBrand"
      - "#Industry"
    twitter:
      - "#YourBrand"
    linkedin:
      - "#YourBrand"
      - "#Professional"

# Platform Credentials (loaded from environment variables)
# These are placeholders - actual credentials should be in .env file
platforms:
  twitter:
    enabled: true
  instagram:
    enabled: false
  linkedin:
    enabled: true
  pinterest:
    enabled: false
  threads:
    enabled: false

# Paths (relative to this config file)
output_dir: output
prompts_dir: prompts
assets_dir: assets

# Schedule Settings (single source of truth for timezone and generation schedule)
scheduling:
  timezone: "America/Los_Angeles"
  generation:
    day: "saturday"
    time: "09:00"

# AI Settings
prefer_gemini: false
max_daily_api_calls: 100
'''


# Global project instance (singleton pattern)
_current_project: Optional[ProjectConfig] = None


def get_current_project() -> ProjectConfig:
    """
    Get the current project configuration.

    Returns:
        Current ProjectConfig instance or default config
    """
    global _current_project
    if _current_project is None:
        _current_project = ProjectConfig()
    return _current_project


def set_current_project(project: ProjectConfig):
    """
    Set the current project configuration.

    Args:
        project: ProjectConfig instance to use
    """
    global _current_project
    _current_project = project


def init_project(config_path: str) -> ProjectConfig:
    """
    Initialize and set the current project from a config file.

    Args:
        config_path: Path to project configuration YAML

    Returns:
        Loaded ProjectConfig instance
    """
    project = load_project(config_path)
    set_current_project(project)
    return project
