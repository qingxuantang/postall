"""
Product Reference System for PostAll Image Generation

Provides product information and asset references for more accurate
AI-generated images that match actual product designs.

Features:
- Load product descriptions and specifications from YAML config
- Locate product reference images
- Inject product context into image generation prompts
- Support multiple product variants

Configuration:
- PRODUCT_ASSETS_DIR: Path to product assets directory
- PRODUCT_REFERENCE_ENABLED: Enable/disable product referencing
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

# Import dynamic brand configuration
from postall.config import get_brand_name, get_brand_colors, get_brand_style


class ProductReference:
    """
    Manages product asset references for image generation.

    Loads product information from a YAML configuration and provides
    context-rich descriptions for AI image generation.
    """

    def __init__(self, assets_dir: Optional[str] = None, config_file: Optional[str] = None):
        """
        Initialize the product reference system.

        Args:
            assets_dir: Path to product assets directory (overrides env var)
            config_file: Path to product config YAML (default: config/product_assets.yaml)
        """
        self.enabled = os.getenv('PRODUCT_REFERENCE_ENABLED', 'true').lower() == 'true'

        # Determine assets directory
        if assets_dir:
            self.assets_dir = Path(assets_dir)
        else:
            env_dir = os.getenv('PRODUCT_ASSETS_DIR', '')
            if env_dir:
                self.assets_dir = Path(env_dir)
            else:
                # Default to products/ in PostAll root
                postall_root = Path(__file__).parent.parent.parent
                self.assets_dir = postall_root / 'products'

        # Determine config file location
        if config_file:
            self.config_path = Path(config_file)
        else:
            postall_root = Path(__file__).parent.parent.parent
            self.config_path = postall_root / 'config' / 'product_assets.yaml'

        # Load configuration
        self.config = self._load_config()
        self.products = self.config.get('products', {})
        self.brand = self.config.get('brand', {})
        self.image_guidelines = self.config.get('image_guidelines', {})

    def _load_config(self) -> Dict[str, Any]:
        """Load product configuration from YAML file."""
        if not self.config_path.exists():
            print(f"[ProductReference] Config not found: {self.config_path}")
            return self._get_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            print(f"[ProductReference] Loaded config from {self.config_path}")
            return config
        except Exception as e:
            print(f"[ProductReference] Error loading config: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if no config file exists."""
        # Use dynamic brand configuration
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        brand_style = get_brand_style()
        return {
            'brand': {
                'name': brand_name,
                'tagline': '',  # Should be set in project config
                'colors': {
                    'primary': brand_colors.get('primary', '#007BFF'),
                    'secondary': brand_colors.get('secondary', '#6C757D'),
                    'accent': brand_colors.get('accent', '#28A745'),
                    'background': brand_colors.get('background', '#FFFFFF'),
                    'text': brand_colors.get('text', '#212529')
                },
                'style': brand_style
            },
            'products': {},
            'image_guidelines': {
                'style': 'Clean, professional, modern aesthetic',
                'avoid': ['placeholder text', 'lorem ipsum', 'human faces', 'identifiable persons'],
                'prefer': ['natural lighting', 'minimal backgrounds', 'lifestyle contexts']
            }
        }

    def is_enabled(self) -> bool:
        """Check if product reference system is enabled."""
        return self.enabled and bool(self.products)

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product information by ID.

        Args:
            product_id: Product identifier (e.g., 'planner_main', 'planner_digital')

        Returns:
            Product configuration dict or None if not found
        """
        return self.products.get(product_id)

    def get_default_product(self) -> Optional[Dict[str, Any]]:
        """Get the default/primary product."""
        # Look for product marked as default
        for product_id, product in self.products.items():
            if product.get('is_default', False):
                return product

        # Return first product if no default specified
        if self.products:
            return next(iter(self.products.values()))

        return None

    def get_product_description(self, product_id: Optional[str] = None) -> str:
        """
        Get a detailed product description for image generation prompts.

        Args:
            product_id: Specific product ID, or None for default product

        Returns:
            Detailed description string for AI image generation
        """
        if product_id:
            product = self.get_product(product_id)
        else:
            product = self.get_default_product()

        if not product:
            return self._get_generic_description()

        # Build detailed description
        parts = []

        # Product name and type
        name = product.get('name', get_brand_name())
        product_type = product.get('type', 'product')
        parts.append(f"Product: {name} ({product_type})")

        # Physical attributes
        if 'physical' in product:
            phys = product['physical']
            if 'size' in phys:
                parts.append(f"Size: {phys['size']}")
            if 'cover_material' in phys:
                parts.append(f"Cover: {phys['cover_material']}")
            if 'binding' in phys:
                parts.append(f"Binding: {phys['binding']}")
            if 'pages' in phys:
                parts.append(f"Pages: {phys['pages']}")
            if 'paper' in phys:
                parts.append(f"Paper: {phys['paper']}")

        # Visual design
        if 'design' in product:
            design = product['design']
            if 'cover_color' in design:
                parts.append(f"Cover color: {design['cover_color']}")
            if 'cover_design' in design:
                parts.append(f"Cover design: {design['cover_design']}")
            if 'interior_style' in design:
                parts.append(f"Interior: {design['interior_style']}")
            if 'special_features' in design:
                features = ', '.join(design['special_features'])
                parts.append(f"Features: {features}")

        # Brand context
        if self.brand:
            parts.append(f"Brand: {self.brand.get('name', get_brand_name())}")
            if 'style' in self.brand:
                parts.append(f"Brand style: {self.brand['style']}")

        return '\n'.join(parts)

    def _get_generic_description(self) -> str:
        """Get generic product description when no specific product configured."""
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        brand_style = get_brand_style()
        primary = brand_colors.get('primary', '#007BFF')
        secondary = brand_colors.get('secondary', '#6C757D')
        return f"""Product: {brand_name}
Type: Product
Style: {brand_style}
Brand colors: {primary} (primary) and {secondary} (secondary)
Design: Clean, professional, minimalist design"""

    def get_product_images(self, product_id: Optional[str] = None) -> List[Path]:
        """
        Get list of reference image paths for a product.

        Args:
            product_id: Specific product ID, or None for default product

        Returns:
            List of Path objects to reference images
        """
        if product_id:
            product = self.get_product(product_id)
        else:
            product = self.get_default_product()

        if not product:
            return []

        images = []
        image_refs = product.get('reference_images', [])

        for img_ref in image_refs:
            if isinstance(img_ref, str):
                img_path = self.assets_dir / img_ref
            elif isinstance(img_ref, dict):
                img_path = self.assets_dir / img_ref.get('path', '')
            else:
                continue

            if img_path.exists():
                images.append(img_path)

        return images

    def get_image_context_for_prompt(
        self,
        prompt_type: str = 'general',
        product_id: Optional[str] = None,
        platform: Optional[str] = None
    ) -> str:
        """
        Get product context to inject into image generation prompts.

        Args:
            prompt_type: Type of image ('product_shot', 'lifestyle', 'detail', 'general')
            product_id: Specific product ID
            platform: Target platform for dimension/style hints

        Returns:
            Context string to prepend/append to image prompts
        """
        if not self.is_enabled():
            return ""

        context_parts = []

        # Product description
        product_desc = self.get_product_description(product_id)
        if product_desc:
            context_parts.append("=== PRODUCT REFERENCE ===")
            context_parts.append(product_desc)

        # Prompt type specific guidance
        type_guidance = self._get_prompt_type_guidance(prompt_type)
        if type_guidance:
            context_parts.append("")
            context_parts.append("=== IMAGE TYPE GUIDANCE ===")
            context_parts.append(type_guidance)

        # Brand guidelines
        if self.brand:
            context_parts.append("")
            context_parts.append("=== BRAND GUIDELINES ===")
            colors = self.brand.get('colors', {})
            if colors:
                color_str = ', '.join([f"{k}: {v}" for k, v in colors.items()])
                context_parts.append(f"Brand colors: {color_str}")
            if 'style' in self.brand:
                context_parts.append(f"Brand style: {self.brand['style']}")

        # Image guidelines
        if self.image_guidelines:
            context_parts.append("")
            context_parts.append("=== IMAGE REQUIREMENTS ===")
            if 'style' in self.image_guidelines:
                context_parts.append(f"Style: {self.image_guidelines['style']}")
            if 'avoid' in self.image_guidelines:
                avoid_str = ', '.join(self.image_guidelines['avoid'])
                context_parts.append(f"AVOID: {avoid_str}")
            if 'prefer' in self.image_guidelines:
                prefer_str = ', '.join(self.image_guidelines['prefer'])
                context_parts.append(f"PREFER: {prefer_str}")

        return '\n'.join(context_parts)

    def _get_prompt_type_guidance(self, prompt_type: str) -> str:
        """Get guidance specific to the type of image being generated."""
        guidance = {
            'product_shot': """
Focus on the product itself prominently displayed.
Clean background (white, light gray, or subtle gradient).
Professional product photography style.
Show the product at a slight angle to add dimension.
Ensure the product looks premium and high-quality.""",

            'lifestyle': """
Show the product in a realistic usage context.
Include complementary items (desk, coffee cup, pen, etc.).
Natural, warm lighting.
Suggest productivity and planning lifestyle.
Make viewer imagine themselves using the product.""",

            'detail': """
Close-up shot focusing on specific product features.
High detail and sharp focus.
Highlight texture, quality, and craftsmanship.
Show specific spreads, binding, or unique features.""",

            'flat_lay': """
Top-down view of product with complementary items.
Carefully arranged aesthetic composition.
Include lifestyle items that match the brand aesthetic.
Clean, organized arrangement with intentional spacing.""",

            'carousel': """
Part of a series - maintain visual consistency.
Educational or informational focus.
Clear visual hierarchy.
Support the accompanying text content.""",

            'general': """
Versatile product representation.
Balance between product focus and context.
Professional and polished appearance.
Suitable for multiple use cases."""
        }

        return guidance.get(prompt_type, guidance['general']).strip()

    def enhance_prompt(
        self,
        original_prompt: str,
        prompt_type: str = 'general',
        product_id: Optional[str] = None,
        platform: Optional[str] = None
    ) -> str:
        """
        Enhance an image generation prompt with product context.

        Args:
            original_prompt: The original image prompt
            prompt_type: Type of image being generated
            product_id: Specific product to reference
            platform: Target platform

        Returns:
            Enhanced prompt with product context
        """
        if not self.is_enabled():
            return original_prompt

        # Get product context
        context = self.get_image_context_for_prompt(prompt_type, product_id, platform)

        if not context:
            return original_prompt

        # Combine context with original prompt
        enhanced = f"""{context}

=== IMAGE PROMPT ===
{original_prompt}

=== CRITICAL REQUIREMENTS ===
- Ensure the product shown matches the reference description above
- Use the specified brand colors where appropriate
- Maintain consistency with the brand style guidelines
- Do not add any text overlays to the image"""

        return enhanced

    def get_brand_colors(self) -> Dict[str, str]:
        """Get brand color palette."""
        return self.brand.get('colors', {
            'primary': '#FF6B6B',
            'secondary': '#9B59B6'
        })

    def get_status(self) -> Dict[str, Any]:
        """Get status of the product reference system."""
        return {
            'enabled': self.enabled,
            'config_loaded': self.config_path.exists(),
            'config_path': str(self.config_path),
            'assets_dir': str(self.assets_dir),
            'assets_dir_exists': self.assets_dir.exists(),
            'products_count': len(self.products),
            'products': list(self.products.keys()),
            'brand_name': self.brand.get('name', 'Not configured')
        }


# Singleton instance for easy access
_product_reference: Optional[ProductReference] = None


def get_product_reference() -> ProductReference:
    """Get or create the singleton ProductReference instance."""
    global _product_reference
    if _product_reference is None:
        _product_reference = ProductReference()
    return _product_reference


def enhance_image_prompt(
    prompt: str,
    prompt_type: str = 'general',
    product_id: Optional[str] = None,
    platform: Optional[str] = None
) -> str:
    """
    Convenience function to enhance an image prompt with product context.

    Args:
        prompt: Original image generation prompt
        prompt_type: Type of image ('product_shot', 'lifestyle', 'detail', 'general')
        product_id: Specific product ID to reference
        platform: Target platform

    Returns:
        Enhanced prompt string
    """
    ref = get_product_reference()
    return ref.enhance_prompt(prompt, prompt_type, product_id, platform)


def get_product_description(product_id: Optional[str] = None) -> str:
    """
    Convenience function to get product description.

    Args:
        product_id: Specific product ID, or None for default

    Returns:
        Product description string
    """
    ref = get_product_reference()
    return ref.get_product_description(product_id)
