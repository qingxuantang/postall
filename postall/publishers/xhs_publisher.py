#!/usr/bin/env python3
"""
小红书发布器 (Xiaohongshu Publisher)

Note: This is a template. Configure your own account settings.
Requires playwright and valid Xiaohongshu cookies.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
import glob
import os
import re

# Account configuration - customize these
ACCOUNTS = {
    "default": {
        "name": "Your Account",
        "cookie": os.getenv("XHS_COOKIE_PATH", "./cookies/xiaohongshu/account.json")
    }
}

def extract_summary_from_content(content_path):
    """Extract summary from content file for Xiaohongshu post"""
    
    with open(content_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    body_lines = []
    
    # Skip metadata patterns
    skip_patterns = [
        r'^\*\*Post Type:\*\*', r'^\*\*Theme:\*\*', r'^\*\*Day:\*\*',
        r'^\*\*Generated:\*\*', r'^\*\*Posting Time:\*\*', r'^\*\*Content Pillar:\*\*',
        r'^# ', r'^## ', r'^### Image Prompt', r'^---$',
    ]
    
    for line in lines:
        stripped = line.strip()
        if 'Image Prompt' in stripped:
            break
        skip = any(re.match(p, stripped) for p in skip_patterns)
        if skip:
            continue
        if stripped:
            body_lines.append(stripped)
    
    return '\n'.join(body_lines[:20])  # Limit to ~20 lines


async def publish_to_xiaohongshu(title: str, content: str, images: list, account: str = "default"):
    """
    Publish content to Xiaohongshu
    
    Args:
        title: Post title
        content: Post body text
        images: List of image paths
        account: Account key from ACCOUNTS config
    
    Returns:
        dict with success status and post URL
    """
    account_config = ACCOUNTS.get(account, ACCOUNTS["default"])
    cookie_path = account_config["cookie"]
    
    if not Path(cookie_path).exists():
        return {"success": False, "error": f"Cookie file not found: {cookie_path}"}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=cookie_path)
        page = await context.new_page()
        
        try:
            # Navigate to creator center
            await page.goto("https://creator.xiaohongshu.com/publish/publish")
            await page.wait_for_load_state("networkidle")
            
            # Upload images
            file_input = await page.wait_for_selector('input[type="file"]')
            await file_input.set_input_files(images)
            
            # Wait for upload
            await asyncio.sleep(3)
            
            # Fill title
            title_input = await page.wait_for_selector('input[placeholder*="标题"]')
            await title_input.fill(title)
            
            # Fill content
            content_area = await page.wait_for_selector('div[contenteditable="true"]')
            await content_area.fill(content)
            
            # Click publish
            publish_btn = await page.wait_for_selector('button:has-text("发布")')
            await publish_btn.click()
            
            # Wait for success
            await asyncio.sleep(5)
            
            return {"success": True, "message": "Published successfully"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            await browser.close()


def publish_sync(title: str, content: str, images: list, account: str = "default"):
    """Synchronous wrapper for publish_to_xiaohongshu"""
    return asyncio.run(publish_to_xiaohongshu(title, content, images, account))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python xhs_publisher.py <title> <content_file> <image1> [image2...]")
        sys.exit(1)
    
    title = sys.argv[1]
    content_file = sys.argv[2]
    images = sys.argv[3:]
    
    content = extract_summary_from_content(content_file)
    result = publish_sync(title, content, images)
    print(result)
