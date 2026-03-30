#!/usr/bin/env python3
"""
Clean generated content and publish to specified platform.

Strips metadata, headers, image prompts — leaves only publishable content.

Usage:
    python clean_and_publish.py twitter <content_file> [image_path]
    python clean_and_publish.py linkedin <content_file> [image_path]
    python clean_and_publish.py xhs <cards_dir> [title] [wechat_md_path]
"""
import sys
import re
import os

sys.path.insert(0, '/app')
os.chdir('/app')

from postall.project_config import init_project
init_project('/app/project/project.yaml')

platform = sys.argv[1]  # twitter, linkedin, xhs
content_file = sys.argv[2]
image_path = sys.argv[3] if len(sys.argv) > 3 else None


def clean_content(text, platform):
    """Strip all metadata, headers, image prompts — leave only publishable content."""
    lines = text.split('\n')
    clean_lines = []
    
    # Detect metadata block at start
    metadata_keywords = ['Analysis', 'Score', 'Hook', 'Trigger', 'AIDA', 'Currency', 'Predicted']
    skip_until_separator = False
    
    for i, line in enumerate(lines[:10]):
        if line.startswith('##') and any(kw in line for kw in metadata_keywords):
            skip_until_separator = True
            break
    
    found_content_start = not skip_until_separator
    
    for line in lines:
        # Stop at Image Prompt section
        if '### Image Prompt' in line or '## Image Prompts' in line:
            break
        
        # Skip metadata block until ---
        if not found_content_start:
            if line.strip() == '---':
                found_content_start = True
            continue
        
        # Platform-specific header handling
        if platform == 'wechat':
            if re.match(r'^##\s*(WeChat Article|微信文章)\s*[-–]', line):
                continue
        else:
            if re.match(r'^#{1,2}\s+', line):
                continue
        
        # Skip metadata lines
        if re.match(r'^\*\*[A-Za-z0-9 ()]+:\*\*', line):
            continue
        
        if line.strip() in ['**Thread:**', '**Image Prompts**', '## Image Prompts']:
            continue
        if re.match(r'^\*\*Thread\s*\(\d+\s*tweets?\):\*\*', line.strip(), re.IGNORECASE):
            continue
        
        # Handle --- separators
        if line.strip() == '---':
            if platform == 'twitter':
                clean_lines.append(line)
            continue
        
        # Remove ### subheaders for non-wechat
        if platform != 'wechat' and re.match(r'^###\s+', line):
            continue
        
        # Remove markdown bold for LinkedIn
        if platform == 'linkedin':
            line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
            line = re.sub(r'\\[0-9]+', '', line)
        
        # Remove parentheses (causes LinkedIn truncation)
        line = re.sub(r'\s*\([^)]*\)', '', line)
        line = re.sub(r'\s*（[^）]*）', '', line)
        
        # Remove tweet labels
        line = re.sub(r'【推文\d+】\s*', '', line)
        line = re.sub(r'\[推文\d+\]\s*', '', line)
        line = re.sub(r'\[Tweet\s*\d+\]\s*', '', line, flags=re.IGNORECASE)
        
        if not line.strip():
            continue
        
        clean_lines.append(line)
    
    result = '\n'.join(clean_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


# Read and clean content
raw = open(content_file).read()
cleaned = clean_content(raw, platform)

print(f"=== CLEANED CONTENT ({len(cleaned)} chars) ===")
print(cleaned[:500])
print("...")
print(f"=== END PREVIEW ===\n")

# Publish
if platform == 'twitter':
    from postall.publishers.twitter_publisher import TwitterPublisher
    pub = TwitterPublisher()
    media = [image_path] if image_path else None
    result = pub.publish(cleaned, media_paths=media, as_thread=True)

elif platform == 'linkedin':
    from postall.publishers.linkedin_publisher import LinkedInPublisher
    pub = LinkedInPublisher()
    media = [image_path] if image_path else None
    result = pub.publish(cleaned, media_paths=media)

elif platform == 'xhs':
    from postall.publishers.xhs_publisher import publish_xhs_sync
    cards_dir = content_file
    title = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(os.path.dirname(cards_dir))
    wechat_path = sys.argv[4] if len(sys.argv) > 4 else None
    result = publish_xhs_sync(cards_dir=cards_dir, title=title, wechat_md_path=wechat_path)

else:
    print(f"Unknown platform: {platform}")
    print("Supported: twitter, linkedin, xhs")
    sys.exit(1)

print(f"Result: {result}")
