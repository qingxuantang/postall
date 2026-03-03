"""
Email Nurture Sequence Generator for PostAll

Based on Cleo Playbook methodology:
- Emails 1-3: Problem education (NO CTA)
- Emails 4-6: Solution preview (NO CTA)
- Emails 7-9: Success stories (NO CTA)
- Email 10: Launch (Direct CTA)

Added: v2.2 Strategy Enhancement (2026-01-13)
"""

import yaml
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from dateutil.tz import gettz as ZoneInfo

from postall.config import (
    TIMEZONE, PROMPTS_DIR, CONFIG_DIR,
    get_brand_name, get_brand_website
)


@dataclass
class EmailContent:
    """Represents a single email in the nurture sequence."""
    id: int
    phase: str
    subject: str
    body: str
    delay_days: int
    has_cta: bool
    key_point: str
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "phase": self.phase,
            "subject": self.subject,
            "body": self.body,
            "delay_days": self.delay_days,
            "has_cta": self.has_cta,
            "key_point": self.key_point,
            "generated_at": self.generated_at
        }

    def to_markdown(self) -> str:
        """Convert email to markdown format."""
        return f"""# Email {self.id}: {self.subject}

**Phase:** {self.phase}
**Send Day:** Day {self.delay_days} after signup
**Subject Line:** {self.subject}
**CTA:** {"Direct link to product" if self.has_cta else "None"}

---

{self.body}

---

**Key Point:** {self.key_point}
**Generated:** {self.generated_at}
"""


class EmailSequenceGenerator:
    """
    Generates email nurture sequences using AI.

    Follows the Cleo Playbook methodology:
    1. Problem Education (emails 1-3) - No CTA
    2. Solution Preview (emails 4-6) - No CTA
    3. Success Stories (emails 7-9) - No CTA
    4. Launch (email 10) - Direct CTA
    """

    def __init__(self, config_path: Path = None):
        """Initialize the email generator."""
        self.timezone = ZoneInfo(TIMEZONE)
        self.config = self._load_config(config_path)
        self.prompt_template = self._load_prompt_template()

    def _load_config(self, config_path: Path = None) -> Dict[str, Any]:
        """Load email sequence configuration."""
        if config_path and config_path.exists():
            return yaml.safe_load(config_path.read_text(encoding="utf-8"))

        default_path = CONFIG_DIR / "email_sequence.yaml"
        if default_path.exists():
            return yaml.safe_load(default_path.read_text(encoding="utf-8"))

        # Return default config with dynamic brand name
        brand_name = get_brand_name()
        return {
            "sequence_name": f"{brand_name} Launch Sequence",
            "total_emails": 10,
            "sending_cadence": "every_3_days",
            "emails": []
        }

    def _load_prompt_template(self) -> str:
        """Load email generation prompt template."""
        prompt_path = PROMPTS_DIR / "email_prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""

    def generate_sequence(self, sequence_type: str = "launch") -> List[EmailContent]:
        """
        Generate a complete email nurture sequence.

        Args:
            sequence_type: Type of sequence ("launch", "nurture", "weekly")

        Returns:
            List of EmailContent objects
        """
        emails: List[EmailContent] = []
        email_configs = self.config.get("emails", [])

        for email_config in email_configs:
            email = self._generate_single_email(email_config)
            emails.append(email)

        return emails

    def _generate_single_email(self, email_config: Dict[str, Any]) -> EmailContent:
        """Generate a single email based on configuration."""
        email_id = email_config.get("id", 1)
        phase = email_config.get("phase", "problem_education")
        subject_example = email_config.get("subject_example", "")
        key_point = email_config.get("key_point", "")
        delay_days = email_config.get("delay_days", 0)
        has_cta = email_config.get("cta", "none") != "none"

        # Build prompt for this email
        prompt = self._build_email_prompt(email_id, phase, subject_example, key_point)

        # Try to generate with AI
        body = self._generate_with_ai(prompt, phase, email_id)

        # If AI fails, use template
        if not body:
            body = self._generate_template_email(email_id, phase, key_point)

        return EmailContent(
            id=email_id,
            phase=phase,
            subject=subject_example,
            body=body,
            delay_days=delay_days,
            has_cta=has_cta,
            key_point=key_point,
            generated_at=datetime.now(self.timezone).isoformat()
        )

    def _build_email_prompt(self, email_id: int, phase: str, subject: str, key_point: str) -> str:
        """Build the AI prompt for generating an email."""
        brand_name = get_brand_name()
        brand_website = get_brand_website()
        shop_url = f"https://{brand_website}/shop" if brand_website else "[YOUR_SHOP_URL]"

        phase_instructions = {
            "problem_education": """
Generate an email that helps the reader recognize their planning problem.
- NO call-to-action
- End with a reflection question
- Make the problem relatable
- Share a personal story or insight
""",
            "solution_preview": f"""
Generate an email that introduces the {brand_name} methodology.
- NO call-to-action
- Explain the methodology, not the product
- Build on previous emails' problems
- Tease what's coming next
""",
            "success_stories": """
Generate an email with a transformation story.
- NO call-to-action
- Use a specific (but fictionalized) example
- Show before/after clearly
- End with a lesson for the reader
""",
            "launch": f"""
Generate a launch email with direct CTA.
- Include link to product: {shop_url}
- Keep it short and clear
- Mention early adopter benefit
- Reference what was taught in previous emails
"""
        }

        return f"""You are writing email {email_id} of a 10-email nurture sequence for {brand_name}.

## Email Details
- Phase: {phase}
- Subject Line: {subject}
- Key Point: {key_point}

## Phase Instructions
{phase_instructions.get(phase, "")}

## Tone
- Conversational, friendly
- First person ("I")
- Short paragraphs
- No marketing speak

## Output
Write ONLY the email body (no subject line, no headers).
The email should be 150-300 words.
Sign off with "— Mark"
"""

    def _generate_with_ai(self, prompt: str, phase: str, email_id: int) -> Optional[str]:
        """Try to generate email content with AI."""
        # Try Claude CLI
        try:
            from postall.executors.claude_cli_executor import execute_with_claude_cli
            response = execute_with_claude_cli(prompt, output_path=None, platform=None)
            if response.get("success") and response.get("content"):
                return response["content"]
        except Exception:
            pass

        # Try Claude API
        try:
            from postall.executors.claude_api_executor import execute_with_claude_api
            response = execute_with_claude_api(prompt)
            if response:
                return response
        except Exception:
            pass

        # Try Gemini API
        try:
            from postall.executors.gemini_api_executor import execute_with_gemini
            response = execute_with_gemini(prompt)
            if response:
                return response
        except Exception:
            pass

        return None

    def _generate_template_email(self, email_id: int, phase: str, key_point: str) -> str:
        """Generate template-based email when AI is unavailable."""
        brand_name = get_brand_name()
        brand_website = get_brand_website()
        shop_url = f"https://{brand_website}/shop" if brand_website else "[YOUR_SHOP_URL]"

        templates = {
            "problem_education": """I've been thinking about why so many planning systems fail.

Here's what I've noticed: {key_point}.

Most people don't realize this until they've wasted months—sometimes years—on the wrong approach.

What's the one planning habit you've tried that never stuck?

— Team""",

            "solution_preview": """Last time I talked about why most planning fails.

Here's what I discovered about {key_point}.

When you start thinking this way, everything changes. Tasks stop being random to-dos and become steps toward something meaningful.

I'll share more about how this connects in the next email.

— Team""",

            "success_stories": f"""I want to share a story about {{key_point}}.

Before discovering {brand_name}, they were scattered. Goals everywhere, progress nowhere.

After making one shift—starting with the big picture first—everything changed.

Not more goals. Fewer, but connected to something real.

What would that kind of clarity do for you?

— Team""",

            "launch": f"""The {brand_name} is live.

Get it here: {shop_url}

Everything we've talked about—the vision, the planning, the review process—it's all in one system now.

First 100 users get early adopter pricing.

— Team"""
        }

        template = templates.get(phase, templates["problem_education"])
        return template.format(key_point=key_point)

    def save_sequence(self, emails: List[EmailContent], output_dir: Path) -> Path:
        """
        Save generated email sequence to files.

        Args:
            emails: List of generated emails
            output_dir: Directory to save files

        Returns:
            Path to the output directory
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save individual emails
        for email in emails:
            filename = f"email_{email.id:02d}_{email.phase}.md"
            filepath = output_dir / filename
            filepath.write_text(email.to_markdown(), encoding="utf-8")

        # Save sequence summary
        summary = self._generate_sequence_summary(emails)
        summary_path = output_dir / "sequence_summary.md"
        summary_path.write_text(summary, encoding="utf-8")

        return output_dir

    def _generate_sequence_summary(self, emails: List[EmailContent]) -> str:
        """Generate a summary document for the email sequence."""
        lines = [
            "# Email Nurture Sequence Summary",
            "",
            f"**Generated:** {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Total Emails:** {len(emails)}",
            f"**Methodology:** Cleo Playbook",
            "",
            "## Sequence Overview",
            "",
            "| # | Day | Phase | Subject | CTA |",
            "|---|-----|-------|---------|-----|",
        ]

        for email in emails:
            cta = "Direct" if email.has_cta else "None"
            lines.append(f"| {email.id} | Day {email.delay_days} | {email.phase} | {email.subject[:40]}... | {cta} |")

        lines.extend([
            "",
            "## Phase Breakdown",
            "",
            "### Problem Education (Emails 1-3)",
            "- **Goal**: Help reader recognize their problem",
            "- **CTA**: None",
            "",
            "### Solution Preview (Emails 4-6)",
            "- **Goal**: Introduce methodology (not product)",
            "- **CTA**: None",
            "",
            "### Success Stories (Emails 7-9)",
            "- **Goal**: Show transformation through stories",
            "- **CTA**: None",
            "",
            "### Launch (Email 10)",
            "- **Goal**: Direct offer",
            "- **CTA**: Product link",
            "",
            "---",
            "",
            "*Generated by PostAll Email Sequence Generator*"
        ])

        return "\n".join(lines)
