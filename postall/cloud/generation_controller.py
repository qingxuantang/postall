"""
Generation Controller for PostAll Cloud

Pipeline: Text → Review → Per-Post Retry → Images (approved only) → Schedule

Handles automated weekly content generation:
- Generate text content for all platforms (NO images yet)
- Director reviews each post
- Per-post retry loop for failed posts (2 rounds + fresh start 2 rounds)
- Generate images ONLY for approved posts
- Escalate remaining failures to human via Telegram

Usage:
    controller = GenerationController()
    result = await controller.generate_weekly_content()
"""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from zoneinfo import ZoneInfo

from postall.config import (
    TIMEZONE, OUTPUT_DIR, PROJECT_ROOT,
    get_next_week_folder_name, get_platforms,
    get_brand_name, get_brand_style, get_brand_tagline,
    get_brand_website, get_content_pillars, get_enabled_platforms,
    get_platform_language
)


class GenerationController:
    """
    Controls weekly content generation with existence checking.

    Features:
    - Check if next week's content exists
    - Generate only missing platform content
    - Run Director review after generation
    - Auto-regenerate low-scoring content (up to max_retries)
    - Report generation results
    """

    # Per-post retry settings
    POST_REGEN_MAX_ROUNDS = 2    # Max regen rounds before fresh start (and max fresh start rounds)
    POST_APPROVAL_THRESHOLD = 8.0  # Per-post score threshold (approve_with_notes = 8.0)

    # Legacy bulk settings (kept for regenerate_platform from Telegram buttons)
    AUTO_REGEN_MIN_SCORE = 7.0
    AUTO_REGEN_MAX_RETRIES = 2

    def __init__(self):
        """Initialize the generation controller."""
        self.timezone = ZoneInfo(TIMEZONE)
        self.output_dir = OUTPUT_DIR

        # Only enabled platforms to generate (call get_platforms() at runtime,
        # not the module-level PLATFORMS import, to reflect apply_project_config() changes)
        self.all_platforms = [k for k, v in get_platforms().items() if v.get('enabled', False)]

        # AI executor preference (Claude API preferred for server)
        self.use_claude_api = os.getenv('ANTHROPIC_API_KEY', '') != ''
        self.use_gemini_api = os.getenv('GEMINI_API_KEY', '') != ''

    def check_content_status(self) -> Dict[str, Any]:
        """
        Check the status of next week's content.

        Returns:
            Dict with:
            - exists: bool - True if all content exists
            - partial: bool - True if some content exists
            - missing_platforms: List[str] - platforms missing content
            - existing_platforms: List[str] - platforms with content
            - week_folder: str - next week's folder name
            - details: Dict - per-platform details
        """
        week_folder = get_next_week_folder_name()
        week_path = self.output_dir / week_folder

        result = {
            'exists': False,
            'partial': False,
            'missing_platforms': [],
            'existing_platforms': [],
            'week_folder': week_folder,
            'week_path': str(week_path),
            'details': {}
        }

        # Check if week folder exists
        if not week_path.exists():
            result['missing_platforms'] = self.all_platforms.copy()
            return result

        # Check each platform
        for platform_key, platform_info in get_platforms().items():
            folder_name = platform_info.get('output_folder', platform_key)
            platform_path = week_path / folder_name

            platform_status = {
                'exists': False,
                'post_count': 0,
                'has_schedule': False,
                'posts': []
            }

            if platform_path.exists() and platform_path.is_dir():
                # Count markdown files (posts)
                posts = list(platform_path.glob('*.md'))
                platform_status['post_count'] = len(posts)
                platform_status['posts'] = [p.name for p in posts]
                platform_status['exists'] = len(posts) > 0

            result['details'][platform_key] = platform_status

            if platform_status['exists']:
                result['existing_platforms'].append(platform_key)
            else:
                result['missing_platforms'].append(platform_key)

        # Check for schedule.json
        schedule_file = week_path / 'schedule.json'
        result['has_schedule'] = schedule_file.exists()

        # Determine overall status
        result['exists'] = len(result['missing_platforms']) == 0
        result['partial'] = len(result['existing_platforms']) > 0 and len(result['missing_platforms']) > 0

        return result

    async def generate_weekly_content(
        self,
        force: bool = False,
        platforms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate weekly content with the pipeline:
        Text → Review → Per-Post Retry → Images (approved only) → Schedule

        Args:
            force: If True, regenerate all platforms even if content exists
            platforms: Specific platforms to generate (None = all missing)

        Returns:
            Dict with generation results
        """
        result = {
            'success': False,
            'week_folder': '',
            'platforms_generated': [],
            'platforms_skipped': [],
            'platforms_failed': [],
            'errors': [],
            'generation_time': None,
            'director_review_done': False,
            'auto_regen_attempts': 0,
            'posts_approved': 0,
            'posts_escalated': 0,
            'images_generated': 0,
        }

        start_time = datetime.now(self.timezone)

        # Check current status
        status = self.check_content_status()
        result['week_folder'] = status['week_folder']

        # Determine which platforms to generate
        if force:
            platforms_to_generate = platforms or self.all_platforms
            result['platforms_skipped'] = []
        else:
            if status['exists'] and not force:
                result['success'] = True
                result['platforms_skipped'] = status['existing_platforms']
                result['message'] = 'All content already exists. Skipping generation.'
                return result

            platforms_to_generate = platforms or status['missing_platforms']
            result['platforms_skipped'] = status['existing_platforms']

        if not platforms_to_generate:
            result['success'] = True
            result['message'] = 'No platforms to generate.'
            return result

        # ==========================================
        # PHASE 1: Generate TEXT content (no images)
        # ==========================================
        for platform in platforms_to_generate:
            try:
                print(f"[GenerationController] Generating text content for {platform}...")
                gen_result = await self._generate_platform_content(platform, status['week_folder'])

                if gen_result['success']:
                    result['platforms_generated'].append(platform)
                else:
                    result['platforms_failed'].append(platform)
                    result['errors'].append(f"{platform}: {gen_result.get('error', 'Unknown error')}")
            except Exception as e:
                result['platforms_failed'].append(platform)
                result['errors'].append(f"{platform}: {str(e)}")

        if not result['platforms_generated']:
            result['generation_time'] = str(datetime.now(self.timezone) - start_time)
            return result

        # ==========================================
        # PHASE 2: Create schedule.json
        # ==========================================
        try:
            print("[GenerationController] Creating schedule...")
            await self._create_schedule(status['week_folder'])
            result['schedule_created'] = True
        except Exception as e:
            result['errors'].append(f"Schedule creation: {str(e)}")
            result['schedule_created'] = False

        if not result.get('schedule_created', False):
            result['generation_time'] = str(datetime.now(self.timezone) - start_time)
            return result

        # ==========================================
        # PHASE 3: Director review
        # ==========================================
        try:
            print("[GenerationController] Running Director review...")
            review_result = await self._run_director_review(status['week_folder'])
            result['director_review_done'] = review_result.get('success', False)
            result['director_review_result'] = review_result
        except Exception as e:
            result['errors'].append(f"Director review: {str(e)}")
            result['generation_time'] = str(datetime.now(self.timezone) - start_time)
            return result

        if not review_result.get('success'):
            result['generation_time'] = str(datetime.now(self.timezone) - start_time)
            return result

        # ==========================================
        # PHASE 4: Per-post retry loop
        # ==========================================
        total_regen_attempts = 0
        try:
            total_regen_attempts = await self._per_post_retry_loop(
                status['week_folder'], review_result
            )
            result['auto_regen_attempts'] = total_regen_attempts

            # Re-run full review to get final state after all retries
            if total_regen_attempts > 0:
                print("[GenerationController] Re-running final Director review after retries...")
                await self._create_schedule(status['week_folder'])
                review_result = await self._run_director_review(status['week_folder'])
                result['director_review_result'] = review_result
        except Exception as e:
            result['errors'].append(f"Per-post retry: {str(e)}")

        # Collect final approved/escalated counts
        final_decisions = result.get('director_review_result', {}).get('decisions', {})
        result['posts_approved'] = final_decisions.get('approve', 0) + final_decisions.get('approve_with_notes', 0)
        result['posts_escalated'] = (
            final_decisions.get('escalate', 0)
            + final_decisions.get('revise', 0)
            + final_decisions.get('reject', 0)
        )

        # ==========================================
        # PHASE 5: Generate images ONLY for approved posts
        # ==========================================
        approved_posts = result.get('director_review_result', {}).get('ready_to_schedule', [])
        if approved_posts:
            try:
                print(f"[GenerationController] Generating images for {len(approved_posts)} approved posts...")
                img_result = await self._generate_images_for_approved_posts(
                    status['week_folder'], approved_posts
                )
                result['images_generated'] = img_result.get('generated', 0)
                if img_result.get('error'):
                    result['errors'].append(f"Image generation: {img_result['error']}")
            except Exception as e:
                result['errors'].append(f"Image generation: {str(e)}")
        else:
            print("[GenerationController] No approved posts — skipping image generation")

        # Calculate generation time
        end_time = datetime.now(self.timezone)
        result['generation_time'] = str(end_time - start_time)

        # Determine overall success
        result['success'] = len(result['platforms_generated']) > 0 or status['exists']

        return result

    async def _per_post_retry_loop(
        self,
        week_folder: str,
        review_result: Dict[str, Any]
    ) -> int:
        """
        Per-post retry loop for failed posts.

        For each failed post:
        1. Regenerate text (up to 2 rounds)
        2. If still failing: fresh start for that slot (up to 2 more rounds)
        3. If still failing: leave as-is for human escalation

        Args:
            week_folder: Week folder name
            review_result: Director review result

        Returns:
            Total number of regeneration attempts made
        """
        week_path = self.output_dir / week_folder
        total_attempts = 0

        # Collect failed posts from review
        failed_posts = []
        for rev in review_result.get('review', {}).get('reviews', []):
            if rev.get('decision') in ('escalate', 'revise', 'reject'):
                failed_posts.append(rev)

        if not failed_posts:
            return 0

        print(f"[GenerationController] {len(failed_posts)} posts failed review — starting per-post retry")

        for post_review in failed_posts:
            post_path_str = post_review.get('post_path', '')
            platform = post_review.get('platform', '')
            score = post_review.get('score', 0)

            # Resolve the full path
            post_path = Path(post_path_str)
            if not post_path.is_absolute():
                # post_path might be relative like "output/2026.../x-tweets/02_xxx.md"
                # or just "x-tweets/02_xxx.md"
                if post_path_str.startswith('output/'):
                    # Strip leading "output/" and week_folder
                    parts = post_path_str.split('/')
                    # Find the platform folder part
                    rel = '/'.join(parts[2:]) if len(parts) > 2 else post_path_str
                    post_path = week_path / rel
                else:
                    post_path = week_path / post_path_str

            if not post_path.exists():
                print(f"[GenerationController]   Skipping {post_path.name} — file not found")
                continue

            post_name = post_path.name
            print(f"[GenerationController]   Retrying {post_name} (score: {score:.1f}, platform: {platform})")

            passed = False

            # Round 1-2: Regenerate text with revision feedback
            for attempt in range(1, self.POST_REGEN_MAX_ROUNDS + 1):
                total_attempts += 1
                feedback = post_review.get('feedback', '')
                revision_notes = post_review.get('revision_notes', '')
                print(f"[GenerationController]     Round {attempt}/{self.POST_REGEN_MAX_ROUNDS} (regen with feedback)...")

                new_review = await self._regenerate_single_post(
                    post_path, platform, week_folder,
                    feedback=f"{feedback}\n{revision_notes}".strip(),
                    fresh_start=False
                )
                if new_review and new_review.get('score', 0) >= self.POST_APPROVAL_THRESHOLD:
                    print(f"[GenerationController]     Passed! Score: {new_review['score']:.1f}")
                    passed = True
                    break
                elif new_review:
                    score = new_review.get('score', 0)
                    post_review = new_review  # Update feedback for next round
                    print(f"[GenerationController]     Still failing. Score: {score:.1f}")

            # Round 3-4: Fresh start (completely new content for this slot)
            if not passed:
                print(f"[GenerationController]     Starting fresh for {post_name}...")
                for attempt in range(1, self.POST_REGEN_MAX_ROUNDS + 1):
                    total_attempts += 1
                    print(f"[GenerationController]     Fresh round {attempt}/{self.POST_REGEN_MAX_ROUNDS}...")

                    new_review = await self._regenerate_single_post(
                        post_path, platform, week_folder,
                        feedback="",
                        fresh_start=True
                    )
                    if new_review and new_review.get('score', 0) >= self.POST_APPROVAL_THRESHOLD:
                        print(f"[GenerationController]     Passed! Score: {new_review['score']:.1f}")
                        passed = True
                        break
                    elif new_review:
                        score = new_review.get('score', 0)
                        post_review = new_review
                        print(f"[GenerationController]     Still failing. Score: {score:.1f}")

            if not passed:
                print(f"[GenerationController]     {post_name} FAILED after all retries — escalating to human")

        return total_attempts

    async def _regenerate_single_post(
        self,
        post_path: Path,
        platform: str,
        week_folder: str,
        feedback: str = "",
        fresh_start: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Regenerate text for a single post and re-review it.

        Args:
            post_path: Path to the post file to regenerate
            platform: Platform key
            week_folder: Week folder name
            feedback: Director feedback to improve upon (empty for fresh start)
            fresh_start: If True, generate completely new content without old context

        Returns:
            Review result dict with 'score' and 'decision', or None on failure
        """
        try:
            # Read existing post to extract metadata
            old_content = post_path.read_text(encoding="utf-8")

            # Extract metadata from the post header
            day_match = re.search(r'\*\*Day:\*\*\s*(\w+)', old_content)
            type_match = re.search(r'\*\*Post Type:\*\*\s*(.+)', old_content)
            theme_match = re.search(r'\*\*Theme:\*\*\s*(.+)', old_content)
            pillar_match = re.search(r'\*\*Content Pillar:\*\*\s*(.+)', old_content)

            day = day_match.group(1).strip() if day_match else "Monday"
            post_type = type_match.group(1).strip() if type_match else "post"
            theme = theme_match.group(1).strip() if theme_match else ""
            pillar = pillar_match.group(1).strip() if pillar_match else ""

            # Build platform info
            platform_info = get_platforms().get(platform, {})
            platform_name = platform_info.get('name', platform)
            platform_language = get_platform_language(platform)
            brand_name = get_brand_name()
            brand_style = get_brand_style()
            brand_tagline = get_brand_tagline()

            # Language instruction
            if platform_language == "zh":
                lang_instruction = "Write ALL content in Chinese (中文)."
            elif platform_language == "en":
                lang_instruction = "Write ALL content in English."
            else:
                lang_instruction = ""

            # Platform constraints
            if platform == 'twitter':
                platform_constraint = (
                    "Twitter/X Thread Mode: Generate LONG-FORM content (600-2000 characters). "
                    "Write substantial, valuable content that will be split into a thread."
                )
            else:
                max_len = platform_info.get('max_length', platform_info.get('max_caption_length', 2000))
                platform_constraint = f"Max length: {max_len} characters."

            # Build the prompt
            if fresh_start:
                prompt = f"""Generate ONE fresh {platform_name} post for {brand_name}.

Brand: {brand_name} — {brand_style}
Tagline: {brand_tagline}
Platform: {platform_name}
Day: {day}
{f'Content Pillar: {pillar}' if pillar else ''}
{platform_constraint}
{lang_instruction}

Take a COMPLETELY DIFFERENT angle than typical content. Be creative and original.
The post must be high quality — scoring 8+/10 on brand voice, platform fit, quality, engagement, and factual accuracy.
Do NOT make unverifiable claims. Focus on genuine value and authentic voice.

Output format — write ONLY the post content in markdown:
## {day} Post - [Your Topic Title]
**Posting Time:** {day}, [optimal time]
**Content Pillar:** [pillar]

[Post content here — substantial, valuable, engaging]

### Image Prompt
[Detailed image generation instructions]
"""
            else:
                prompt = f"""Improve this {platform_name} post for {brand_name}. The previous version scored poorly.

Brand: {brand_name} — {brand_style}
Tagline: {brand_tagline}
Platform: {platform_name}
Day: {day}
{platform_constraint}
{lang_instruction}

Previous content that needs improvement:
---
{old_content[:2000]}
---

Director feedback:
{feedback}

Rewrite this post to address ALL the feedback. The post must score 8+/10.
Do NOT make unverifiable claims. Focus on genuine value and authentic voice.

Output format — write ONLY the improved post content in markdown:
## {day} Post - [Topic Title]
**Posting Time:** {day}, [optimal time]
**Content Pillar:** [pillar]

[Improved post content here]

### Image Prompt
[Detailed image generation instructions]
"""

            # Call AI executor
            content = await self._call_ai_for_text(prompt, platform_language)
            if not content:
                return None

            # Write the new content to the post file (overwrite)
            # Add the standard header
            header = f"""# {platform.title()} Post - {day} {post_type.replace('_', ' ').title()}
**Post Type:** {post_type}
**Theme:** {theme or 'Regenerated'}
**Day:** {day}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

"""
            post_path.write_text(header + content, encoding="utf-8")

            # Review the regenerated post
            from postall.director.director import ContentDirector
            director = ContentDirector()
            review = await asyncio.to_thread(
                director._review_single_post, post_path, platform
            )

            return {
                'score': review.score,
                'decision': review.decision.value,
                'feedback': review.feedback,
                'revision_notes': review.revision_notes,
                'post_path': str(post_path),
            }

        except Exception as e:
            print(f"[GenerationController]     Single post regen error: {e}")
            return None

    async def _call_ai_for_text(self, prompt: str, language: str = "") -> Optional[str]:
        """
        Call AI executor to generate text content (no file writing).

        Returns the generated text or None on failure.
        """
        # Try Claude API first
        if self.use_claude_api:
            try:
                import anthropic
                from postall.config import ANTHROPIC_API_KEY

                client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

                brand_name = get_brand_name()
                brand_style = get_brand_style()

                system_msg = (
                    f"You are a professional content creator for {brand_name}. "
                    f"Brand style: {brand_style}. "
                    f"Create high-quality, authentic content. Never fabricate statistics or claims."
                )

                response = await asyncio.to_thread(
                    lambda: client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=4096,
                        system=system_msg,
                        messages=[{"role": "user", "content": prompt}]
                    )
                )

                if response.content:
                    return response.content[0].text
            except Exception as e:
                print(f"[GenerationController] Claude API text call failed: {e}")

        # Fallback to Gemini
        if self.use_gemini_api:
            try:
                import google.generativeai as genai
                from postall.config import GEMINI_API_KEY

                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel("gemini-2.0-flash")

                response = await asyncio.to_thread(
                    lambda: model.generate_content(prompt)
                )

                if response and response.text:
                    return response.text
            except Exception as e:
                print(f"[GenerationController] Gemini text call failed: {e}")

        return None

    async def _generate_images_for_approved_posts(
        self,
        week_folder: str,
        approved_posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate images ONLY for posts that passed Director review.

        Args:
            week_folder: Week folder name
            approved_posts: List of approved review dicts with 'post_path'

        Returns:
            Dict with generation results
        """
        result = {'success': False, 'generated': 0, 'failed': 0, 'error': None}

        try:
            from postall.executors.gemini_image_executor import (
                extract_image_prompts_from_content,
                generate_image_with_gemini,
                check_image_exists
            )

            week_path = self.output_dir / week_folder
            total_generated = 0
            total_failed = 0

            for post_data in approved_posts:
                post_path_str = post_data.get('post_path', '')

                # Resolve path
                post_path = Path(post_path_str)
                if not post_path.is_absolute():
                    if post_path_str.startswith('output/'):
                        parts = post_path_str.split('/')
                        rel = '/'.join(parts[2:]) if len(parts) > 2 else post_path_str
                        post_path = week_path / rel
                    else:
                        post_path = week_path / post_path_str

                if not post_path.exists():
                    continue

                # Extract image prompts from this specific post
                prompts = extract_image_prompts_from_content(post_path)
                if not prompts:
                    continue

                # Determine asset folder
                base_name = post_path.stem
                prefix = base_name.split("_")[0]
                if prefix.isdigit():
                    asset_folder = post_path.parent / f"{prefix}_assets"
                else:
                    asset_folder = post_path.parent / f"{base_name}_assets"

                asset_folder.mkdir(parents=True, exist_ok=True)

                platform = post_data.get('platform', '')

                for img_prompt in prompts:
                    img_name = img_prompt.get('name', base_name)

                    # Skip if already exists
                    existing = check_image_exists(asset_folder, img_name)
                    if existing:
                        continue

                    try:
                        img_result = await asyncio.to_thread(
                            generate_image_with_gemini,
                            img_prompt['prompt'],
                            asset_folder,
                            img_name,
                            1080, 1080,  # width, height
                            "modern minimalist professional design",
                            platform
                        )
                        if img_result.get('success'):
                            total_generated += 1
                            print(f"[GenerationController]   Image: {img_name} ✓")
                        else:
                            total_failed += 1
                            print(f"[GenerationController]   Image: {img_name} ✗ {img_result.get('error', '')[:50]}")
                    except Exception as e:
                        total_failed += 1
                        print(f"[GenerationController]   Image error: {e}")

            result['success'] = total_generated > 0 or total_failed == 0
            result['generated'] = total_generated
            result['failed'] = total_failed

        except ImportError as e:
            result['error'] = f'Image executor not available: {e}'
        except Exception as e:
            result['error'] = str(e)

        return result

    async def _generate_platform_content(
        self,
        platform: str,
        week_folder: str
    ) -> Dict[str, Any]:
        """
        Generate content for a single platform by calling the AI executor directly.

        Uses the executor fallback chain: Claude API -> Gemini API
        """
        result = {'success': False, 'error': None}

        try:
            # Build generation prompt from brand config and platform info
            platform_info = get_platforms().get(platform, {})
            platform_name = platform_info.get('name', platform)
            brand_name = get_brand_name()
            brand_style = get_brand_style()
            brand_tagline = get_brand_tagline()
            brand_website = get_brand_website()
            content_pillars = get_content_pillars()

            # Get social links for CTA
            from postall.config import get_social_links_text
            social_links_text = get_social_links_text(platform)
            if social_links_text:
                cta_instruction = (
                    "\nCTA (Call-to-Action) Links - include at the end of each post:\n"
                    + social_links_text + "\n"
                    + "- Naturally weave these links into the closing CTA of each post. Vary the CTA phrasing across posts.\n"
                )
            else:
                cta_instruction = ""

            # Get platform language
            platform_language = get_platform_language(platform)

            # Format content pillars for prompt
            pillars_text = "\n".join(
                f"  - {pillar.replace('_', ' ').title()}: {weight}%"
                for pillar, weight in content_pillars.items()
            )

            # Language instruction for the prompt
            if platform_language == "zh":
                lang_instruction = "\n- Write ALL content in Chinese (中文)"
            elif platform_language == "en":
                lang_instruction = "\n- Write ALL content in English"
            else:
                lang_instruction = ""

            # Determine post count from platform config or default
            post_frequency = platform_info.get('post_frequency', 0)
            if post_frequency > 0:
                post_count_instruction = f"- Generate exactly {post_frequency} posts for the week"
            else:
                post_count_instruction = "- Generate 5-7 posts for the week (one per day, Monday through Sunday)"

            # Platform-specific content instructions
            if platform == 'twitter':
                platform_language = get_platform_language(platform)
                if platform_language == "zh":
                    platform_constraint = """- Twitter/X: Each post is a THREAD of 3-6 tweets
- Each tweet in the thread MUST be under 280 characters (Chinese characters count as 1)
- Clearly mark each tweet with 1/, 2/, 3/ numbering
- First tweet must be a strong hook that grabs attention
- Last tweet should include CTA
- Write ALL content in Chinese (中文). Do NOT mix languages.
- Use natural, conversational Chinese — not translated-from-English Chinese"""
                else:
                    platform_constraint = """- Twitter/X: Each post is a THREAD of 3-6 tweets
- Each tweet in the thread MUST be under 280 characters
- Clearly mark each tweet with 1/, 2/, 3/ numbering
- First tweet must be a strong hook that grabs attention
- Last tweet should include CTA
- Write ALL content in English. Do NOT mix languages."""
            elif platform == 'linkedin':
                platform_constraint = """- LinkedIn: Professional long-form posts (800-1500 characters)
- Write in a professional but authentic voice — share real experiences and insights
- Use line breaks for readability (LinkedIn rewards whitespace)
- Include a strong opening hook (first 2 lines are visible before "see more")
- End with a clear CTA or engagement question
- Do NOT fabricate statistics or unverifiable data — use personal observations instead"""
            elif platform == 'instagram':
                platform_constraint = """- Instagram: Visual-first carousel posts + single image posts
- Caption: 150-250 words, optimized for engagement
- Caption Formula: [Hook - 1 sentence that stops scrolling] → [Problem/insight] → [Value/solution] → [Personal story 2-3 sentences] → [CTA]
- Hashtags: 5-10 relevant hashtags, placed AFTER caption separated by dots
- Carousel Structure (7-10 slides):
  * Slide 1: Bold hook statement or question
  * Slides 2-7: One clear point per slide, scannable text
  * Slide 8-9: Summary or transformation
  * Slide 10: CTA (link in bio / follow for more)
- Content Mix per week:
  * 1-2 Educational carousels (tips, how-to, insights)
  * 1 Inspirational/quote post
  * 1 Behind-the-scenes or personal story
- Keep captions conversational and authentic — write like talking to a friend
- First line of caption is CRITICAL (visible before "more" button)
- Do NOT fabricate statistics or unverifiable data
- Use emoji sparingly but naturally (1-3 per caption)
- Each post MUST include ### Caption, **Hashtags:**, and ### Image Prompt sections

Output format per post:
### Caption:
[full caption text]

**Hashtags:** #tag1 #tag2 #tag3 ...

### Carousel Text:
**Slide 1:** [hook text]
**Slide 2:** [point 1]
...
**Slide N:** [CTA]

### Image Prompt
[image generation instructions per slide or single image]"""
            elif platform == 'reddit':
                platform_constraint = """- Reddit: Value-first long-form posts for relevant subreddits
- Write 300-800 words per post, helpful and informative tone
- NEVER be promotional — Reddit communities hate self-promotion
- Share genuine insights, tips, or experiences that happen to relate to the brand's domain
- Mention the product/tool only if it naturally fits (max 1 brief mention per post)
- Include the target subreddit in the post header
- Structure: Hook title → Problem/context → Detailed advice/insight → Subtle CTA if appropriate
- Write 1-2 posts per week targeting different subreddits
- Each post should stand alone as genuinely helpful content
- Do NOT fabricate statistics or unverifiable data"""
            else:
                max_len = platform_info.get('max_length', platform_info.get('max_caption_length', 'N/A'))
                platform_constraint = f"- Platform constraints: max length {max_len} characters"

            prompt = f"""Generate a week's worth of {platform_name} content for {brand_name}.

Brand Info:
  - Name: {brand_name}
  - Style/Voice: {brand_style}
  - Tagline: {brand_tagline}
  - Website: {brand_website}

Content Pillars (distribution targets):
{pillars_text}

Platform: {platform_name}
Week Folder: {week_folder}

CRITICAL RULES:
- Do NOT invent or fabricate statistics, research findings, or data points (e.g. "studies show 73% of developers..." or "saves 86 hours per month")
- Do NOT reference any specific product by name as a promotion (this is a creator channel, not a product page)
- Use only personal experiences, observations, and commonly known facts
- Instead of fake numbers, use qualitative descriptions (e.g. "significantly faster", "most developers I know", "in my experience")
- Keep content authentic — write as a real developer sharing genuine insights
- Each platform has strict format rules below — follow them exactly

GEO (Generative Engine Optimization) RULES — optimize content for AI discovery and citation:
- **Problem Sniper**: Each post must target ONE specific problem or question real users search for. Open with a clear problem statement and deliver a concise solution within the first 150 words. Think "how to...", "why does...", "best way to..." queries.
- **Structured Data for AI**: Use comparison lists, step-by-step instructions, numbered checklists, and parameter tables whenever possible. AI models (Gemini, ChatGPT, Perplexity) prefer structured, extractable content over vague prose.
- **Authoritative Tone with Citations**: Reference concrete personal experience, real tools, or verifiable methods. When mentioning techniques, name the specific approach (e.g., "the 4To1 Method™" not "a planning method"). This helps AI identify and cite the source.
- **Cross-Platform Trust Signals**: Content should naturally reference or link to other platforms where the brand has presence (website, YouTube, LinkedIn, etc.). This builds a cross-platform authority footprint that AI engines recognize.
- **Question-First Titles**: Use specific question-based or problem-based titles (e.g., "Why Most Planners Fail After Week 2" not "Planning Tips"). These match the long-tail queries AI engines serve answers for.
- **Front-Load Value**: The first 2-3 sentences must contain the core insight or answer. AI extracts snippets from the beginning — don't bury the lead with storytelling intros.
- **BALANCE: Human Voice over Robot Lists**: GEO does NOT mean turning every post into bullet-point lists. Wrap structured insights inside personal stories, conversational tone, and real experiences. AI can extract structure from natural prose — you don't need to format like a wiki page. A post that reads like a human sharing genuine experience but happens to contain clear, extractable insights is the sweet spot. Avoid formulaic "X reasons why..." or "Step 1, Step 2, Step 3" unless the platform specifically calls for it (e.g., Instagram carousel slides). On Twitter and LinkedIn, conversational storytelling with embedded structure beats naked checklists every time.

Requirements:
{post_count_instruction}
- Each post MUST be a separate ## section (level-2 markdown header)
- Use day names in section headers (e.g., ## Monday Morning Post - Topic Title)
- Include **Posting Time:** inside each section for optimal engagement
- Include ### Image Prompt subsection with detailed image generation instructions following this STYLE GUIDE:
  * Hand-drawn illustration, watercolor, or paper-craft aesthetic — NOT photorealistic, NOT glossy 3D
  * Warm color palette: orange, cream, coral, watercolor red-blue gradients
  * Typography-heavy: bold text as the focal visual element — ENGLISH TEXT ONLY in images (AI cannot render Chinese characters correctly)
  * Textured feel: hand-lettering, stamp prints, paper-cut art, or ink brush strokes
  * Minimalist composition with flat hand-drawn icons if needed
  * Should feel human-made and artistic, anti-AI aesthetic
  * If including text/branding in the image, use the EXACT brand name "YOUR_BRAND_NAME" — NEVER use "Your Brand" or generic placeholders
  * Keep image prompt simple and topic-focused — describe the visual scene, not marketing copy
- Use the content pillar distribution as a guide for topic selection
{platform_constraint}{lang_instruction}
{cta_instruction}
Output Format:
Each post as a separate ## section. Example:
## Monday Morning Post - Topic Title
**Posting Time:** Monday, 9:00 AM
**Content Pillar:** Product Education

[Post content here]

### Image Prompt
[Detailed image generation instructions here]

---
"""

            # Prepare output path
            week_path = self.output_dir / week_folder
            folder_name = platform_info.get('output_folder', platform)
            platform_output = week_path / folder_name
            platform_output.mkdir(parents=True, exist_ok=True)

            # Try Claude API first
            if self.use_claude_api:
                try:
                    from postall.executors.claude_api_executor import execute_with_claude_api
                    gen_result = await asyncio.to_thread(
                        execute_with_claude_api,
                        prompt,
                        platform_output,
                        platform,
                        platform_language
                    )
                    if gen_result.get('success'):
                        result['success'] = True
                        result['output'] = gen_result.get('output', '')[:500]
                        result['executor'] = 'claude_api'
                        return result
                    else:
                        print(f"[GenerationController] Claude API failed for {platform}: {gen_result.get('error')}")
                except Exception as e:
                    print(f"[GenerationController] Claude API exception for {platform}: {e}")

            # Fallback to Gemini API
            if self.use_gemini_api:
                try:
                    from postall.executors.gemini_api_executor import execute_with_gemini_api
                    gen_result = await asyncio.to_thread(
                        execute_with_gemini_api,
                        prompt,
                        platform_output,
                        platform,
                        platform_language
                    )
                    if gen_result.get('success'):
                        result['success'] = True
                        result['output'] = gen_result.get('output', '')[:500]
                        result['executor'] = 'gemini_api'
                        return result
                    else:
                        result['error'] = f"Gemini API: {gen_result.get('error')}"
                except Exception as e:
                    result['error'] = f"Gemini API exception: {e}"

            if not result['success'] and not result['error']:
                result['error'] = 'No AI executor available (set ANTHROPIC_API_KEY or GEMINI_API_KEY)'

        except Exception as e:
            result['error'] = str(e)

        return result

    async def _generate_images(self, week_folder: str) -> Dict[str, Any]:
        """Generate images for the week's content by calling the image executor directly."""
        result = {'success': False, 'error': None}

        try:
            from postall.executors.gemini_image_executor import generate_all_images

            week_path = self.output_dir / week_folder

            if not week_path.exists():
                result['error'] = f'Week folder not found: {week_path}'
                return result

            def progress_callback(current, total, name, success):
                status = "OK" if success else "FAIL"
                print(f"[GenerationController] Image {current}/{total}: {name} [{status}]")

            img_result = await asyncio.to_thread(
                generate_all_images,
                week_path,
                progress_callback,
                True  # skip_existing
            )

            result['success'] = img_result.get('total_success', 0) > 0 or img_result.get('total_skipped', 0) > 0
            result['total'] = img_result.get('total_prompts', 0)
            result['generated'] = img_result.get('total_success', 0)
            result['skipped'] = img_result.get('total_skipped', 0)
            result['failed'] = img_result.get('total_failed', 0)

            if not result['success'] and img_result.get('total_failed', 0) > 0:
                result['error'] = f"All {img_result['total_failed']} image(s) failed"

        except ImportError as e:
            result['error'] = f'Image executor not available: {e}'
        except Exception as e:
            result['error'] = str(e)

        return result

    async def _create_schedule(self, week_folder: str) -> Dict[str, Any]:
        """Create schedule.json for the week's content by calling PostScheduler directly."""
        result = {'success': False, 'error': None}

        try:
            from postall.schedulers.post_scheduler import PostScheduler

            week_path = self.output_dir / week_folder

            if not week_path.exists():
                result['error'] = f'Week folder not found: {week_path}'
                return result

            scheduler = PostScheduler(week_folder=week_path)
            schedule_data = await asyncio.to_thread(
                scheduler.create_schedule,
                True  # force=True
            )

            if schedule_data.get('error'):
                result['error'] = schedule_data['error']
            else:
                result['success'] = True
                result['total_posts'] = schedule_data.get('stats', {}).get('total_posts', 0)
                result['platforms'] = schedule_data.get('stats', {}).get('platforms', [])

        except ImportError as e:
            result['error'] = f'PostScheduler not available: {e}'
        except Exception as e:
            result['error'] = str(e)

        return result

    async def _run_director_review(self, week_folder: str) -> Dict[str, Any]:
        """Run Content Director review on generated content directly."""
        result = {'success': False, 'error': None}

        try:
            from postall.director.director import ContentDirector

            week_path = self.output_dir / week_folder

            if not week_path.exists():
                result['error'] = f'Week folder not found: {week_path}'
                return result

            director = ContentDirector()
            review_result = await asyncio.to_thread(
                director.review_week_content,
                week_path,
                True  # auto_schedule=True
            )

            result['success'] = True
            result['review'] = review_result

            # Extract summary for easy access
            summary = review_result.get('summary', {})
            result['total_reviewed'] = summary.get('total_reviewed', 0)
            result['avg_score'] = summary.get('avg_score', 0)
            result['decisions'] = summary.get('decisions', {})
            result['escalations'] = review_result.get('escalations', [])
            result['ready_to_schedule'] = review_result.get('ready_to_schedule', [])

        except ImportError as e:
            result['error'] = f'ContentDirector not available: {e}'
        except Exception as e:
            result['error'] = str(e)

        return result

    async def regenerate_platform(
        self,
        platform: str,
        week_folder: str
    ) -> Dict[str, Any]:
        """
        Regenerate content for a single platform and re-run Director review.

        Used by the revision loop when posts are flagged for regeneration.

        Args:
            platform: Platform key to regenerate
            week_folder: Week folder name

        Returns:
            Dict with regeneration and review results
        """
        result = {
            'success': False,
            'platform': platform,
            'week_folder': week_folder,
            'errors': []
        }

        # Step 1: Regenerate content
        try:
            print(f"[GenerationController] Regenerating {platform} content...")
            gen_result = await self._generate_platform_content(platform, week_folder)
            result['generation'] = gen_result

            if not gen_result.get('success'):
                result['errors'].append(f"Generation failed: {gen_result.get('error')}")
                return result
        except Exception as e:
            result['errors'].append(f"Generation exception: {e}")
            return result

        # Step 2: Re-run Director review on the week
        try:
            print(f"[GenerationController] Re-running Director review...")
            review_result = await self._run_director_review(week_folder)
            result['director_review'] = review_result

            if review_result.get('success'):
                result['success'] = True
                result['escalations'] = review_result.get('escalations', [])
                result['avg_score'] = review_result.get('avg_score', 0)
            else:
                result['errors'].append(f"Review failed: {review_result.get('error')}")
        except Exception as e:
            result['errors'].append(f"Review exception: {e}")

        return result

    def get_status_summary(self) -> str:
        """Get a human-readable status summary."""
        status = self.check_content_status()

        lines = [
            f"Week: {status['week_folder']}",
            f"Status: {'Complete' if status['exists'] else 'Partial' if status['partial'] else 'Missing'}"
        ]

        if status['existing_platforms']:
            lines.append(f"Existing: {', '.join(status['existing_platforms'])}")

        if status['missing_platforms']:
            lines.append(f"Missing: {', '.join(status['missing_platforms'])}")

        return '\n'.join(lines)
