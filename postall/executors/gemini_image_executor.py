"""
Gemini Image Executor
Uses Google Gemini Imagen 3 API to generate images from prompts

Features:
- Multi-provider fallback chain (Gemini 3 Pro → Imagen 3 → Gemini Flash → DALL-E 3)
- Product reference integration for accurate product image generation
- Platform-specific dimensions and styling
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from postall.config import (
    GEMINI_API_KEY,
    get_platforms,
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
    USE_VERTEX_AI,
    OPENAI_API_KEY,
    PRODUCT_REFERENCE_ENABLED,
    get_brand_name,
    get_brand_colors
)

# Import product reference system for accurate product image generation
try:
    from postall.utils.product_reference import (
        get_product_reference,
        enhance_image_prompt
    )
    PRODUCT_REFERENCE_AVAILABLE = True
except ImportError:
    PRODUCT_REFERENCE_AVAILABLE = False
    print("[ImageExecutor] Warning: Product reference module not available")


# Supported image extensions to check for existing images
SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.gif']


def check_image_exists(asset_folder: Path, image_name: str) -> Optional[str]:
    """
    Check if an image with the given name already exists in the asset folder.

    Args:
        asset_folder: Path to the asset folder
        image_name: Base name of the image (without extension)

    Returns:
        Path to existing image if found, None otherwise
    """
    if not asset_folder.exists():
        return None

    for ext in SUPPORTED_IMAGE_EXTENSIONS:
        image_path = asset_folder / f"{image_name}{ext}"
        if image_path.exists():
            return str(image_path)

    # Also check for variations with different naming patterns
    # e.g., "slide_1" might be saved as "slide1" or "Slide_1"
    for file in asset_folder.iterdir():
        if file.is_file() and file.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            # Check if the file name matches (case-insensitive, ignoring underscores/spaces)
            file_base = file.stem.lower().replace("_", "").replace(" ", "").replace("-", "")
            image_base = image_name.lower().replace("_", "").replace(" ", "").replace("-", "")
            if file_base == image_base:
                return str(file)

    return None


def extract_image_prompts_from_content(content_path: Path) -> List[Dict[str, str]]:
    """
    Extract image generation prompts from a content markdown file.

    Looks for sections like:
    ## Image Generation Prompts
    OR
    ## Image Prompts

    Followed by:
    ### Slide 1
    ```
    prompt text here
    ```

    Args:
        content_path: Path to the content markdown file

    Returns:
        List of dictionaries with 'name' and 'prompt' keys
    """
    prompts = []

    if not content_path.exists():
        return prompts

    content = content_path.read_text(encoding="utf-8")

    # Check if file has image generation prompts section (multiple possible headers)
    # Support various naming conventions used across platforms
    image_section_headers = [
        "## Image Generation Prompts",  # Instagram format (plural)
        "## Image Generation Prompt",   # Pinterest format (singular)
        "## Image Prompts",             # Twitter/X format
        "## Image Prompt",              # Singular variant
    ]

    found_header = None
    for header in image_section_headers:
        if header in content:
            found_header = header
            break

    if not found_header:
        return prompts

    # Extract the image prompts section
    parts = content.split(found_header)
    if len(parts) < 2:
        return prompts

    prompts_section = parts[1]

    # Stop at next ## section or --- separator or end
    if "\n## " in prompts_section:
        prompts_section = prompts_section.split("\n## ")[0]
    if "\n---\n" in prompts_section:
        prompts_section = prompts_section.split("\n---\n")[0]

    # Try Format 1: Instagram style with ### Name and code blocks
    # Pattern: ### Name followed by ``` prompt ```
    pattern = r'###\s+(.+?)\n```\n(.+?)\n```'
    matches = re.findall(pattern, prompts_section, re.DOTALL)

    if matches:
        for name, prompt in matches:
            prompts.append({
                "name": name.strip(),
                "prompt": prompt.strip()
            })
        return prompts

    # Try Format 2: Twitter/simple style without code blocks
    # If no ### headers found, treat the entire section as a single prompt
    # Extract prompt name from section header if present (e.g., "## Image Prompts (for starter tweet)")
    clean_section = prompts_section.strip()

    if clean_section:
        # Determine image name from file context
        # Check if there's a parenthetical name in the header (e.g., "(for starter tweet)")
        header_match = re.search(r'\(([^)]+)\)', found_header) if found_header else None
        if header_match:
            image_name = header_match.group(1).strip()
        else:
            # Use content file name (without extension) as the image name
            # This ensures unique naming per source file
            image_name = content_path.stem

        # Combine all the descriptive lines into a single prompt
        # This handles **Style:**, **Content:**, etc. format
        prompts.append({
            "name": image_name,
            "prompt": clean_section
        })

    return prompts


def extract_all_image_prompts_from_output(output_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract all image prompts from an output folder structure.

    Args:
        output_path: Path to the week's output folder

    Returns:
        Dictionary with platform keys and lists of image prompts with metadata
    """
    all_prompts = {}

    for platform_key, platform_info in get_platforms().items():
        folder_name = platform_info["output_folder"]
        platform_path = output_path / folder_name

        if not platform_path.exists():
            continue

        platform_prompts = []

        # Find all markdown files in the platform folder (including subdirectories)
        for md_file in platform_path.glob("**/*.md"):
            if md_file.name.startswith("_"):  # Skip hidden/temp files
                continue

            prompts = extract_image_prompts_from_content(md_file)

            for prompt in prompts:
                # Determine asset folder name based on content file
                # e.g., post1_monday_educational_carousel.md -> post1_assets
                # For files in subdirectories, keep the subdirectory path
                base_name = md_file.stem
                if "_" in base_name:
                    asset_folder_name = base_name.split("_")[0] + "_assets"
                else:
                    asset_folder_name = base_name + "_assets"

                # If file is in a subdirectory, include that in the asset path
                relative_parent = md_file.parent.relative_to(platform_path)
                if str(relative_parent) != ".":
                    asset_folder_name = str(relative_parent / asset_folder_name)

                platform_prompts.append({
                    "platform": platform_key,
                    "source_file": str(md_file.relative_to(platform_path)),
                    "asset_folder": asset_folder_name,
                    "name": prompt["name"],
                    "prompt": prompt["prompt"],
                    "specs": platform_info.get("specs", {})
                })

        if platform_prompts:
            all_prompts[platform_key] = platform_prompts

    return all_prompts


def get_image_dimensions(platform_key: str, prompt_name: str) -> tuple:
    """
    Determine image dimensions based on platform and prompt context.

    Args:
        platform_key: Platform identifier
        prompt_name: Name of the prompt (e.g., "Slide 1", "Cover")

    Returns:
        Tuple of (width, height) in pixels
    """
    # Default dimensions by platform
    platform_defaults = {
        "instagram": (1080, 1080),      # 1:1 square
        "twitter": (1200, 675),          # 16:9
        "linkedin": (1200, 675),         # 16:9
        "thread": (1080, 1080),          # 1:1
        "pinterest": (1000, 1500),       # 2:3 vertical
        "xiaohongshu": (1080, 1440),     # 3:4 vertical
        "reddit": (1200, 675),           # 16:9
        "substack": (1200, 675),         # 16:9 header
    }

    # Check for specific format hints in prompt name
    prompt_lower = prompt_name.lower()

    if "story" in prompt_lower or "stories" in prompt_lower:
        return (1080, 1920)  # 9:16 stories
    elif "cover" in prompt_lower and platform_key == "xiaohongshu":
        return (1080, 1440)  # 3:4 cover
    elif "4:5" in prompt_lower:
        return (1080, 1350)  # 4:5 Instagram portrait
    elif "3:4" in prompt_lower:
        return (1080, 1440)  # 3:4
    elif "1:1" in prompt_lower or "square" in prompt_lower:
        return (1080, 1080)  # Square
    elif "16:9" in prompt_lower:
        return (1200, 675)   # Landscape

    return platform_defaults.get(platform_key, (1080, 1080))


def _decode_image_data(raw_data) -> bytes:
    """
    Decode image data from various formats.

    The Gemini API can return image data in different formats:
    - Raw bytes (direct binary data)
    - Base64-encoded string
    - Base64-encoded bytes

    This helper handles all these cases to ensure we get raw image bytes.

    Returns:
        Decoded image bytes
    """
    import base64

    # PNG starts with: 0x89 0x50 0x4E 0x47 (‰PNG)
    # JPEG starts with: 0xFF 0xD8 0xFF
    # GIF starts with: 0x47 0x49 0x46 (GIF8)
    valid_headers = [b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'GIF8']

    if isinstance(raw_data, str):
        # Data is base64-encoded string
        return base64.b64decode(raw_data)
    elif isinstance(raw_data, bytes):
        # Check if it's already raw image data
        if raw_data[:4] in valid_headers:
            return raw_data
        else:
            # Try base64 decoding
            try:
                decoded = base64.b64decode(raw_data)
                # Verify decoded data is valid image
                if decoded[:4] in valid_headers:
                    return decoded
                else:
                    # Decoding produced non-image data, use original
                    return raw_data
            except Exception:
                # Not base64 encoded, use as-is
                return raw_data
    else:
        return raw_data


def _convert_to_png(image_data: bytes, mime_type: str = None) -> bytes:
    """
    Convert image data to PNG format to ensure compatibility with Instagram.

    Instagram's API can reject images when the file extension doesn't match
    the actual content format (e.g., WebP saved as .png). This function
    ensures the output is always valid PNG data.

    Args:
        image_data: Raw image bytes (could be PNG, JPEG, WebP, GIF, etc.)
        mime_type: Optional MIME type hint from the API response

    Returns:
        Image data in PNG format
    """
    try:
        from PIL import Image
        import io

        # Open the image from bytes
        img = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (PNG doesn't support all modes)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Keep alpha channel for RGBA/LA
            if img.mode == 'P':
                img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'RGBA', 'L'):
            img = img.convert('RGB')

        # Save as PNG
        output = io.BytesIO()
        img.save(output, format='PNG', optimize=True)
        output.seek(0)

        return output.read()

    except ImportError:
        print("    Warning: PIL not available, cannot convert image format")
        return image_data
    except Exception as e:
        print(f"    Warning: Image conversion failed ({e}), using original")
        return image_data


def _generate_with_gemini_3_pro(
    prompt: str,
    output_path: Path,
    image_name: str,
    width: int,
    height: int,
    style: str
) -> Dict[str, Any]:
    """
    Generate image using Gemini 3 Pro Preview with generate_content API.

    This is the recommended primary approach as it's more reliable than
    the generate_images API which requires Vertex AI or specific access.

    Uses response_modalities=['TEXT', 'IMAGE'] to enable image generation.
    """
    if not GEMINI_API_KEY:
        return {
            "success": False,
            "error": "GEMINI_API_KEY not configured"
        }

    try:
        from google import genai
        from google.genai import types

        # Use Gemini API (no Vertex AI needed for this approach)
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Get dynamic brand configuration
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        primary_color = brand_colors.get('primary', '#007BFF')
        secondary_color = brand_colors.get('secondary', '#6C757D')

        # Replace generic brand placeholders with actual brand name
        prompt = prompt.replace('Your Brand', brand_name).replace('your brand', brand_name).replace('YOUR BRAND', brand_name)

        enhanced_prompt = f"""Generate an image with the following specifications:

{prompt}

Style: {style}
Target dimensions: {width}x{height} pixels
Color palette: Use {primary_color} (primary) and {secondary_color} (secondary) as accent colors.
Clean, professional, modern aesthetic suitable for social media.
High quality, sharp details.

CRITICAL RULES - MUST FOLLOW:
- DO NOT include ANY text, words, letters, numbers, or characters in the image
- DO NOT render any brand names, logos, watermarks, or labels
- DO NOT include placeholder text like "lorem ipsum", "sample text", "your brand", etc.
- The image should be purely visual - NO TEXT AT ALL
- No human faces or identifiable persons
- Suitable for social media

Generate a clean image with NO TEXT WHATSOEVER."""

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=enhanced_prompt,
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE'],
            )
        )

        # Extract image from response
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    if part.inline_data.mime_type.startswith('image/'):
                        # Decode image data (handles various formats)
                        image_data = _decode_image_data(part.inline_data.data)

                        # Convert to PNG format to ensure Instagram compatibility
                        # Gemini may return WebP which causes "Only photo or video" error
                        image_data = _convert_to_png(
                            image_data,
                            mime_type=part.inline_data.mime_type
                        )

                        output_path.mkdir(parents=True, exist_ok=True)
                        image_path = output_path / f"{image_name}.png"

                        with open(image_path, 'wb') as f:
                            f.write(image_data)

                        return {
                            "success": True,
                            "file_path": str(image_path),
                            "dimensions": f"{width}x{height}",
                            "model": "gemini-3-pro-image-preview",
                            "client_type": "gemini_3_pro"
                        }

        return {
            "success": False,
            "error": "Gemini 3 Pro did not return an image"
        }

    except Exception as e:
        error_msg = str(e)
        return {
            "success": False,
            "error": f"Gemini 3 Pro error: {error_msg}"
        }


def _generate_with_dalle_3(
    prompt: str,
    output_path: Path,
    image_name: str,
    width: int,
    height: int
) -> Dict[str, Any]:
    """
    Final fallback: Generate image using OpenAI DALL-E 3.

    Only used if all Gemini/Imagen options fail.
    Requires OPENAI_API_KEY to be configured.
    """
    if not OPENAI_API_KEY:
        return {
            "success": False,
            "error": "OPENAI_API_KEY not configured for DALL-E 3 fallback"
        }

    try:
        import base64
        import httpx
        from openai import OpenAI

        # Create client without proxy
        http_client = httpx.Client(proxy=None)
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            http_client=http_client
        )

        # Get dynamic brand configuration
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        primary_color = brand_colors.get('primary', '#007BFF')
        secondary_color = brand_colors.get('secondary', '#6C757D')

        # Enhanced prompt for DALL-E 3
        enhanced_prompt = f"""{prompt}

Style: Professional, clean, modern digital illustration suitable for social media.
Brand colors: {primary_color} (primary) and {secondary_color} (secondary).
DO NOT include any text, logos, or brand names in the image.
No human faces. High quality, sharp details.

CRITICAL: Never use placeholder text like "lorem ipsum" or random characters."""

        # Determine size (DALL-E 3 supports: 1024x1024, 1792x1024, 1024x1792)
        ratio = width / height
        if ratio > 1.5:  # Wide/landscape
            size = "1792x1024"
        elif ratio < 0.67:  # Tall/portrait
            size = "1024x1792"
        else:  # Square-ish
            size = "1024x1024"

        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt[:4000],  # DALL-E 3 has 4000 char limit
            size=size,
            quality="standard",
            n=1,
            response_format="b64_json"
        )

        if response.data and response.data[0].b64_json:
            # Decode and save image
            image_data = base64.b64decode(response.data[0].b64_json)
            output_path.mkdir(parents=True, exist_ok=True)
            image_path = output_path / f"{image_name}.png"

            with open(image_path, 'wb') as f:
                f.write(image_data)

            return {
                "success": True,
                "file_path": str(image_path),
                "dimensions": size,
                "model": "dall-e-3",
                "client_type": "openai_dalle"
            }
        else:
            return {
                "success": False,
                "error": "DALL-E 3 did not return an image"
            }

    except ImportError:
        return {
            "success": False,
            "error": "openai package not installed. Run: pip install openai"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"DALL-E 3 error: {str(e)}"
        }


def _infer_prompt_type(image_name: str, prompt: str) -> str:
    """
    Infer the image prompt type from the image name and prompt content.

    Args:
        image_name: Name of the image being generated
        prompt: The image generation prompt

    Returns:
        Prompt type string: 'product_shot', 'lifestyle', 'detail', 'carousel', 'flat_lay', or 'general'
    """
    name_lower = image_name.lower()
    prompt_lower = prompt.lower()

    # Check for carousel/slide images
    if any(kw in name_lower for kw in ['slide', 'carousel', 'card', 'page']):
        return 'carousel'

    # Check for product shots
    if any(kw in name_lower for kw in ['product', 'cover', 'planner', 'notebook', 'hero']):
        return 'product_shot'
    if any(kw in prompt_lower for kw in ['product shot', 'product image', 'showcase the planner', 'featuring the planner']):
        return 'product_shot'

    # Check for lifestyle images
    if any(kw in name_lower for kw in ['lifestyle', 'scene', 'desk', 'workspace', 'office', 'coffee']):
        return 'lifestyle'
    if any(kw in prompt_lower for kw in ['lifestyle', 'desk scene', 'workspace', 'in use', 'person using', 'hands holding']):
        return 'lifestyle'

    # Check for detail shots
    if any(kw in name_lower for kw in ['detail', 'close', 'zoom', 'feature', 'binding', 'paper']):
        return 'detail'
    if any(kw in prompt_lower for kw in ['close-up', 'detail shot', 'zoom in', 'showing the']):
        return 'detail'

    # Check for flat lay
    if any(kw in name_lower for kw in ['flatlay', 'flat_lay', 'overhead', 'topdown', 'top_down']):
        return 'flat_lay'
    if any(kw in prompt_lower for kw in ['flat lay', 'overhead view', 'top-down', 'bird\'s eye']):
        return 'flat_lay'

    # Default to general
    return 'general'


def generate_image_with_gemini(
    prompt: str,
    output_path: Path,
    image_name: str,
    width: int = 1080,
    height: int = 1080,
    style: str = "Hand-drawn illustration or watercolor/paper-craft style. Warm color palette (orange, cream, coral). Typography-heavy, textured feel like hand-lettering or paper-cut art. Minimalist, NOT photorealistic, NOT glossy 3D. Anti-AI aesthetic, human-made and artistic.",
    platform: Optional[str] = None,
    prompt_type: Optional[str] = None,
    use_product_reference: bool = True
) -> Dict[str, Any]:
    """
    Generate an image with multi-provider fallback chain.

    Priority order (per BIP implementation):
    1. Gemini 3 Pro Preview (generate_content API) - Most reliable
    2. Imagen 3 (generate_images API, if Vertex AI configured)
    3. Gemini 2.0 Flash (generate_content API)
    4. OpenAI DALL-E 3 (if OPENAI_API_KEY configured)

    Args:
        prompt: The image generation prompt
        output_path: Directory to save the image
        image_name: Name for the output image file (without extension)
        width: Image width in pixels
        height: Image height in pixels
        style: Additional style guidance
        platform: Target platform (instagram, twitter, etc.) for context
        prompt_type: Type of image (product_shot, lifestyle, detail, carousel, general)
        use_product_reference: Whether to enhance prompt with product context

    Returns:
        Dictionary with success status and file path or error
    """
    # Enhance prompt with product reference if enabled
    enhanced_prompt = prompt
    product_context_used = False

    if (use_product_reference and
        PRODUCT_REFERENCE_ENABLED and
        PRODUCT_REFERENCE_AVAILABLE):
        try:
            # Determine prompt type from image name if not specified
            if not prompt_type:
                prompt_type = _infer_prompt_type(image_name, prompt)

            enhanced_prompt = enhance_image_prompt(
                prompt=prompt,
                prompt_type=prompt_type or 'general',
                platform=platform
            )
            product_context_used = True
            print(f"    📦 Product reference context added (type: {prompt_type or 'general'})")
        except Exception as e:
            print(f"    ⚠️  Product reference failed: {e}, using original prompt")
            enhanced_prompt = prompt

    # CRITICAL: Chinese text in AI-generated images is almost always garbled/nonsensical.
    # Force all text in images to be English only, or remove Chinese text requirements.
    enhanced_prompt = enhanced_prompt.replace('Your Brand', brand_name if 'brand_name' in dir() else 'YOUR_BRAND')
    enhanced_prompt += "\n\nCRITICAL TEXT RULE: Any text or typography shown in the image MUST be in English only. Do NOT include any Chinese characters, Japanese, or Korean text in the image — AI image generators cannot reliably render CJK characters and they will appear garbled or nonsensical. If the concept requires text, use English words only."

    if not GEMINI_API_KEY and not VERTEX_PROJECT_ID and not OPENAI_API_KEY:
        return {
            "success": False,
            "error": "No image generation API configured. Set GEMINI_API_KEY, VERTEX_PROJECT_ID, or OPENAI_API_KEY."
        }

    # Priority 1: Gemini 3 Pro Preview (most reliable, uses generate_content API)
    if GEMINI_API_KEY:
        print(f"    🎨 Trying Gemini 3 Pro Preview...")
        result = _generate_with_gemini_3_pro(enhanced_prompt, output_path, image_name, width, height, style)
        if result.get("success"):
            result["product_context_used"] = product_context_used
            return result
        print(f"    ⚠️  Gemini 3 Pro failed: {result.get('error', 'Unknown')}")

    # Priority 2: Imagen 3 (if Vertex AI configured)
    if USE_VERTEX_AI and VERTEX_PROJECT_ID:
        print(f"    🔄 Trying Imagen 3 (Vertex AI)...")
        result = _generate_with_imagen_3(enhanced_prompt, output_path, image_name, width, height, style)
        if result.get("success"):
            result["product_context_used"] = product_context_used
            return result
        print(f"    ⚠️  Imagen 3 failed: {result.get('error', 'Unknown')}")

    # Priority 3: Gemini 2.0 Flash
    if GEMINI_API_KEY:
        print(f"    🔄 Trying Gemini 2.0 Flash...")
        result = _generate_with_gemini_flash(enhanced_prompt, output_path, image_name, width, height, style)
        if result.get("success"):
            result["product_context_used"] = product_context_used
            return result
        print(f"    ⚠️  Gemini Flash failed: {result.get('error', 'Unknown')}")

    # Priority 4: OpenAI DALL-E 3 (final fallback)
    if OPENAI_API_KEY:
        print(f"    🔄 Trying OpenAI DALL-E 3...")
        result = _generate_with_dalle_3(enhanced_prompt, output_path, image_name, width, height)
        if result.get("success"):
            result["product_context_used"] = product_context_used
            return result
        print(f"    ⚠️  DALL-E 3 failed: {result.get('error', 'Unknown')}")

    return {
        "success": False,
        "error": "All image generation providers failed",
        "product_context_used": product_context_used
    }


def _generate_with_imagen_3(
    prompt: str,
    output_path: Path,
    image_name: str,
    width: int,
    height: int,
    style: str
) -> Dict[str, Any]:
    """
    Generate image using Imagen 3 via Vertex AI.

    This is the original PostAll approach, now moved to priority 2.
    Requires Vertex AI configuration.
    """
    try:
        from google import genai
        from google.genai import types

        # Use Vertex AI with v1 API version (avoids v1beta 404 issues)
        client = genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION,
            http_options=types.HttpOptions(api_version='v1')
        )

        # Get dynamic brand configuration
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        primary_color = brand_colors.get('primary', '#007BFF')
        secondary_color = brand_colors.get('secondary', '#6C757D')

        # Enhance prompt with style and dimensions
        enhanced_prompt = f"""{prompt}

Style: {style}
Aspect ratio optimized for {width}x{height} pixels.
Brand colors: {primary_color} (primary) and {secondary_color} (secondary).
DO NOT include any text, logos, or brand names in the image.
Clean, professional, modern aesthetic suitable for social media.
No text overlay - text will be added separately.
High quality, sharp details.

CRITICAL: Never use placeholder text like "lorem ipsum", "sample text", or random characters.
If text is needed, use relevant content from the prompt or leave text areas blank for manual addition."""

        # Use Imagen 3 model for image generation
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=enhanced_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=_get_aspect_ratio(width, height),
                safety_filter_level="BLOCK_ONLY_HIGH",
                person_generation="dont_allow",
            )
        )

        if result.generated_images:
            output_path.mkdir(parents=True, exist_ok=True)
            image_path = output_path / f"{image_name}.png"
            image_data = result.generated_images[0].image
            image_data.save(str(image_path))

            return {
                "success": True,
                "file_path": str(image_path),
                "dimensions": f"{width}x{height}",
                "model": "imagen-3.0-generate-002",
                "client_type": "vertex_ai"
            }
        else:
            return {
                "success": False,
                "error": "No image generated by Imagen API"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Imagen 3 error: {str(e)}"
        }


def _generate_with_gemini_api_fallback(
    prompt: str,
    output_path: Path,
    image_name: str,
    width: int,
    height: int,
    style: str
) -> Dict[str, Any]:
    """
    Fallback: Use Gemini API with API key when Vertex AI credentials are unavailable.
    """
    if not GEMINI_API_KEY:
        return {
            "success": False,
            "error": "GEMINI_API_KEY not configured and Vertex AI credentials unavailable"
        }

    try:
        from google import genai
        from google.genai import types

        # Use Gemini API with API key (not Vertex AI)
        client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version='v1')
        )

        # Get dynamic brand configuration
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        primary_color = brand_colors.get('primary', '#007BFF')
        secondary_color = brand_colors.get('secondary', '#6C757D')

        enhanced_prompt = f"""{prompt}

Style: {style}
Aspect ratio optimized for {width}x{height} pixels.
Brand colors: {primary_color} (primary) and {secondary_color} (secondary).
DO NOT include any text, logos, or brand names in the image.
Clean, professional, modern aesthetic suitable for social media.
No text overlay - text will be added separately.
High quality, sharp details.

CRITICAL: Never use placeholder text like "lorem ipsum", "sample text", or random characters.
If text is needed, use relevant content from the prompt or leave text areas blank for manual addition."""

        # Try Imagen 3 with Gemini API
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=enhanced_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=_get_aspect_ratio(width, height),
                safety_filter_level="BLOCK_ONLY_HIGH",
                person_generation="dont_allow",
            )
        )

        if result.generated_images:
            output_path.mkdir(parents=True, exist_ok=True)
            image_path = output_path / f"{image_name}.png"
            image_data = result.generated_images[0].image
            image_data.save(str(image_path))

            return {
                "success": True,
                "file_path": str(image_path),
                "dimensions": f"{width}x{height}",
                "model": "imagen-3.0-generate-002",
                "client_type": "gemini_api_fallback"
            }
        else:
            return {
                "success": False,
                "error": "No image generated (Gemini API fallback)"
            }

    except Exception as e:
        # If Gemini API also fails, try Gemini Flash
        return _generate_with_gemini_flash_api_only(prompt, output_path, image_name, width, height, style)


def _generate_with_gemini_flash_api_only(
    prompt: str,
    output_path: Path,
    image_name: str,
    width: int,
    height: int,
    style: str
) -> Dict[str, Any]:
    """
    Final fallback: Use Gemini 2.0 Flash with API key only (no Vertex AI).
    Note: Uses default API version (v1beta) as response_modalities requires it.
    """
    try:
        from google import genai
        from google.genai import types

        # Use Gemini API key without specifying api_version
        # response_modalities for image generation requires v1beta (default)
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Get dynamic brand configuration
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        primary_color = brand_colors.get('primary', '#007BFF')
        secondary_color = brand_colors.get('secondary', '#6C757D')

        enhanced_prompt = f"""Generate an image with the following specifications:

{prompt}

Style: {style}
Target dimensions: {width}x{height} pixels
Brand colors: {primary_color} (primary) and {secondary_color} (secondary)
DO NOT include any text, logos, or brand names in the image.
Clean, professional, modern aesthetic suitable for social media.
High quality, sharp details.

CRITICAL: Never use placeholder text like "lorem ipsum", "sample text", or random characters.
If text is needed, use relevant content from the prompt or leave text areas blank for manual addition.

Please generate this image."""

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=enhanced_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    if part.inline_data.mime_type.startswith('image/'):
                        image_data = part.inline_data.data

                        # Convert to PNG format to ensure Instagram compatibility
                        image_data = _convert_to_png(
                            image_data,
                            mime_type=part.inline_data.mime_type
                        )

                        output_path.mkdir(parents=True, exist_ok=True)
                        image_path = output_path / f"{image_name}.png"

                        with open(image_path, 'wb') as f:
                            f.write(image_data)

                        return {
                            "success": True,
                            "file_path": str(image_path),
                            "dimensions": f"{width}x{height}",
                            "model": "gemini-2.0-flash-exp",
                            "client_type": "gemini_api_flash_fallback"
                        }

        return {
            "success": False,
            "error": "Gemini Flash API did not return an image"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"All fallbacks failed: {str(e)}"
        }


def _generate_with_gemini_flash(
    prompt: str,
    output_path: Path,
    image_name: str,
    width: int,
    height: int,
    style: str
) -> Dict[str, Any]:
    """
    Fallback: Generate image using Gemini 2.0 Flash with native image generation.

    This model can generate images as part of its multimodal capabilities.
    Uses the new google-genai SDK. Note: response_modalities requires v1beta API.
    """
    try:
        from google import genai
        from google.genai import types

        # For Gemini Flash image generation, we need v1beta API (default)
        # because response_modalities is not supported in v1
        if USE_VERTEX_AI and VERTEX_PROJECT_ID:
            client = genai.Client(
                vertexai=True,
                project=VERTEX_PROJECT_ID,
                location=VERTEX_LOCATION
            )
        else:
            # Use default API version (v1beta) for response_modalities support
            client = genai.Client(api_key=GEMINI_API_KEY)

        # Get dynamic brand configuration
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        primary_color = brand_colors.get('primary', '#007BFF')
        secondary_color = brand_colors.get('secondary', '#6C757D')

        enhanced_prompt = f"""Generate an image with the following specifications:

{prompt}

Style: {style}
Target dimensions: {width}x{height} pixels
Brand colors: {primary_color} (primary) and {secondary_color} (secondary)
DO NOT include any text, logos, or brand names in the image.
Clean, professional, modern aesthetic suitable for social media.
High quality, sharp details.

CRITICAL: Never use placeholder text like "lorem ipsum", "sample text", or random characters.
If text is needed, use relevant content from the prompt or leave text areas blank for manual addition.

Please generate this image."""

        # Generate with Gemini 2.0 Flash (supports image generation)
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=enhanced_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )
        )

        # Extract image from response
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    if part.inline_data.mime_type.startswith('image/'):
                        # Data is already raw bytes (not base64 encoded)
                        image_data = part.inline_data.data

                        # Convert to PNG format to ensure Instagram compatibility
                        image_data = _convert_to_png(
                            image_data,
                            mime_type=part.inline_data.mime_type
                        )

                        output_path.mkdir(parents=True, exist_ok=True)
                        image_path = output_path / f"{image_name}.png"

                        with open(image_path, 'wb') as f:
                            f.write(image_data)

                        return {
                            "success": True,
                            "file_path": str(image_path),
                            "dimensions": f"{width}x{height}",
                            "model": "gemini-2.0-flash-exp"
                        }

        return {
            "success": False,
            "error": "Gemini Flash did not return an image"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Gemini Flash fallback error: {str(e)}"
        }


def _generate_without_person_param(
    prompt: str,
    output_path: Path,
    image_name: str,
    width: int,
    height: int,
    style: str
) -> Dict[str, Any]:
    """
    Fallback: Retry image generation without person_generation parameter.

    This handles cases where person_generation causes 400 errors due to
    allowlist requirements.
    """
    try:
        from google import genai
        from google.genai import types

        # Create client - prefer Vertex AI if configured
        if USE_VERTEX_AI and VERTEX_PROJECT_ID:
            client = genai.Client(
                vertexai=True,
                project=VERTEX_PROJECT_ID,
                location=VERTEX_LOCATION,
                http_options=types.HttpOptions(api_version='v1')
            )
            client_type = "vertex_ai"
        else:
            client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=types.HttpOptions(api_version='v1')
            )
            client_type = "gemini_api"

        # Get dynamic brand configuration
        brand_name = get_brand_name()
        brand_colors = get_brand_colors()
        primary_color = brand_colors.get('primary', '#007BFF')
        secondary_color = brand_colors.get('secondary', '#6C757D')

        enhanced_prompt = f"""{prompt}

Style: {style}
Aspect ratio optimized for {width}x{height} pixels.
Brand colors: {primary_color} (primary) and {secondary_color} (secondary).
DO NOT include any text, logos, or brand names in the image.
Clean, professional, modern aesthetic suitable for social media.
No people or faces in the image.
High quality, sharp details.

CRITICAL: Never use placeholder text like "lorem ipsum", "sample text", or random characters.
If text is needed, use relevant content from the prompt or leave text areas blank for manual addition."""

        # Generate without person_generation parameter
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=enhanced_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=_get_aspect_ratio(width, height),
                safety_filter_level="BLOCK_ONLY_HIGH",
            )
        )

        if result.generated_images:
            output_path.mkdir(parents=True, exist_ok=True)
            image_path = output_path / f"{image_name}.png"
            image_data = result.generated_images[0].image
            image_data.save(str(image_path))

            return {
                "success": True,
                "file_path": str(image_path),
                "dimensions": f"{width}x{height}",
                "model": "imagen-3.0-generate-002",
                "client_type": client_type,
                "note": "Generated without person_generation param"
            }
        else:
            return {
                "success": False,
                "error": "No image generated (retry without person_generation)"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Retry without person_generation failed: {str(e)}"
        }


def _get_aspect_ratio(width: int, height: int) -> str:
    """
    Convert dimensions to Imagen API aspect ratio string.

    Supported ratios: "1:1", "3:4", "4:3", "9:16", "16:9"
    """
    ratio = width / height

    if abs(ratio - 1.0) < 0.1:
        return "1:1"
    elif abs(ratio - 0.75) < 0.1:  # 3:4
        return "3:4"
    elif abs(ratio - 1.33) < 0.1:  # 4:3
        return "4:3"
    elif abs(ratio - 0.5625) < 0.1:  # 9:16
        return "9:16"
    elif abs(ratio - 1.78) < 0.1:  # 16:9
        return "16:9"
    elif ratio < 1:
        return "3:4"  # Default vertical
    else:
        return "16:9"  # Default horizontal


def generate_images_for_platform(
    platform_key: str,
    output_path: Path,
    prompts: List[Dict[str, Any]],
    progress_callback=None,
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Generate all images for a specific platform.

    Args:
        platform_key: Platform identifier
        output_path: Base output path for the week
        prompts: List of prompt dictionaries
        progress_callback: Optional callback for progress updates
        skip_existing: If True, skip images that already exist

    Returns:
        Dictionary with results summary
    """
    results = {
        "platform": platform_key,
        "total": len(prompts),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "images": []
    }

    platform_info = get_platforms().get(platform_key, {})
    platform_folder = output_path / platform_info.get("output_folder", platform_key)

    for i, prompt_info in enumerate(prompts):
        # Determine output folder
        asset_folder = platform_folder / prompt_info.get("asset_folder", "assets")

        # Clean image name
        image_name = prompt_info["name"].lower().replace(" ", "_").replace("/", "_")
        image_name = re.sub(r'[^a-z0-9_]', '', image_name)

        # Check if image already exists
        if skip_existing:
            existing_path = check_image_exists(asset_folder, image_name)
            if existing_path:
                result = {
                    "success": True,
                    "skipped": True,
                    "file_path": existing_path,
                    "prompt_name": prompt_info["name"],
                    "source_file": prompt_info.get("source_file", ""),
                    "message": "Image already exists, skipped"
                }
                results["skipped"] += 1
                results["images"].append(result)

                if progress_callback:
                    # Pass "skipped" status (we'll use True since it's not a failure)
                    progress_callback(i + 1, len(prompts), f"{prompt_info['name']} (skipped)", True)

                continue

        # Get dimensions
        width, height = get_image_dimensions(platform_key, prompt_info["name"])

        # Generate image with platform context for product reference
        result = generate_image_with_gemini(
            prompt=prompt_info["prompt"],
            output_path=asset_folder,
            image_name=image_name,
            width=width,
            height=height,
            platform=platform_key  # Pass platform for product reference context
        )

        result["prompt_name"] = prompt_info["name"]
        result["source_file"] = prompt_info.get("source_file", "")
        result["skipped"] = False

        if result.get("success"):
            results["success"] += 1
        else:
            results["failed"] += 1

        results["images"].append(result)

        if progress_callback:
            progress_callback(i + 1, len(prompts), prompt_info["name"], result.get("success", False))

    return results


def generate_all_images(output_path: Path, progress_callback=None, skip_existing: bool = True) -> Dict[str, Any]:
    """
    Generate all images for all platforms in an output folder.

    Args:
        output_path: Path to the week's output folder
        progress_callback: Optional callback for progress updates
        skip_existing: If True, skip images that already exist

    Returns:
        Dictionary with comprehensive results
    """
    # Extract all prompts
    all_prompts = extract_all_image_prompts_from_output(output_path)

    total_prompts = sum(len(prompts) for prompts in all_prompts.values())

    results = {
        "output_path": str(output_path),
        "timestamp": datetime.now().isoformat(),
        "total_prompts": total_prompts,
        "total_success": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "platforms": {}
    }

    current_prompt = 0

    for platform_key, prompts in all_prompts.items():
        def platform_progress(i, total, name, success):
            nonlocal current_prompt
            current_prompt += 1
            if progress_callback:
                progress_callback(
                    current_prompt,
                    total_prompts,
                    f"{platform_key}: {name}",
                    success
                )

        platform_results = generate_images_for_platform(
            platform_key,
            output_path,
            prompts,
            platform_progress,
            skip_existing=skip_existing
        )

        results["platforms"][platform_key] = platform_results
        results["total_success"] += platform_results["success"]
        results["total_failed"] += platform_results["failed"]
        results["total_skipped"] += platform_results.get("skipped", 0)

    return results


def generate_image_report(results: Dict[str, Any], output_path: Path) -> str:
    """
    Generate a report of image generation results.

    Args:
        results: Results dictionary from generate_all_images
        output_path: Path to save the report

    Returns:
        Path to the generated report file
    """
    total_prompts = results.get('total_prompts', 0)
    total_success = results.get('total_success', 0)
    total_failed = results.get('total_failed', 0)
    total_skipped = results.get('total_skipped', 0)

    # Calculate success rate (excluding skipped from denominator)
    actual_processed = total_success + total_failed
    success_rate = (total_success / actual_processed * 100) if actual_processed > 0 else 100.0

    report = f"""# Image Generation Report
Generated: {results['timestamp']}

## Summary

| Metric | Value |
|--------|-------|
| Total Prompts | {total_prompts} |
| Generated (New) | {total_success} |
| Skipped (Existing) | {total_skipped} |
| Failed | {total_failed} |
| Success Rate | {success_rate:.1f}% |

"""

    if total_skipped > 0:
        report += f"> **Note**: {total_skipped} images were skipped because they already exist.\n\n"

    if total_skipped == total_prompts:
        report += "✅ **All images already exist. No new images were generated.**\n\n"

    report += "## Platform Breakdown\n\n"

    for platform_key, platform_data in results.get("platforms", {}).items():
        platform_name = get_platforms().get(platform_key, {}).get("name", platform_key)
        report += f"### {platform_name}\n\n"
        report += f"- Total: {platform_data['total']}\n"
        report += f"- Generated: {platform_data['success']}\n"
        report += f"- Skipped: {platform_data.get('skipped', 0)}\n"
        report += f"- Failed: {platform_data['failed']}\n\n"

        if platform_data.get("images"):
            report += "| Image | Status | Model | Path |\n"
            report += "|-------|--------|-------|------|\n"

            for img in platform_data["images"]:
                if img.get("skipped"):
                    status = "⏭️ Skipped"
                    model = "-"
                elif img.get("success"):
                    status = "✓ Generated"
                    model = img.get("model", "unknown")
                    client_type = img.get("client_type", "")
                    if client_type:
                        model = f"{model} ({client_type})"
                else:
                    status = "✗ Failed"
                    model = "-"

                path = img.get("file_path", img.get("error", "N/A"))
                name = img.get("prompt_name", "Unknown")
                report += f"| {name} | {status} | {model} | {path} |\n"

            report += "\n"

    # Save report
    report_path = output_path / "image_generation_report.md"
    report_path.write_text(report, encoding="utf-8")

    return str(report_path)


def get_product_reference_status() -> Dict[str, Any]:
    """
    Get the status of the product reference system.

    Returns:
        Dictionary with product reference system status
    """
    if not PRODUCT_REFERENCE_AVAILABLE:
        return {
            "available": False,
            "enabled": False,
            "message": "Product reference module not installed"
        }

    if not PRODUCT_REFERENCE_ENABLED:
        return {
            "available": True,
            "enabled": False,
            "message": "Product reference disabled in config (PRODUCT_REFERENCE_ENABLED=false)"
        }

    try:
        ref = get_product_reference()
        status = ref.get_status()
        status["available"] = True
        status["message"] = "Product reference system active"
        return status
    except Exception as e:
        return {
            "available": True,
            "enabled": False,
            "error": str(e),
            "message": f"Product reference error: {e}"
        }


def generate_xiaohongshu_cards(
    content_path: Path,
    output_dir: Path,
    cover_image_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Generate Xiaohongshu HTML cards with 3:4 ratio screenshots.

    This creates beautifully styled HTML pages with dark gradient backgrounds
    and cream-colored cards, then captures them as sequential screenshots
    optimized for Xiaohongshu's 3:4 aspect ratio.

    Args:
        content_path: Path to markdown content file
        output_dir: Directory to save HTML and screenshots
        cover_image_path: Optional path to cover image

    Returns:
        Dictionary with generation results
    """
    try:
        from postall.utils.xiaohongshu_cards import (
            generate_xhs_cards_from_content,
            is_playwright_available
        )

        # Check Playwright availability
        if not is_playwright_available():
            return {
                "success": False,
                "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"
            }

        # Read content
        if not content_path.exists():
            return {
                "success": False,
                "error": f"Content file not found: {content_path}"
            }

        content = content_path.read_text(encoding='utf-8')

        # Extract title from content (first # heading)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Untitled"

        # Generate cards
        result = generate_xhs_cards_from_content(
            content=content,
            title=title,
            output_dir=output_dir,
            cover_image_path=str(cover_image_path) if cover_image_path else None,
            image_name_prefix="xhs"
        )

        return result

    except ImportError as e:
        return {
            "success": False,
            "error": f"Xiaohongshu cards module not available: {e}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating Xiaohongshu cards: {e}"
        }


def generate_xiaohongshu_cards_for_platform(
    platform_output_path: Path,
    cover_image_name: str = "cover"
) -> Dict[str, Any]:
    """
    Generate Xiaohongshu HTML cards for all content files in a platform folder.

    This scans the platform folder for markdown files and generates
    HTML cards + screenshots for each.

    Args:
        platform_output_path: Path to platform output folder (e.g., output/xiaohongshu/)
        cover_image_name: Name of cover image to look for in asset folders

    Returns:
        Dictionary with results summary
    """
    results = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "cards": []
    }

    # Find all markdown content files
    for md_file in platform_output_path.glob("**/*.md"):
        if md_file.name.startswith("_"):
            continue

        results["total"] += 1

        # Determine output folder (same as content file location)
        cards_dir = md_file.parent / f"{md_file.stem}_xhs_cards"

        # Look for cover image in asset folder
        asset_folder = md_file.parent / f"{md_file.stem}_assets"
        cover_image = None

        if asset_folder.exists():
            for ext in SUPPORTED_IMAGE_EXTENSIONS:
                cover_path = asset_folder / f"{cover_image_name}{ext}"
                if cover_path.exists():
                    cover_image = cover_path
                    break

        # Generate cards
        print(f"\n[XHS Cards] Processing: {md_file.name}")
        result = generate_xiaohongshu_cards(
            content_path=md_file,
            output_dir=cards_dir,
            cover_image_path=cover_image
        )

        result["source_file"] = str(md_file.relative_to(platform_output_path))

        if result.get("success"):
            results["success"] += 1
            print(f"[XHS Cards] ✓ Generated {result.get('screenshot_count', 0)} screenshots")
        else:
            results["failed"] += 1
            print(f"[XHS Cards] ✗ Failed: {result.get('error', 'Unknown error')}")

        results["cards"].append(result)

    return results
