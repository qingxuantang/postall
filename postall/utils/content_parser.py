"""
Content Parser - Parse and split generated content into individual post files

When content is generated via API (not CLI with file access), it's saved to a single
*_content.md file. This module parses that file and creates individual post files
that match the expected format for scheduling and publishing.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


# Day mapping for filename generation
DAY_MAPPING = {
    1: 'monday',
    2: 'tuesday',
    3: 'wednesday',
    4: 'thursday',
    5: 'friday',
    6: 'saturday',
    7: 'sunday'
}

# Chinese day name to English mapping
CHINESE_DAY_MAPPING = {
    '星期一': 'monday', '周一': 'monday',
    '星期二': 'tuesday', '周二': 'tuesday',
    '星期三': 'wednesday', '周三': 'wednesday',
    '星期四': 'thursday', '周四': 'thursday',
    '星期五': 'friday', '周五': 'friday',
    '星期六': 'saturday', '周六': 'saturday',
    '星期日': 'sunday', '星期天': 'sunday', '周日': 'sunday',
}

# Platform-specific configurations
PLATFORM_CONFIG = {
    'instagram': {
        'prefix_pattern': r'(?:Post\s*)?(\d+)',
        'day_mapping': {1: 'monday', 2: 'wednesday', 3: 'friday', 4: 'sunday'},
        'default_type': 'carousel'
    },
    'twitter': {
        'prefix_pattern': r'(?:Tweet\s*)?(\d+)',
        'day_mapping': {1: 'monday', 2: 'tuesday', 3: 'wednesday', 4: 'thursday', 5: 'friday'},
        'default_type': 'tweet'
    },
    'linkedin': {
        'prefix_pattern': r'(?:Post\s*)?(\d+)',
        'day_mapping': {1: 'monday', 2: 'tuesday', 3: 'thursday', 4: 'saturday'},
        'default_type': 'post'
    },
    'thread': {
        'prefix_pattern': r'(?:Post\s*)?(\d+)',
        'day_mapping': {1: 'monday', 2: 'wednesday', 3: 'friday'},
        'default_type': 'post'
    },
    'pinterest': {
        'prefix_pattern': r'(?:Pin\s*)?(\d+)',
        'day_mapping': {1: 'monday', 2: 'wednesday', 3: 'friday', 4: 'sunday'},
        'default_type': 'pin'
    },
    'reddit': {
        'prefix_pattern': r'(?:Post\s*)?(\d+)',
        'day_mapping': {1: 'tuesday', 2: 'thursday', 3: 'saturday'},
        'default_type': 'post'
    },
    'substack': {
        'prefix_pattern': r'(?:Post\s*)?(\d+)',
        'day_mapping': {1: 'friday'},
        'default_type': 'article'
    },
    'xiaohongshu': {
        'prefix_pattern': r'(?:Post\s*)?(\d+)',
        'day_mapping': {1: 'monday', 2: 'thursday'},
        'default_type': 'post'
    }
}


def parse_content_file(content_path: Path, platform_key: str) -> List[Dict]:
    """
    Parse a *_content.md file and extract individual posts.

    Args:
        content_path: Path to the content file (e.g., instagram_content.md)
        platform_key: Platform identifier (e.g., 'instagram', 'twitter')

    Returns:
        List of dictionaries with post data:
        [
            {
                'number': 1,
                'title': 'Educational Carousel',
                'day': 'monday',
                'content': '...',
                'type': 'carousel',
                'day_hint': 'Monday/Tuesday'
            },
            ...
        ]
    """
    if not content_path.exists():
        return []

    content = content_path.read_text(encoding='utf-8')

    # Use platform-specific parser
    if platform_key == 'twitter':
        return _parse_twitter_content(content)
    elif platform_key == 'substack':
        return _parse_substack_content(content)
    elif platform_key == 'thread':
        return _parse_thread_content(content)
    elif platform_key == 'pinterest':
        return _parse_pinterest_content(content)
    else:
        return _parse_standard_content(content, platform_key)


def _parse_pinterest_content(content: str) -> List[Dict]:
    """Parse Pinterest content with ## Pin N format."""
    posts = []

    # Pattern: ## Pin N: Title or ## Pin N - Title
    pin_pattern = r'^##\s+Pin\s+(\d+)\s*[:–-]\s*(.+?)$'
    lines = content.split('\n')
    current_pin = None

    for line in lines:
        match = re.match(pin_pattern, line.strip(), re.IGNORECASE)
        if match:
            # Save previous pin
            if current_pin:
                posts.append(current_pin)

            pin_num = int(match.group(1))
            title = match.group(2).strip()

            # Map pin numbers to days (spread across the week)
            day_mapping = {1: 'monday', 2: 'tuesday', 3: 'wednesday', 4: 'thursday',
                          5: 'friday', 6: 'saturday', 7: 'sunday'}
            day = day_mapping.get(pin_num, 'monday')

            current_pin = {
                'number': pin_num,
                'title': title,
                'day': day,
                'content': line + '\n',
                'type': 'pin',
                'day_hint': None
            }
        elif current_pin:
            current_pin['content'] += line + '\n'

    # Don't forget last pin
    if current_pin:
        posts.append(current_pin)

    # If no pins found, try standard parsing
    if not posts:
        posts = _parse_standard_content(content, 'pinterest')

    return posts


def _parse_twitter_content(content: str) -> List[Dict]:
    """
    Parse Twitter content organized by day/post sections.

    Handles multiple formats:
    - ## Monday, ## Tuesday (English day headers)
    - ## 星期一, ## 星期二 (Chinese day headers)
    - ## 星期一 | Monday_Morning_Tweet.md (Chinese with filename hint)
    - ## Post 1 - Title (numbered post format)
    - --- separated sections
    """
    posts = []

    # Strategy: split by ## headers and parse each section
    sections = _split_by_h2_headers(content)

    if not sections:
        # Fallback: try splitting by --- separators
        sections = _split_by_separator(content)

    post_number = 0
    for section_title, section_content in sections:
        # Skip title/header sections and image prompt sections
        if not section_content.strip():
            continue
        if re.match(r'image\s*prompt', section_title, re.IGNORECASE):
            continue

        # Try to extract day from section title
        day = _extract_day_from_title(section_title)

        # Try to extract a suggested filename from section title
        filename_hint = _extract_filename_hint(section_title)

        # Extract posting time from content
        time_hint = None
        time_patterns = [
            r'\*\*(?:发布时间|Posting Time|Best Time)[:：]\*\*\s*(.+?)(?:\n|$)',
            r'\*\*(?:Posting Time|发布时间)[:：]\*\*\s*(.+?)(?:\n|$)',
        ]
        for tp in time_patterns:
            tm = re.search(tp, section_content, re.IGNORECASE)
            if tm:
                time_hint = tm.group(1).strip()
                break

        post_number += 1

        # Determine post type
        post_type = 'tweet'
        title_lower = section_title.lower()
        content_lower = section_content.lower()
        if 'thread' in title_lower or 'thread' in content_lower:
            post_type = 'thread'

        if not day:
            day = DAY_MAPPING.get(post_number, 'monday')

        # Determine time of day for filename
        time_of_day = 'morning'
        if time_hint:
            if any(x in time_hint.lower() for x in ['afternoon', 'pm', '14', '15', '16', '下午']):
                time_of_day = 'afternoon'
            elif any(x in time_hint.lower() for x in ['evening', '19', '20', '21', '晚']):
                time_of_day = 'evening'

        posts.append({
            'number': post_number,
            'title': section_title.strip() or f'Tweet {post_number}',
            'day': day,
            'content': f"## {section_title}\n{section_content}" if section_title else section_content,
            'type': post_type,
            'day_hint': f'{day.title()} {time_hint}' if time_hint else day.title(),
            'filename_hint': filename_hint,
            'time_of_day': time_of_day,
        })

    return posts


def _split_by_h2_headers(content: str) -> List[Tuple[str, str]]:
    """Split content by ## headers, returning (title, content) pairs."""
    sections = []
    lines = content.split('\n')
    current_title = ''
    current_lines = []

    for line in lines:
        if line.strip().startswith('## '):
            # Save previous section
            if current_title or current_lines:
                sections.append((current_title, '\n'.join(current_lines)))
            current_title = line.strip()[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Last section
    if current_title or current_lines:
        sections.append((current_title, '\n'.join(current_lines)))

    # Filter out empty sections and preamble (sections before the first ## header have no title)
    return [(t, c) for t, c in sections if t and c.strip()]


def _split_by_separator(content: str) -> List[Tuple[str, str]]:
    """Split content by --- separators as fallback."""
    parts = re.split(r'\n---+\n', content)
    sections = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        # Try to extract a title from the first line
        first_line = part.split('\n')[0].strip()
        if first_line.startswith('#'):
            title = first_line.lstrip('#').strip()
            body = '\n'.join(part.split('\n')[1:])
        else:
            title = f'Post {i + 1}'
            body = part
        sections.append((title, body))
    return sections


def _extract_day_from_title(title: str) -> Optional[str]:
    """Extract day name from section title (English or Chinese)."""
    title_lower = title.lower()

    # English day names
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        if day in title_lower:
            return day

    # Chinese day names
    for cn_day, en_day in CHINESE_DAY_MAPPING.items():
        if cn_day in title:
            return en_day

    return None


def _extract_filename_hint(title: str) -> Optional[str]:
    """Extract a suggested filename from section title like '星期一 | Monday_Morning_Tweet.md'."""
    # Pattern: anything | filename.md
    match = re.search(r'\|\s*(\S+\.md)', title)
    if match:
        return match.group(1).replace('.md', '')

    # Pattern: **File:** filename.md
    match = re.search(r'\*\*File:\*\*\s*(\S+\.md)', title, re.IGNORECASE)
    if match:
        return match.group(1).replace('.md', '')

    return None


def _parse_substack_content(content: str) -> List[Dict]:
    """Parse Substack content - typically a single article."""
    # Substack is usually one article, extract title and create single post
    title_match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "Weekly Article"

    # Look for subject line
    subject_match = re.search(r'\d+\.\s*(.+?)$', content, re.MULTILINE)
    if subject_match:
        title = subject_match.group(1).strip()

    return [{
        'number': 1,
        'title': title,
        'day': 'sunday',
        'content': content,
        'type': 'article',
        'day_hint': 'Sunday'
    }]


def _parse_thread_content(content: str) -> List[Dict]:
    """Parse Thread/Threads content."""
    posts = []

    # Try Day-based format first: ## Day N (DayName) - Title
    day_pattern = r'^##\s+Day\s+(\d+)\s*\(([^)]+)\)\s*[-–:]\s*(.+?)$'
    lines = content.split('\n')
    current_post = None

    for i, line in enumerate(lines):
        match = re.match(day_pattern, line.strip(), re.IGNORECASE)
        if match:
            # Save previous post
            if current_post:
                posts.append(current_post)

            day_num = int(match.group(1))
            day_name = match.group(2).strip().lower()
            title = match.group(3).strip()

            current_post = {
                'number': day_num,
                'title': title,
                'day': day_name,
                'content': line + '\n',
                'type': 'post',
                'day_hint': f'Day {day_num} ({day_name.title()})'
            }
        elif current_post:
            # Check if we hit next ## section (not ###)
            if line.strip().startswith('## ') and not line.strip().startswith('### '):
                # Might be a new day, let pattern handle it
                pass
            current_post['content'] += line + '\n'

    # Don't forget last post
    if current_post:
        posts.append(current_post)

    if posts:
        return posts

    # Try standard parsing if Day format didn't work
    posts = _parse_standard_content(content, 'thread')

    # If no posts found, try alternative patterns
    if not posts:
        # Look for numbered posts like "1.", "2."
        post_pattern = r'^(\d+)\.\s+(.+?)(?=^\d+\.|$)'
        matches = re.findall(post_pattern, content, re.MULTILINE | re.DOTALL)

        for num_str, post_content in matches:
            posts.append({
                'number': int(num_str),
                'title': f'Thread Post {num_str}',
                'day': 'monday' if int(num_str) % 2 == 1 else 'wednesday',
                'content': post_content.strip(),
                'type': 'post',
                'day_hint': None
            })

    # If still no posts, create single post from entire content
    if not posts and content.strip():
        posts.append({
            'number': 1,
            'title': 'Thread Post',
            'day': 'monday',
            'content': content,
            'type': 'post',
            'day_hint': None
        })

    return posts


def _parse_standard_content(content: str, platform_key: str) -> List[Dict]:
    """
    Parse standard content format using flexible ## header splitting.

    Handles:
    - ## Post 1 (Monday/Tuesday) - Title
    - ## Monday Morning Post - Title
    - ## Post 1 - Title
    - ## 1. Title
    - --- separated sections
    """
    # Use the generic header splitter
    sections = _split_by_h2_headers(content)

    if not sections:
        sections = _split_by_separator(content)

    if not sections:
        return []

    posts = []
    config = PLATFORM_CONFIG.get(platform_key, PLATFORM_CONFIG.get('linkedin', {}))
    post_number = 0

    for section_title, section_content in sections:
        if not section_content.strip():
            continue
        # Skip image prompt sections
        if re.match(r'image\s*prompt', section_title, re.IGNORECASE):
            continue

        post_number += 1

        # Extract day from title
        day = _extract_day_from_title(section_title)
        if not day:
            day = config.get('day_mapping', DAY_MAPPING).get(post_number, 'monday')

        # Extract filename hint
        filename_hint = _extract_filename_hint(section_title)
        # Also check in content for **File:** pattern
        if not filename_hint:
            file_match = re.search(r'\*\*File:\*\*\s*(\S+\.md)', section_content, re.IGNORECASE)
            if file_match:
                filename_hint = file_match.group(1).replace('.md', '')

        # Extract posting time
        time_hint = None
        for tp in [r'\*\*Posting Time:\*\*\s*(.+?)(?:\n|$)',
                    r'\*\*发布时间[:：]\*\*\s*(.+?)(?:\n|$)']:
            tm = re.search(tp, section_content, re.IGNORECASE)
            if tm:
                time_hint = tm.group(1).strip()
                break

        # Determine time of day
        time_of_day = 'morning'
        if time_hint:
            if any(x in time_hint.lower() for x in ['afternoon', 'pm', '14', '15', '16', '下午']):
                time_of_day = 'afternoon'
            elif any(x in time_hint.lower() for x in ['evening', '19', '20', '21', '晚']):
                time_of_day = 'evening'

        # Determine post type from title
        title_lower = section_title.lower()
        if 'carousel' in title_lower:
            post_type = 'carousel'
        elif 'thread' in title_lower:
            post_type = 'thread'
        elif 'quote' in title_lower or 'story' in title_lower or 'testimonial' in title_lower:
            post_type = 'quote'
        elif 'behind' in title_lower or 'bts' in title_lower:
            post_type = 'behind_the_scenes'
        elif 'tip' in title_lower:
            post_type = 'tips'
        elif 'article' in title_lower:
            post_type = 'article'
        else:
            post_type = config.get('default_type', 'post')

        posts.append({
            'number': post_number,
            'title': section_title.strip(),
            'day': day,
            'content': f"## {section_title}\n{section_content}" if section_title else section_content,
            'type': post_type,
            'day_hint': f'{day.title()} {time_hint}' if time_hint else day.title(),
            'filename_hint': filename_hint,
            'time_of_day': time_of_day,
        })

    return posts


def generate_post_filename(post: Dict, platform_key: str) -> str:
    """
    Generate a filename for an individual post.

    Args:
        post: Post dictionary from parse_content_file
        platform_key: Platform identifier

    Returns:
        Filename like '01_monday_educational_carousel' or 'monday_morning_tweet'
    """
    # Use filename hint from AI if available (e.g., "Monday_Morning_Tweet")
    filename_hint = post.get('filename_hint')
    if filename_hint:
        # Sanitize the hint
        filename = filename_hint.lower()
        filename = re.sub(r'[^a-z0-9_\-]', '_', filename)
        filename = re.sub(r'_+', '_', filename).strip('_')
        if filename:
            return f"{post['number']:02d}_{filename}"

    # Format: NN_day_timeofday_type
    num_str = f"{post['number']:02d}"
    day = post['day']
    time_of_day = post.get('time_of_day', 'morning')

    # Use post type as suffix
    post_type = post.get('type', 'post')

    return f"{num_str}_{day}_{time_of_day}_{post_type}"


def create_individual_post_files(
    content_path: Path,
    platform_key: str,
    output_dir: Optional[Path] = None
) -> List[Path]:
    """
    Parse a content file and create individual post files.

    Args:
        content_path: Path to the *_content.md file
        platform_key: Platform identifier
        output_dir: Directory to save files (defaults to same as content_path)

    Returns:
        List of created file paths
    """
    if output_dir is None:
        output_dir = content_path.parent

    posts = parse_content_file(content_path, platform_key)

    if not posts:
        print(f"[ContentParser] No posts found in {content_path}")
        return []

    created_files = []

    for post in posts:
        filename = generate_post_filename(post, platform_key)
        filepath = output_dir / f"{filename}.md"

        # Create post header
        header = f"""# {platform_key.title()} Post {post['number']} - {post['day'].title()} {post['type'].replace('_', ' ').title()}
**Post Type:** {post['type'].replace('_', ' ').title()}
**Theme:** {post['title']}
**Day:** {post['day'].title()}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

"""
        # Write the file
        full_content = header + post['content']
        filepath.write_text(full_content, encoding='utf-8')
        created_files.append(filepath)

        print(f"[ContentParser] Created: {filepath.name}")

    return created_files


def process_platform_content(platform_output_dir: Path, platform_key: str) -> Dict:
    """
    Process a platform's output directory to create individual post files.

    This is the main entry point after content generation.

    Args:
        platform_output_dir: Directory containing *_content.md
        platform_key: Platform identifier

    Returns:
        Result dictionary with success status and created files
    """
    content_file = platform_output_dir / f"{platform_key}_content.md"

    result = {
        'success': False,
        'content_file': str(content_file),
        'created_files': [],
        'post_count': 0,
        'error': None
    }

    if not content_file.exists():
        result['error'] = f"Content file not found: {content_file}"
        return result

    try:
        created_files = create_individual_post_files(
            content_file,
            platform_key,
            platform_output_dir
        )

        result['success'] = len(created_files) > 0
        result['created_files'] = [str(f) for f in created_files]
        result['post_count'] = len(created_files)

        if not created_files:
            result['error'] = "No posts could be extracted from content file"

    except Exception as e:
        result['error'] = str(e)

    return result


def process_all_platforms(week_output_dir: Path) -> Dict[str, Dict]:
    """
    Process all platforms in a week's output directory.

    Args:
        week_output_dir: Week output directory (e.g., output/2026-01-19_week4)

    Returns:
        Dictionary with results per platform
    """
    from postall.config import get_platforms

    results = {}

    for platform_key, platform_info in get_platforms().items():
        folder_name = platform_info.get('output_folder', platform_key)
        platform_dir = week_output_dir / folder_name

        if platform_dir.exists():
            results[platform_key] = process_platform_content(platform_dir, platform_key)
        else:
            results[platform_key] = {
                'success': False,
                'error': f"Platform directory not found: {platform_dir}"
            }

    return results


# Expected minimum post counts per platform (per week)
EXPECTED_POST_COUNTS = {
    'instagram': 4,    # 3-4 posts/week
    'twitter': 14,     # 14 tweets/week (2/day)
    'linkedin': 4,     # 3-5 posts/week
    'thread': 7,       # 7 posts/week (1/day)
    'pinterest': 7,    # 7-14 pins/week
    'reddit': 2,       # 1-2 posts/week
    'substack': 3,     # 3 posts/week (Sunday article + Wednesday deep dive + Friday tips)
}


def validate_content_generation(week_output_dir: Path) -> Dict[str, Dict]:
    """
    Validate that content generation meets expected post counts.

    Args:
        week_output_dir: Week output directory

    Returns:
        Dictionary with validation results per platform:
        {
            'platform': {
                'expected': int,
                'actual': int,
                'status': 'ok' | 'warning' | 'missing',
                'message': str
            }
        }
    """
    from postall.config import get_platforms

    results = {}

    for platform_key, platform_info in get_platforms().items():
        folder_name = platform_info.get('output_folder', platform_key)
        platform_dir = week_output_dir / folder_name
        expected = EXPECTED_POST_COUNTS.get(platform_key, 1)

        if not platform_dir.exists():
            results[platform_key] = {
                'expected': expected,
                'actual': 0,
                'status': 'missing',
                'message': f"Platform folder missing: {folder_name}"
            }
            continue

        # Count posts from content file
        content_file = platform_dir / f"{platform_key}_content.md"
        if content_file.exists():
            posts = parse_content_file(content_file, platform_key)
            actual = len(posts)
        else:
            # Count individual post files
            individual_files = [f for f in platform_dir.glob("*.md")
                               if not f.name.endswith('_content.md')
                               and not f.name.startswith('README')]
            actual = len(individual_files)

        if actual >= expected:
            status = 'ok'
            message = f"✓ {actual}/{expected} posts"
        elif actual > 0:
            status = 'warning'
            message = f"⚠ Only {actual}/{expected} posts generated (missing {expected - actual})"
        else:
            status = 'missing'
            message = f"✗ No posts found (expected {expected})"

        results[platform_key] = {
            'expected': expected,
            'actual': actual,
            'status': status,
            'message': message
        }

    return results


def get_content_validation_summary(validation_results: Dict[str, Dict]) -> str:
    """
    Generate a summary of content validation results.

    Args:
        validation_results: Results from validate_content_generation

    Returns:
        Formatted summary string
    """
    lines = ["## Content Generation Validation\n"]

    total_expected = 0
    total_actual = 0
    warnings = []

    for platform, result in validation_results.items():
        total_expected += result['expected']
        total_actual += result['actual']

        if result['status'] == 'warning':
            warnings.append(f"- {platform}: {result['message']}")
        elif result['status'] == 'missing':
            warnings.append(f"- {platform}: {result['message']}")

    lines.append(f"**Total Posts:** {total_actual}/{total_expected}")

    if total_actual >= total_expected:
        lines.append("\n✓ All platforms meet expected post counts.\n")
    else:
        lines.append(f"\n⚠ **Warning:** {total_expected - total_actual} posts missing:\n")
        lines.extend(warnings)
        lines.append("\n**Recommendation:** Regenerate content for platforms with warnings.\n")

    return '\n'.join(lines)
