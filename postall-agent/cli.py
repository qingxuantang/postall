#!/usr/bin/env python3
"""
PostAll Agent CLI

AI-friendly command line interface for content generation and publishing.
Designed for OpenClaw, Claude, and other AI agents.

All output is JSON for easy parsing.

Usage:
    postall-agent generate --topic "..." --platforms twitter,wechat,xhs
    postall-agent image --draft <id>
    postall-agent publish --draft <id> --platforms twitter
    postall-agent list --status draft
"""

import argparse
import json
import sys
import os
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Storage for drafts
DRAFT_DIR = Path(os.environ.get('POSTALL_DRAFT_DIR', '/tmp/postall-agent/drafts'))
DRAFT_DIR.mkdir(parents=True, exist_ok=True)


def output_json(data: Dict[str, Any], success: bool = True):
    """Output JSON response and exit."""
    response = {
        "success": success,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **data
    }
    print(json.dumps(response, ensure_ascii=False, indent=2))
    sys.exit(0 if success else 1)


def output_error(message: str, code: str = "error"):
    """Output error JSON and exit."""
    output_json({"error": code, "message": message}, success=False)


def load_draft(draft_id: str) -> Optional[Dict]:
    """Load a draft by ID."""
    draft_file = DRAFT_DIR / f"{draft_id}.json"
    if not draft_file.exists():
        return None
    with open(draft_file) as f:
        return json.load(f)


def save_draft(draft: Dict) -> str:
    """Save a draft and return its ID."""
    draft_id = draft.get('id') or str(uuid.uuid4())[:8]
    draft['id'] = draft_id
    draft['updated_at'] = datetime.utcnow().isoformat() + "Z"
    
    draft_file = DRAFT_DIR / f"{draft_id}.json"
    with open(draft_file, 'w') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    return draft_id


def generate_with_claude(prompt: str) -> str:
    """Generate content using Claude API."""
    import anthropic
    
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text


def generate_image_with_gemini(prompt: str, output_path: Path) -> str:
    """Generate image using Gemini API."""
    import google.generativeai as genai
    
    api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable not set")
    
    genai.configure(api_key=api_key)
    
    # Use Imagen model for image generation
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    response = model.generate_content(
        f"Generate an image: {prompt}",
        generation_config=genai.GenerationConfig(
            response_mime_type="image/png"
        )
    )
    
    # Save image
    output_path.mkdir(parents=True, exist_ok=True)
    image_path = output_path / "image.png"
    
    if hasattr(response, 'candidates') and response.candidates:
        # Extract image data
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data'):
                import base64
                image_data = base64.b64decode(part.inline_data.data)
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                return str(image_path)
    
    raise ValueError("No image generated")


def cmd_generate(args):
    """Generate content for multiple platforms."""
    topic = args.topic
    platforms = [p.strip() for p in args.platforms.split(',')]
    style = args.style or "professional"
    
    # Validate platforms
    valid_platforms = ['twitter', 'linkedin', 'wechat', 'xhs', 'instagram']
    for p in platforms:
        if p not in valid_platforms:
            output_error(f"Unknown platform: {p}. Valid: {', '.join(valid_platforms)}")
    
    # Build generation prompt
    prompt = f"""Generate social media content for the following topic.
    
Topic: {topic}

Style: {style}

Generate content for these platforms: {', '.join(platforms)}

For each platform, follow these guidelines:
- Twitter: 3-tweet thread, each under 280 chars, engaging and conversational
- LinkedIn: Professional long-form post, 1000-1500 chars, with insights
- WeChat (公众号): Chinese article, 800-1200 chars, with clear structure
- XHS (小红书): Chinese post, casual tone, 300-500 chars, with emoji
- Instagram: English caption, 150-300 chars, with hashtags

IMPORTANT: 
- For Chinese platforms (wechat, xhs), write in Chinese
- For international platforms, write in English
- NO parentheses () in any content - use dashes or commas instead
- NO AI clichés like "震撼" "颠覆认知" "久久不能平静"

Output as JSON with this structure:
{{
  "contents": {{
    "twitter": {{"thread": ["tweet1", "tweet2", "tweet3"]}},
    "linkedin": {{"post": "content"}},
    "wechat": {{"title": "标题", "article": "正文"}},
    "xhs": {{"title": "标题", "content": "正文", "tags": ["tag1", "tag2"]}},
    "instagram": {{"caption": "content", "hashtags": ["tag1", "tag2"]}}
  }},
  "image_prompt": "A prompt for generating a cover image in English"
}}

Only include platforms that were requested. Output valid JSON only, no other text."""

    try:
        # Use Claude API to generate
        response = generate_with_claude(prompt)
        
        # Parse the response - extract JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            contents = json.loads(json_match.group())
        else:
            output_error("Failed to parse AI response as JSON")
        
        # Create draft
        draft = {
            "id": str(uuid.uuid4())[:8],
            "topic": topic,
            "platforms": platforms,
            "style": style,
            "status": "draft",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "contents": contents.get('contents', {}),
            "image_prompt": contents.get('image_prompt', ''),
            "image_path": None
        }
        
        draft_id = save_draft(draft)
        
        output_json({
            "draft_id": draft_id,
            "topic": topic,
            "platforms": platforms,
            "contents": draft['contents'],
            "image_prompt": draft['image_prompt']
        })
        
    except Exception as e:
        output_error(f"Generation failed: {str(e)}")


def cmd_image(args):
    """Generate image for a draft."""
    draft_id = args.draft
    custom_prompt = args.prompt
    
    if draft_id:
        draft = load_draft(draft_id)
        if not draft:
            output_error(f"Draft not found: {draft_id}", "not_found")
        prompt = custom_prompt or draft.get('image_prompt', '')
    else:
        draft = None
        prompt = custom_prompt
    
    if not prompt:
        output_error("No image prompt provided. Use --prompt or generate from draft.")
    
    try:
        # Output directory
        output_dir = DRAFT_DIR / (draft_id or 'custom')
        
        image_path = generate_image_with_gemini(prompt, output_dir)
        
        # Update draft if exists
        if draft_id and draft:
            draft['image_path'] = image_path
            save_draft(draft)
        
        output_json({
            "draft_id": draft_id,
            "image_path": image_path,
            "prompt": prompt
        })
        
    except Exception as e:
        output_error(f"Image generation failed: {str(e)}")


def cmd_publish(args):
    """Publish content to platforms."""
    draft_id = args.draft
    platforms = [p.strip() for p in args.platforms.split(',')] if args.platforms else None
    
    draft = load_draft(draft_id)
    if not draft:
        output_error(f"Draft not found: {draft_id}", "not_found")
    
    # Default to all platforms in draft
    if not platforms:
        platforms = draft.get('platforms', [])
    
    results = {}
    
    # Try to import and use PostAll publishers
    for platform in platforms:
        content = draft.get('contents', {}).get(platform)
        if not content:
            results[platform] = {"success": False, "error": "No content for platform"}
            continue
        
        try:
            # Add parent path for PostAll imports
            sys.path.insert(0, '/opt/postall')
            
            if platform == 'twitter':
                from postall.publishers.twitter_publisher import TwitterPublisher
                publisher = TwitterPublisher()
                # Format thread content
                if 'thread' in content:
                    text = content['thread'][0] if content['thread'] else ''
                else:
                    text = content.get('post', '')
                result = publisher.publish(text, draft.get('image_path'))
                results[platform] = {"success": True, "result": str(result)}
                
            elif platform == 'linkedin':
                from postall.publishers.linkedin_publisher import LinkedInPublisher
                publisher = LinkedInPublisher()
                text = content.get('post', '')
                result = publisher.publish(text, draft.get('image_path'))
                results[platform] = {"success": True, "result": str(result)}
                
            elif platform == 'wechat':
                from postall.publishers.wechat_publisher import WeChatPublisher
                publisher = WeChatPublisher()
                result = publisher.publish(
                    title=content.get('title', ''),
                    content=content.get('article', ''),
                    image_path=draft.get('image_path')
                )
                results[platform] = {"success": True, "result": str(result)}
                
            elif platform == 'xhs':
                from postall.publishers.xhs_publisher import XHSPublisher
                publisher = XHSPublisher()
                result = publisher.publish(
                    title=content.get('title', ''),
                    content=content.get('content', ''),
                    tags=content.get('tags', []),
                    image_path=draft.get('image_path')
                )
                results[platform] = {"success": True, "result": str(result)}
                
            elif platform == 'instagram':
                from postall.publishers.instagram_publisher import InstagramPublisher
                publisher = InstagramPublisher()
                caption = content.get('caption', '')
                hashtags = content.get('hashtags', [])
                full_caption = caption + '\n\n' + ' '.join(f'#{tag}' for tag in hashtags)
                result = publisher.publish(full_caption, draft.get('image_path'))
                results[platform] = {"success": True, "result": str(result)}
                
            else:
                results[platform] = {"success": False, "error": "Unknown platform"}
                
        except ImportError as e:
            results[platform] = {"success": False, "error": f"Publisher not available: {str(e)}"}
        except Exception as e:
            results[platform] = {"success": False, "error": str(e)}
    
    # Update draft status
    all_success = all(r.get('success', False) for r in results.values())
    draft['status'] = 'published' if all_success else 'partial'
    draft['publish_results'] = results
    save_draft(draft)
    
    output_json({
        "draft_id": draft_id,
        "platforms": platforms,
        "results": results,
        "status": draft['status']
    })


def cmd_list(args):
    """List drafts."""
    status_filter = args.status
    
    drafts = []
    for draft_file in DRAFT_DIR.glob('*.json'):
        try:
            with open(draft_file) as f:
                draft = json.load(f)
                if status_filter and draft.get('status') != status_filter:
                    continue
                drafts.append({
                    "id": draft.get('id'),
                    "topic": draft.get('topic'),
                    "platforms": draft.get('platforms'),
                    "status": draft.get('status'),
                    "created_at": draft.get('created_at'),
                    "has_image": bool(draft.get('image_path'))
                })
        except:
            continue
    
    # Sort by created_at descending
    drafts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    output_json({
        "count": len(drafts),
        "drafts": drafts
    })


def cmd_show(args):
    """Show draft details."""
    draft_id = args.draft
    
    draft = load_draft(draft_id)
    if not draft:
        output_error(f"Draft not found: {draft_id}", "not_found")
    
    output_json({"draft": draft})


def cmd_accounts(args):
    """List configured platform accounts."""
    accounts = {}
    
    # Twitter
    if os.environ.get('TWITTER_BEARER_TOKEN') or os.environ.get('TWITTER_ACCESS_TOKEN'):
        accounts['twitter'] = {"configured": True, "username": os.environ.get('TWITTER_USERNAME', 'unknown')}
    
    # LinkedIn
    if os.environ.get('LINKEDIN_ACCESS_TOKEN'):
        accounts['linkedin'] = {"configured": True}
    
    # WeChat
    if os.environ.get('WECHAT_APP_ID'):
        accounts['wechat'] = {"configured": True, "app_id": os.environ.get('WECHAT_APP_ID')}
    
    # XHS
    xhs_paths = [
        Path('/app/data/xiaohongshu/account.json'),
        Path('/opt/postall/data/xiaohongshu/account.json'),
        Path(os.path.expanduser('~/.postall/xhs/account.json'))
    ]
    if os.environ.get('XHS_COOKIE') or any(p.exists() for p in xhs_paths):
        accounts['xhs'] = {"configured": True}
    
    # Instagram
    if os.environ.get('INSTAGRAM_ACCESS_TOKEN'):
        accounts['instagram'] = {"configured": True}
    
    output_json({
        "accounts": accounts,
        "configured_count": len(accounts)
    })


def main():
    parser = argparse.ArgumentParser(
        prog="postall-agent",
        description="PostAll Agent CLI - AI-friendly content generation and publishing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate content for multiple platforms
  postall-agent generate --topic "AI 编程趋势" --platforms twitter,linkedin,wechat

  # Generate image for a draft
  postall-agent image --draft abc123

  # Publish draft to specific platforms
  postall-agent publish --draft abc123 --platforms twitter,linkedin

  # List all drafts
  postall-agent list --status draft

  # Show draft details
  postall-agent show --draft abc123

All output is JSON for easy parsing by AI agents.
"""
    )
    
    parser.add_argument('--version', '-v', action='version', version='postall-agent 0.1.0')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # generate
    gen = subparsers.add_parser('generate', help='Generate content for platforms')
    gen.add_argument('--topic', '-t', required=True, help='Topic or idea to write about')
    gen.add_argument('--platforms', '-p', required=True, help='Comma-separated platforms: twitter,linkedin,wechat,xhs,instagram')
    gen.add_argument('--style', '-s', help='Writing style (default: professional)')
    gen.add_argument('--url', '-u', help='URL to extract content from (YouTube, article, etc.)')
    
    # image
    img = subparsers.add_parser('image', help='Generate image for draft')
    img.add_argument('--draft', '-d', help='Draft ID')
    img.add_argument('--prompt', '-p', help='Custom image prompt')
    
    # publish
    pub = subparsers.add_parser('publish', help='Publish draft to platforms')
    pub.add_argument('--draft', '-d', required=True, help='Draft ID')
    pub.add_argument('--platforms', '-p', help='Comma-separated platforms (default: all in draft)')
    
    # list
    lst = subparsers.add_parser('list', help='List drafts')
    lst.add_argument('--status', '-s', choices=['draft', 'published', 'partial'], help='Filter by status')
    
    # show
    shw = subparsers.add_parser('show', help='Show draft details')
    shw.add_argument('--draft', '-d', required=True, help='Draft ID')
    
    # accounts
    subparsers.add_parser('accounts', help='List configured platform accounts')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to command
    commands = {
        'generate': cmd_generate,
        'image': cmd_image,
        'publish': cmd_publish,
        'list': cmd_list,
        'show': cmd_show,
        'accounts': cmd_accounts
    }
    
    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
