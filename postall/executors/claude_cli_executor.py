"""
Claude Code CLI Executor (Primary Method)
Uses Claude Code Max subscription via CLI
"""

import subprocess
from pathlib import Path
from typing import Dict, Any

from postall.config import CLAUDE_CLI_PATH, EXECUTION_TIMEOUT, PROJECT_ROOT, get_brand_name, get_brand_style


def execute_with_claude_cli(prompt: str, output_path: Path, platform_key: str) -> Dict[str, Any]:
    """
    Execute content generation using Claude Code CLI.

    This uses the Claude Code Max subscription through the CLI,
    which provides unlimited usage without API costs.

    Args:
        prompt: The full prompt for content generation
        output_path: Directory to save generated content
        platform_key: Platform identifier (e.g., 'instagram', 'twitter')

    Returns:
        Dictionary with:
        - success: bool
        - output: generated content
        - image_prompts: prompts for image generation
        - error: error message if failed
    """

    # Build system prompt for Claude Code with dynamic brand info
    brand_name = get_brand_name()
    brand_style = get_brand_style()
    system_prompt = f"""You are generating social media content for {brand_name}.

CRITICAL RULES:
1. Generate content ready for posting
2. Follow brand voice: {brand_style}
3. Include hashtags where appropriate
4. Provide image generation prompts for visual content
5. Output as markdown files

OUTPUT FORMAT:
Save generated content to: {output_path}

For each post, create:
1. A markdown file with the post content
2. Image prompts section at the end (marked with ## Image Prompts)

TASK:
{prompt}
"""

    # Build Claude Code CLI command
    cmd = [
        CLAUDE_CLI_PATH,
        "--dangerously-skip-permissions",
        "--print",
        "--output-format", "text",
        "-p", system_prompt
    ]

    try:
        # Execute in project directory
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for completion with timeout
        stdout, stderr = process.communicate(timeout=EXECUTION_TIMEOUT)

        if process.returncode == 0:
            # Parse output and save to files
            content = stdout.strip()

            # Extract image prompts if present
            image_prompts = ""
            if "## Image Prompts" in content:
                parts = content.split("## Image Prompts")
                content = parts[0]
                image_prompts = "## Image Prompts" + parts[1] if len(parts) > 1 else ""

            # Save content to platform file
            content_file = output_path / f"{platform_key}_content.md"
            content_file.write_text(content, encoding="utf-8")

            return {
                "success": True,
                "output": content,
                "image_prompts": image_prompts,
                "file_path": str(content_file)
            }
        else:
            return {
                "success": False,
                "error": f"CLI error: {stderr}"
            }

    except subprocess.TimeoutExpired:
        process.kill()
        return {
            "success": False,
            "error": f"Execution timed out after {EXECUTION_TIMEOUT}s"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Claude CLI not found at '{CLAUDE_CLI_PATH}'"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {str(e)}"
        }


def check_claude_cli_available() -> tuple:
    """
    Check if Claude Code CLI is available and working.

    Returns:
        Tuple of (is_available, message)
    """
    try:
        result = subprocess.run(
            [CLAUDE_CLI_PATH, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"Claude CLI available: {version}"
        else:
            return False, f"CLI error: {result.stderr}"
    except FileNotFoundError:
        return False, f"Claude CLI not found at '{CLAUDE_CLI_PATH}'"
    except Exception as e:
        return False, f"Error checking CLI: {str(e)}"
