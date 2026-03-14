---
name: postall
version: 1.0.0
description: AI-powered multi-platform social media content generation and publishing automation. Generate, review, and publish content across Twitter, LinkedIn, Instagram, Pinterest, Threads, and Xiaohongshu.
homepage: https://postall.live
repository: https://github.com/qingxuantang/postall
metadata:
  emoji: "📮"
  category: "content-automation"
  platforms: ["twitter", "linkedin", "instagram", "pinterest", "threads", "xiaohongshu", "wechat"]
  ai_providers: ["anthropic", "openai", "google"]
---

# PostAll - AI Agent Integration

AI-powered multi-platform content automation. Generate, review, and publish across all social platforms from a single configuration.

## Skill Files

| File | URL |
|------|-----|
| **SKILL.md** (this file) | `https://postall.live/skill.md` |
| **skill.json** (metadata) | `https://postall.live/skill.json` |

**Quick install for agents:**
```bash
curl -s https://postall.live/skill.md > ~/.postall/SKILL.md
curl -s https://postall.live/skill.json > ~/.postall/skill.json
```

---

## What PostAll Does

1. **Content Generation** - AI creates platform-optimized posts from your brand guidelines
2. **Director Review** - Second AI reviews for quality, brand alignment, factual accuracy
3. **Image Generation** - Auto-generate matching visuals with correct dimensions per platform
4. **Multi-Platform Publishing** - Publish to Twitter, LinkedIn, Instagram, Pinterest, Threads, Xiaohongshu
5. **RLHF Learning** - System improves from feedback over time
6. **Scheduling** - Optimal posting times per platform

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and setup
git clone https://github.com/qingxuantang/postall.git
cd postall
cp .env.example .env

# Configure API keys in .env
# ANTHROPIC_API_KEY=your_key (or OPENAI_API_KEY or GEMINI_API_KEY)

# Start
docker-compose up -d
```

### Option 2: Local Installation

```bash
git clone https://github.com/qingxuantang/postall.git
cd postall
pip install -e .
cp .env.example .env
# Edit .env with your API keys
```

---

## Core CLI Commands

All commands use the format: `python -m postall.cli <command> --project <path/to/project.yaml>`

### Generate Content

```bash
# Generate content for all platforms
python -m postall.cli generate --project projects/example/project.yaml

# Generate for specific platform
python -m postall.cli generate --project projects/example/project.yaml --platform twitter

# Generate with specific AI model
python -m postall.cli generate --project projects/example/project.yaml --model claude
```

### Publish Content

```bash
# Publish all pending content
python -m postall.cli publish --project projects/example/project.yaml

# Publish to specific platform
python -m postall.cli publish --project projects/example/project.yaml --platform linkedin
```

### Run as Daemon

```bash
# Continuous operation - auto generate and publish
python -m postall.cli daemon --project projects/example/project.yaml
```

### Check Status

```bash
# View system status
python -m postall.cli status --project projects/example/project.yaml

# Review generated content
python -m postall.cli review --project projects/example/project.yaml
```

---

## Docker Commands

```bash
# Start PostAll
docker-compose up -d

# View logs
docker-compose logs -f postall

# Stop
docker-compose down

# Restart
docker-compose restart

# Execute CLI inside container
docker exec postall python -m postall.cli status --project /app/projects/example/project.yaml
```

---

## Telegram Bot Integration

PostAll includes a Telegram bot for monitoring and control. Each project gets its own bot.

### Bot Commands (in Telegram)

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot |
| `/status` | View current system status |
| `/upcoming` | Posts scheduled for next 24 hours |
| `/schedule` | Today's posting schedule |
| `/stats` | Recent publishing statistics |
| `/generate` | Trigger content generation for next week |
| `/publish` | Manually trigger publishing |
| `/help` | Show all commands |

### Bot Menu Buttons

- **Upcoming** - View posts in the next 24 hours
- **Schedule** - Today's scheduled posts
- **Stats** - Publishing statistics by platform
- **Content Status** - Next week's content status
- **Generate** - Start content generation

### Setting Up Telegram Bot

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get your bot token
3. Add to `.env`:
   ```
   TELEGRAM_BOT_ENABLED=true
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

---

## Project Configuration

Create a `project.yaml` file to define your brand and content strategy:

```yaml
project_name: "My Brand"

brand:
  name: "My Brand"
  tagline: "Your Tagline"
  website: "mybrand.com"
  
  colors:
    primary: "#3498DB"
    secondary: "#2ECC71"
    accent: "#E74C3C"
  
  voice:
    tone: "professional yet friendly"
    characteristics:
      - "clear and concise"
      - "helpful and educational"
      - "trustworthy and authentic"
    avoid:
      - "aggressive sales language"
      - "overpromising or hype"
      - "technical jargon"

content_strategy:
  pillars:
    product_education: 35
    industry_insights: 25
    tips_productivity: 20
    customer_stories: 10
    behind_scenes: 5
    lead_magnet: 5
  
  themes:
    - "Getting Started"
    - "Best Practices"
    - "Common Mistakes"
    - "Success Stories"

platforms:
  twitter:
    enabled: true
    language: "en"
  linkedin:
    enabled: true
    language: "en"
  instagram:
    enabled: false
  pinterest:
    enabled: false

timezone: "America/Los_Angeles"

generation_schedule:
  day: "saturday"
  time: "09:00"

posting_times:
  twitter: ["08:00", "12:00", "18:00"]
  linkedin: ["07:30", "12:00"]
```

---

## Environment Variables

```bash
# AI Providers (at least one required)
ANTHROPIC_API_KEY=           # Claude API
OPENAI_API_KEY=              # GPT-4 API
GEMINI_API_KEY=              # Gemini API

# Twitter/X
TWITTER_ENABLED=true
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=

# LinkedIn
LINKEDIN_ENABLED=true
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_PERSON_URN=

# Instagram (Meta)
INSTAGRAM_ENABLED=false
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_ACCOUNT_ID=

# Pinterest
PINTEREST_ENABLED=false
PINTEREST_ACCESS_TOKEN=

# Telegram Bot
TELEGRAM_BOT_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## Content Generation Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Brand Config   │────▶│  AI Generation  │────▶│ Director Review │
│ (project.yaml)  │     │ (Claude/GPT/    │     │ (Quality Check) │
│                 │     │  Gemini)        │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Publishing    │◀────│  Human Review   │◀────│ Content Ready   │
│  (Platforms)    │     │   (Optional)    │     │   (Approved)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  RLHF Learning  │
                        │  (Improvement)  │
                        └─────────────────┘
```

---

## Director Review System

The Director is a second AI that reviews generated content for:

- **Brand Alignment** - Does it match your voice and tone?
- **Quality Standards** - Is it well-written and engaging?
- **Platform Fit** - Is it optimized for the target platform?
- **Factual Accuracy** - No fabricated statistics or claims
- **Compliance** - No problematic content

Posts receive a score. Low-scoring posts can be regenerated automatically.

---

## Supported Platforms

| Platform | Publishing | Image Support | Notes |
|----------|------------|---------------|-------|
| Twitter/X | ✅ | ✅ | Threads supported |
| LinkedIn | ✅ | ✅ | Personal & Company pages |
| Instagram | ✅ | ✅ | Requires Meta Business |
| Pinterest | ✅ | ✅ | Pin creation |
| Threads | ✅ | ✅ | Meta Threads API |
| Xiaohongshu | ✅ | ✅ | Card generation + publishing |
| WeChat | ✅ | ✅ | Article publishing |

---

## Image Generation

PostAll automatically generates images optimized for each platform:

- **Twitter**: 1200x675 (16:9)
- **LinkedIn**: 1200x627 (1.91:1)
- **Instagram**: 1080x1080 (1:1)
- **Pinterest**: 1000x1500 (2:3)

**Recommended**: Use Gemini Pro for image generation (best quality).

---

## RLHF Learning

The system learns from your feedback:

1. **Rate Content** - Mark posts as good, bad, or needs improvement
2. **Custom Feedback** - Provide specific notes on what to change
3. **Auto-Learning** - System adjusts future generations based on patterns

---

## Agent Integration Patterns

### Pattern 1: Scheduled Generation

Set up weekly content generation with auto-publish:

```python
# In your agent's scheduled tasks
import subprocess

def weekly_content_generation():
    # Generate content
    subprocess.run([
        "python", "-m", "postall.cli", "generate",
        "--project", "projects/mybrand/project.yaml"
    ])
    
    # Publish approved content
    subprocess.run([
        "python", "-m", "postall.cli", "publish", 
        "--project", "projects/mybrand/project.yaml"
    ])
```

### Pattern 2: On-Demand Generation

Generate content when triggered by your agent:

```bash
# Generate a single post for a specific topic
python -m postall.cli generate \
  --project projects/mybrand/project.yaml \
  --topic "New product feature announcement" \
  --platform twitter
```

### Pattern 3: Monitor via Telegram

Let your agent receive status updates via Telegram bot, then take action based on results.

---

## File Structure

```
postall/
├── postall/                    # Core library
│   ├── cli.py                  # Command-line interface
│   ├── config.py               # Configuration management
│   ├── cloud/                  # Cloud services
│   │   ├── daemon.py           # Background daemon
│   │   ├── generation_controller.py
│   │   └── telegram_bot.py
│   ├── director/               # AI review system
│   │   └── director.py
│   ├── executors/              # AI model executors
│   │   ├── claude_api_executor.py
│   │   ├── gemini_api_executor.py
│   │   └── gemini_image_executor.py
│   ├── publishers/             # Platform publishers
│   │   ├── twitter_publisher.py
│   │   ├── linkedin_publisher.py
│   │   ├── instagram_publisher.py
│   │   └── xhs_publisher.py
│   └── learning/               # RLHF system
│       ├── feedback_collector.py
│       └── rlhf_manager.py
├── projects/
│   └── example/                # Example project
│       ├── project.yaml
│       ├── output/             # Generated content
│       └── database/           # Persistent data
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

---

## Critical Rules

When using PostAll, follow these rules to avoid common issues:

1. **NO parentheses in content** - 括号会导致 LinkedIn 内容被截断
2. **NO AI clichés** - 避免「久久不能平静」「震撼了我」「颠覆认知」等空洞表达
3. **NO fabricated data** - 只使用原始内容中的真实信息，不要编造统计数据
4. **Image prompts in English** - AI 图像生成器无法渲染中文字符
5. **Handle rate limits gracefully** - 遇到平台限制时等待后重试
6. **WeChat: use *_content.md files** - Content parser 可能错误分割单篇文章，发布时永远使用完整的 `*_content.md` 文件（如 `wechat_content.md`），不要使用分割后的小文件（如 `01_monday_morning_article.md`）

### Content File Structure

When content is generated, you'll see:
```
wechat-posts/
├── wechat_content.md           # ✅ 完整内容 - 发布时用这个
├── 01_monday_morning_article.md # ❌ 可能被截断
├── 02_tuesday_morning_post.md   # ❌ 可能被截断
└── ...
```

**Always publish using the `*_content.md` file**, not the numbered split files.

---

## Troubleshooting

### Common Issues

**Content not publishing:**
```bash
# Check platform credentials
python -m postall.cli status --project project.yaml

# View detailed logs
docker-compose logs -f postall | grep ERROR
```

**Rate limits:**
- Twitter: 1 post per platform per posting slot
- LinkedIn: Respect 100 posts/day limit
- Instagram: 25 posts/day limit

**Image generation failing:**
- Ensure `GEMINI_API_KEY` is set
- Check quota limits on Google AI Studio

---

## Resources

- **Website**: https://postall.live
- **GitHub**: https://github.com/qingxuantang/postall
- **Demo Video**: https://youtube.com/shorts/12EMDFuA8mc
- **Platform Setup Guide**: https://github.com/qingxuantang/postall/blob/master/docs/PLATFORM_SETUP.md

---

## License

MIT License - Free to use and modify.

---

*Last updated: 2026-03-04*
