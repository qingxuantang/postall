"""
Gemini API Executor (Fallback 2)
Uses Google Gemini API when both Claude options fail
"""

from pathlib import Path
from typing import Dict, Any

from postall.config import GEMINI_API_KEY, get_brand_name, get_brand_style


def execute_with_gemini_api(prompt: str, output_path: Path, platform_key: str, language: str = "") -> Dict[str, Any]:
    """
    Execute content generation using Gemini API.

    This is Fallback 2 when both Claude CLI and API fail.
    Uses Google's Generative AI Python SDK.

    Args:
        prompt: The full prompt for content generation
        output_path: Directory to save generated content
        platform_key: Platform identifier
        language: Content language ("en", "zh", or "" for auto)

    Returns:
        Dictionary with success status and content/error
    """

    if not GEMINI_API_KEY:
        return {
            "success": False,
            "error": "GEMINI_API_KEY not configured"
        }

    try:
        import google.generativeai as genai

        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)

        # Use Gemini Pro for text generation
        model = genai.GenerativeModel('gemini-1.5-pro')

        # Build full prompt with instructions using dynamic brand info
        brand_name = get_brand_name()
        brand_style = get_brand_style()
        lang = language or "auto"
        if lang == "zh":
            lang_instruction = "- Write ALL content in Chinese (中文)"
        elif lang == "en":
            lang_instruction = "- Write ALL content in English"
        else:
            lang_instruction = "- Write content in the language that matches the brand voice"

        full_prompt = f"""You are a social media content creator for {brand_name}.

INSTRUCTIONS:
- Generate high-quality, engaging content ready for posting
- Follow brand guidelines: {brand_style}
{lang_instruction}
- Include image generation prompts in a ## Image Prompts section

TASK:
{prompt}
"""

        # Generate content
        response = model.generate_content(full_prompt)

        # Extract content (keep image prompts in the file — image generator needs them)
        content = response.text

        # Save aggregate file (including image prompts — DO NOT strip them)
        content_file = output_path / f"{platform_key}_content.md"
        content_file.write_text(content, encoding="utf-8")

        # Split aggregate into individual post files for scheduler/director
        try:
            from postall.utils.content_parser import process_platform_content
            split_result = process_platform_content(output_path, platform_key)
            if split_result.get('success'):
                print(f"[Executor] Split into {split_result['post_count']} individual files")
            else:
                print(f"[Executor] Content split warning: {split_result.get('error', 'unknown')}")
        except Exception as e:
            print(f"[Executor] Content split error (non-fatal): {e}")

        return {
            "success": True,
            "output": content,
            "file_path": str(content_file),
            "model": "gemini-1.5-pro"
        }

    except ImportError:
        return {
            "success": False,
            "error": "google-generativeai package not installed. Run: pip install google-generativeai"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Gemini API error: {str(e)}"
        }


def execute_review_with_gemini(prompt: str) -> str:
    """
    Execute a review request using Gemini API.

    Used by Content Director for reviewing generated content.

    Args:
        prompt: The review prompt with content to analyze

    Returns:
        Raw response text from Gemini
    """

    if not GEMINI_API_KEY:
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')

        response = model.generate_content(prompt)
        return response.text

    except Exception:
        return None
