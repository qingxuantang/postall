"""
Image processing utilities for PostAll

Provides brand-agnostic image processing with dynamic configuration.
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Optional

# Import dynamic configuration
from postall.config import get_brand_name, get_brand_website, get_copyright_text

# Suffix added to images after footer is applied
FOOTER_SUFFIX = "_branded"


def has_footer_suffix(file_path: Path) -> bool:
    """
    Check if a file already has the footer suffix in its name.

    Args:
        file_path: Path to the image file

    Returns:
        True if the file has the footer suffix, False otherwise
    """
    return file_path.stem.endswith(FOOTER_SUFFIX)


def get_branded_path(file_path: Path) -> Path:
    """
    Get the new file path with footer suffix.

    Args:
        file_path: Original file path

    Returns:
        New path with _branded suffix before extension
    """
    return file_path.parent / f"{file_path.stem}{FOOTER_SUFFIX}{file_path.suffix}"


def add_brand_footer(
    input_path: Path,
    output_path: Optional[Path] = None,
    text: Optional[str] = None,
    brand_text: Optional[str] = None,
    url_text: Optional[str] = None,
    rename_after: bool = True
) -> bool:
    """
    Add a brand footer to an image.

    Uses dynamic brand configuration when parameters are not provided.

    Args:
        input_path: Path to input image
        output_path: Path to output image (if None, saves with _branded suffix)
        text: Copyright text (defaults to project config)
        brand_text: Brand name (defaults to project config)
        url_text: Brand URL (defaults to project config)
        rename_after: If True, rename file with _branded suffix after processing

    Returns:
        True if successful, False otherwise
    """
    input_path = Path(input_path)

    # Skip if already has footer suffix
    if has_footer_suffix(input_path):
        return True  # Already processed, consider it a success

    # Use dynamic configuration if not provided
    if text is None:
        text = get_copyright_text()
    if brand_text is None:
        brand_text = get_brand_name()
    if url_text is None:
        url_text = get_brand_website()

    # Determine output path
    if output_path is None:
        if rename_after:
            output_path = get_branded_path(input_path)
        else:
            output_path = input_path
    else:
        output_path = Path(output_path)

    try:
        with Image.open(input_path) as img:
            # Convert to RGB to ensure compatibility
            if img.mode != 'RGB':
                img = img.convert('RGB')

            width, height = img.size

            # Create a new image with extra height for the footer (approx 5% or min 40px)
            footer_height = max(int(height * 0.05), 40)
            new_height = height + footer_height

            new_img = Image.new('RGB', (width, new_height), (255, 255, 255))
            new_img.paste(img, (0, 0))

            draw = ImageDraw.Draw(new_img)

            # Use default font or try to find a system font
            font = None
            try:
                # Common system font paths
                font_paths = [
                    "C:/Windows/Fonts/arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "/usr/share/fonts/TTF/Arial.ttf"
                ]
                for fp in font_paths:
                    if os.path.exists(fp):
                        font = ImageFont.truetype(fp, size=max(int(footer_height * 0.4), 12))
                        break
            except Exception:
                pass

            if not font:
                font = ImageFont.load_default()

            # Draw footer background (light gray separator)
            draw.line([(0, height), (width, height)], fill=(220, 220, 220), width=1)

            # Calculate positions
            margin = 20

            # Copyright (Left)
            draw.text((margin, height + (footer_height - 12) // 2), text, fill=(102, 102, 102), font=font)

            # Brand & URL (Right) - only if we have values
            if brand_text or url_text:
                if brand_text and url_text:
                    full_brand_text = f"{brand_text} | {url_text}"
                else:
                    full_brand_text = brand_text or url_text

                try:
                    # Text size for right alignment
                    _, _, text_w, text_h = draw.textbbox((0, 0), full_brand_text, font=font)
                    draw.text((width - text_w - margin, height + (footer_height - text_h) // 2),
                              full_brand_text, fill=(102, 102, 102), font=font)
                except Exception:
                    # Minimal alignment fallback
                    draw.text((width - 200, height + (footer_height - 12) // 2),
                              full_brand_text, fill=(102, 102, 102), font=font)

            new_img.save(output_path, quality=95)

            # If we saved to a new file and rename_after is True, delete the original
            if rename_after and output_path != input_path:
                try:
                    input_path.unlink()
                except Exception:
                    pass  # Keep going even if we can't delete original

            return True
    except Exception as e:
        print(f"Error adding footer to {input_path}: {e}")
        return False
