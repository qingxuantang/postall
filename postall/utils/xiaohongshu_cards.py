"""
Xiaohongshu HTML Cards Generator

Transform markdown content into beautifully styled HTML pages with 3:4 ratio screenshots.
Based on James Writing Workflow's xiaohongshu-images skill.

Features:
- Dark gradient background
- 600px × 800px cream-colored card
- 3:4 aspect ratio screenshots (1200×1600 pixels)
- Smart text boundary detection (no text cut-off)
- Google Fonts (Noto Serif SC, Inter, JetBrains Mono)
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import re
import markdown

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Screenshot specifications
CONTAINER_WIDTH = 600
CONTAINER_HEIGHT = 800
DEVICE_SCALE_FACTOR = 2
OUTPUT_WIDTH = CONTAINER_WIDTH * DEVICE_SCALE_FACTOR   # 1200px
OUTPUT_HEIGHT = CONTAINER_HEIGHT * DEVICE_SCALE_FACTOR  # 1600px


# HTML Template with CSS styling
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700&family=Inter:wght@300;400;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background: linear-gradient(135deg, #1e1e2e 0%, #2d2b55 50%, #3e3a5f 100%);
            background-attachment: fixed;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 100vh;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}

        .container {{
            width: {container_width}px;
            height: {container_height}px;
            background-color: #F9F9F6;
            box-shadow:
                0 25px 50px rgba(0, 0, 0, 0.4),
                0 10px 30px rgba(0, 10, 20, 0.3),
                0 5px 15px rgba(0, 5, 15, 0.25);
            overflow-y: auto;
            overflow-x: hidden;
            position: relative;
        }}

        /* Hide scrollbar */
        .container::-webkit-scrollbar {{
            width: 0;
            background: transparent;
        }}

        .container {{
            -ms-overflow-style: none;
            scrollbar-width: none;
        }}

        .cover-image {{
            width: 100%;
            height: 350px;
            object-fit: cover;
            display: block;
        }}

        .content {{
            padding: 20px 50px 50px 50px;
        }}

        h1 {{
            font-family: 'Noto Serif SC', serif;
            font-size: 42px;
            color: #000000;
            font-weight: 700;
            line-height: 1.3;
            margin-bottom: 30px;
        }}

        h2 {{
            font-family: 'Times New Roman', serif;
            font-size: 26px;
            color: #000000;
            font-weight: 700;
            margin: 40px 0 20px;
        }}

        h3 {{
            font-size: 22px;
            color: #2c3e50;
            font-weight: 600;
            margin: 30px 0 15px;
        }}

        h4 {{
            font-size: 20px;
            color: #5a6c7d;
            font-weight: 600;
            margin: 25px 0 12px;
        }}

        p {{
            font-size: 20px;
            color: #333333;
            line-height: 2;
            margin-bottom: 20px;
        }}

        .en-title {{
            font-family: 'Inter', sans-serif;
            font-size: 18px;
            color: #888888;
            font-weight: 300;
        }}

        .metadata {{
            font-size: 14px;
            color: #888888;
        }}

        a {{
            color: #4a9eff;
            text-decoration: none;
            transition: 0.2s ease;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        em {{
            color: #000000;
            font-style: normal;
        }}

        strong {{
            font-weight: bold;
        }}

        mark {{
            background-color: #fffde7;
            color: #000000;
            font-weight: bold;
            border-bottom: 1px solid #ffc107;
            border-radius: 2px;
            padding: 2px 4px;
        }}

        ul, ol {{
            font-size: 20px;
            padding-left: 20px;
            margin-bottom: 20px;
        }}

        li {{
            margin-bottom: 8px;
        }}

        blockquote {{
            border-left: 4px solid #4a9eff;
            padding-left: 20px;
            font-style: italic;
            margin: 20px 0;
        }}

        pre {{
            background-color: #f5f5f5;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 20px;
            overflow-x: auto;
        }}

        code {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 17px;
            line-height: 1.6;
        }}

        p code, li code {{
            background-color: #f5f5f5;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: inherit;
        }}

        /* Responsive Design */
        @media (max-width: 650px) {{
            body {{
                padding: 10px;
            }}

            .container {{
                width: 100%;
                min-height: 80vh;
                height: auto;
            }}

            .content {{
                padding: 30px;
            }}

            h1 {{
                font-size: 36px;
            }}

            h2 {{
                font-size: 24px;
            }}

            pre {{
                padding: 15px;
            }}

            code {{
                font-size: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {cover_image}
        <div class="content">
            {content_html}
        </div>
    </div>
</body>
</html>
"""


def markdown_to_html(markdown_text: str) -> str:
    """
    Convert markdown to HTML with auto-highlighting for key phrases.

    Args:
        markdown_text: Markdown formatted text

    Returns:
        HTML string
    """
    # Convert markdown to HTML
    md = markdown.Markdown(extensions=['extra', 'codehilite', 'fenced_code'])
    html = md.convert(markdown_text)

    # Auto-highlight patterns (key phrases that should be marked)
    # These are common patterns for memorable quotes in Chinese content
    highlight_patterns = [
        r'「([^」]+)」',  # Quoted text in Chinese quotes
        r'"([^"]+)"',    # Quoted text in Western quotes
    ]

    # Apply mark tags to quoted content
    for pattern in highlight_patterns:
        html = re.sub(pattern, r'<mark>\1</mark>', html)

    return html


def generate_xhs_html(
    content: str,
    title: str,
    cover_image_path: Optional[str] = None,
    output_path: Path = None
) -> str:
    """
    Generate Xiaohongshu-styled HTML from markdown content.

    Args:
        content: Markdown content
        title: Article title
        cover_image_path: Path to cover image (optional)
        output_path: Path to save HTML file (optional)

    Returns:
        HTML string
    """
    # Convert markdown to HTML
    content_html = markdown_to_html(content)

    # Cover image HTML
    cover_html = ""
    if cover_image_path:
        # Use relative path for the HTML
        if Path(cover_image_path).exists():
            cover_html = f'<img src="{cover_image_path}" class="cover-image" alt="Cover">'

    # Generate complete HTML
    html = HTML_TEMPLATE.format(
        title=title,
        container_width=CONTAINER_WIDTH,
        container_height=CONTAINER_HEIGHT,
        cover_image=cover_html,
        content_html=content_html
    )

    # Save to file if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')
        print(f"[XHS Cards] HTML saved to: {output_path}")

    return html


def _get_container_info(page) -> dict:
    """Get container element scroll information."""
    script = """
    () => {
        const container = document.querySelector('.container');
        if (!container) return null;

        const rect = container.getBoundingClientRect();
        return {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
            scrollHeight: container.scrollHeight,
            clientHeight: container.clientHeight
        };
    }
    """
    return page.evaluate(script)


def _scroll_container(page, scroll_top: int) -> int:
    """Scroll container to specific position."""
    script = f"""
    () => {{
        const container = document.querySelector('.container');
        if (container) {{
            container.scrollTop = {scroll_top};
            return container.scrollTop;
        }}
        return 0;
    }}
    """
    return page.evaluate(script)


def _find_safe_cut_position(page, viewport_height: int) -> dict:
    """
    Find safe position to cut screenshot without splitting text.

    Returns:
        Dict with safe_y, has_more, next_start
    """
    script = f"""
    () => {{
        const container = document.querySelector('.container');
        if (!container) return {{ safe_y: {viewport_height}, has_more: false, next_start: 0 }};

        const containerRect = container.getBoundingClientRect();
        const viewportHeight = {viewport_height};
        const currentScroll = container.scrollTop;
        const maxScroll = container.scrollHeight - container.clientHeight;

        if (currentScroll >= maxScroll) {{
            return {{ safe_y: viewportHeight, has_more: false, next_start: currentScroll }};
        }}

        const blockElements = container.querySelectorAll(
            'p, h1, h2, h3, h4, h5, h6, li, blockquote, pre, div.content > *, img, figure'
        );

        let lastSafeY = 0;
        let nextStartScroll = currentScroll + viewportHeight;
        let foundCutElement = false;

        for (const el of blockElements) {{
            const rect = el.getBoundingClientRect();
            const elTop = rect.top - containerRect.top;
            const elBottom = rect.bottom - containerRect.top;

            if (elBottom <= 0) continue;
            if (elTop >= viewportHeight) break;

            if (elTop >= 0 && elBottom <= viewportHeight) {{
                lastSafeY = elBottom;
            }} else if (elTop >= 0 && elBottom > viewportHeight) {{
                foundCutElement = true;
                nextStartScroll = currentScroll + elTop;
                break;
            }} else if (elTop < 0 && elBottom > viewportHeight) {{
                lastSafeY = viewportHeight;
                nextStartScroll = currentScroll + viewportHeight;
                break;
            }}
        }}

        if (!foundCutElement) {{
            lastSafeY = viewportHeight;
            nextStartScroll = currentScroll + viewportHeight;
        }}

        if (lastSafeY < viewportHeight && lastSafeY > 0) {{
            lastSafeY = Math.min(lastSafeY + 5, viewportHeight);
        }}

        const hasMore = nextStartScroll < container.scrollHeight - 10;

        return {{
            safe_y: Math.floor(lastSafeY),
            has_more: hasMore,
            next_start: Math.floor(nextStartScroll)
        }};
    }}
    """
    return page.evaluate(script)


def _add_whitespace_mask(page, from_y: int):
    """Add whitespace mask to cover partial content."""
    script = f"""
    () => {{
        const container = document.querySelector('.container');
        if (!container) return false;

        const existingMask = document.getElementById('screenshot-mask');
        if (existingMask) existingMask.remove();

        const mask = document.createElement('div');
        mask.id = 'screenshot-mask';
        mask.style.cssText = `
            position: absolute;
            left: 0;
            right: 0;
            top: {from_y}px;
            bottom: 0;
            background-color: #F9F9F6;
            z-index: 9999;
            pointer-events: none;
        `;

        const containerPosition = window.getComputedStyle(container).position;
        if (containerPosition === 'static') {{
            container.style.position = 'relative';
        }}

        container.appendChild(mask);
        return true;
    }}
    """
    return page.evaluate(script)


def _remove_whitespace_mask(page):
    """Remove whitespace mask."""
    script = """
    () => {
        const mask = document.getElementById('screenshot-mask');
        if (mask) {
            mask.remove();
            return true;
        }
        return false;
    }
    """
    return page.evaluate(script)


def capture_xhs_screenshots(
    html_path: Path,
    output_dir: Path,
    image_name_prefix: str = "xhs"
) -> List[str]:
    """
    Capture sequential 3:4 ratio screenshots from HTML file.

    Args:
        html_path: Path to HTML file
        output_dir: Directory to save screenshots
        image_name_prefix: Prefix for screenshot files

    Returns:
        List of generated screenshot file paths
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("[XHS Cards] Error: Playwright not installed")
        print("Install with: pip install playwright && playwright install chromium")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[XHS Cards] Opening: {html_path}")
    print(f"[XHS Cards] Screenshots will be saved to: {output_dir}")
    print(f"[XHS Cards] Container size: {CONTAINER_WIDTH}x{CONTAINER_HEIGHT} (3:4 ratio)")
    print(f"[XHS Cards] Output size: {OUTPUT_WIDTH}x{OUTPUT_HEIGHT} ({DEVICE_SCALE_FACTOR}x scale)")

    captured_screenshots = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            viewport_width = CONTAINER_WIDTH + 200
            viewport_height = CONTAINER_HEIGHT + 200

            context = browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=DEVICE_SCALE_FACTOR
            )
            page = context.new_page()

            # Navigate and wait for content
            file_url = f"file://{html_path.resolve()}"
            page.goto(file_url, wait_until="networkidle")
            page.wait_for_timeout(2000)  # Wait for fonts/images

            # Get container info
            container_info = _get_container_info(page)
            if not container_info:
                print("[XHS Cards] Error: Could not find .container element")
                browser.close()
                return []

            print(f"[XHS Cards] Container: {container_info['width']}x{container_info['height']}")
            print(f"[XHS Cards] Content height: {container_info['scrollHeight']}px")

            container = page.locator('.container')
            scroll_height = container_info['scrollHeight']
            client_height = container_info['clientHeight']

            # Start from the top
            _scroll_container(page, 0)
            page.wait_for_timeout(100)

            screenshot_index = 1
            current_scroll = 0
            max_iterations = 50

            print(f"[XHS Cards] Capturing screenshots...")

            while screenshot_index <= max_iterations:
                # Scroll to current position
                actual_scroll = _scroll_container(page, current_scroll)
                page.wait_for_timeout(150)

                # Find safe cut position
                cut_info = _find_safe_cut_position(page, client_height)
                safe_y = cut_info['safe_y']
                has_more = cut_info['has_more']
                next_start = cut_info['next_start']

                # Add mask if needed
                needs_mask = safe_y < client_height and has_more
                if needs_mask:
                    _add_whitespace_mask(page, safe_y)
                    page.wait_for_timeout(50)

                # Capture screenshot
                filename = f"{image_name_prefix}-{screenshot_index:02d}.png"
                filepath = output_dir / filename
                container.screenshot(path=str(filepath))

                # Remove mask
                if needs_mask:
                    _remove_whitespace_mask(page)

                visible_height = safe_y if needs_mask else client_height
                print(f"  {filename}: scroll={current_scroll}, visible={visible_height}px" +
                      (" [padded]" if needs_mask else ""))

                captured_screenshots.append(str(filepath))

                # Check if done
                if not has_more:
                    break

                # Move to next section
                current_scroll = next_start
                screenshot_index += 1

                # Safety check
                if current_scroll >= scroll_height - 10:
                    break

            browser.close()

    except Exception as e:
        print(f"[XHS Cards] Error during screenshot capture: {e}")
        import traceback
        traceback.print_exc()
        return []

    print(f"[XHS Cards] Capture complete! Generated {len(captured_screenshots)} screenshots")
    return captured_screenshots


def generate_xhs_cards_from_content(
    content: str,
    title: str,
    output_dir: Path,
    cover_image_path: Optional[str] = None,
    image_name_prefix: str = "xhs"
) -> Dict[str, Any]:
    """
    Generate Xiaohongshu HTML cards and screenshots from content.

    Complete workflow:
    1. Generate styled HTML
    2. Capture 3:4 ratio screenshots

    Args:
        content: Markdown content
        title: Article title
        output_dir: Output directory for HTML and screenshots
        cover_image_path: Optional cover image path
        image_name_prefix: Prefix for screenshot files

    Returns:
        Dictionary with results
    """
    # Generate HTML
    html_path = output_dir / "xhs-preview.html"
    html = generate_xhs_html(
        content=content,
        title=title,
        cover_image_path=cover_image_path,
        output_path=html_path
    )

    # Capture screenshots
    screenshots = capture_xhs_screenshots(
        html_path=html_path,
        output_dir=output_dir,
        image_name_prefix=image_name_prefix
    )

    return {
        "success": len(screenshots) > 0,
        "html_path": str(html_path),
        "screenshots": screenshots,
        "screenshot_count": len(screenshots)
    }


def is_playwright_available() -> bool:
    """Check if Playwright is available."""
    return PLAYWRIGHT_AVAILABLE
