# PostAll 📮

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**[English](#postall-) | [中文](./README_CN.md)**

> AI-powered multi-platform social media content generation and publishing automation.

PostAll is a complete content automation pipeline that generates platform-optimized posts from your brand guidelines and content strategy, reviews them with AI quality control, and publishes across multiple social platforms.

## 📺 Demo

See the Telegram Bot in action:

[![PostAll Telegram Bot Demo](https://img.youtube.com/vi/12EMDFuA8mc/maxresdefault.jpg)](https://youtube.com/shorts/12EMDFuA8mc)

*Click to watch the demo video*

## 🤖 AI Agent Integration

PostAll is designed for AI agent automation. Use our **Agent CLI** or integrate via skill files.

### Agent CLI (NEW!)

A dedicated command-line interface for AI agents with JSON output:

```bash
# Install
pip install postall-agent

# Generate content for multiple platforms
postall-agent generate --topic "AI is changing how we work" --platforms twitter,linkedin,wechat,xhs

# Output (all commands return JSON)
{
  "success": true,
  "draft_id": "abc123",
  "contents": {
    "twitter": {"thread": ["Tweet 1...", "Tweet 2...", "Tweet 3..."]},
    "linkedin": {"post": "Professional content..."},
    "wechat": {"title": "标题", "article": "公众号文章..."},
    "xhs": {"title": "小红书标题", "content": "笔记内容...", "tags": ["AI", "效率"]}
  },
  "image_prompt": "A futuristic workspace..."
}

# Generate cover image
postall-agent image --draft abc123

# Publish to platforms
postall-agent publish --draft abc123 --platforms twitter,linkedin

# List drafts
postall-agent list --status draft
```

See [postall-agent/README.md](postall-agent/README.md) for full documentation.

### Skill Files

For AI agents that prefer HTTP-based discovery:

| File | URL | Description |
|------|-----|-------------|
| **SKILL.md** | [`https://postall.live/skill.md`](https://postall.live/skill.md) | Full integration guide for AI agents |
| **skill.json** | [`https://postall.live/skill.json`](https://postall.live/skill.json) | Machine-readable metadata |

```bash
# Your AI agent can fetch and read these files directly
curl https://postall.live/skill.md
curl https://postall.live/skill.json
```

## 🎯 How It Works

### End-to-End Content Automation
![PostAll Workflow](https://postall.live/assets/hero/01_workflow.jpg)

### One-Time Setup, Endless Automation
![One-Time Setup](https://postall.live/assets/hero/02_setup.jpg)
Configure your brand once - AI handles everything else automatically.

### AI Director Review System
![Director Review](https://postall.live/assets/hero/03_director.jpg)
Quality control with brand alignment, factual accuracy, and platform best practices.

### Smart Image Generation
![Image Generation](https://postall.live/assets/hero/04_images.jpg)
Auto-generate platform-optimized images with correct dimensions. Gemini Pro 3 recommended.

### Auto Scheduling & Publishing
![Auto Publishing](https://postall.live/assets/hero/05_publish.jpg)
AI arranges optimal timing and publishes automatically - no manual drag-and-drop needed.

## ✨ Features

- **🤖 AI Content Generation** - Powered by Claude, GPT-4, and Gemini
- **🎯 Director Review System** - AI quality control with **per-issue actionable fixes** (location + original text + suggested replacement, not just a score)
- **📅 Timeliness Context** - Auto-detects when content references go stale and keeps generated content using current AI tooling vocabulary
- **📱 Multi-Platform Publishing** - Twitter/X, LinkedIn, Instagram, Pinterest, Threads, Xiaohongshu
- **🎨 Image Generation** - Auto-generate matching visuals with AI (Gemini with retry/backoff)
- **📊 Content Strategy** - Define pillars, themes, and maintain balanced content mix
- **📈 RLHF Learning** - System improves from your feedback over time
- **⏰ Smart Scheduling** - Optimal posting times per platform
- **🔄 Daemon Mode** - Run continuously with auto-generation and publishing
- **🛡️ Production Safety** - Rate limiting, atomic publish claims, crash recovery, and 12-hour sliding window prevent surprise group-publishes after daemon restarts

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Docker (optional, recommended)
- API keys for AI providers (Anthropic, OpenAI, or Google)

### Installation

#### Option 1: Docker (Recommended)

```bash
git clone https://github.com/qingxuantang/postall.git
cd postall

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Start with Docker
docker-compose up -d
```

#### Option 2: Local Installation

```bash
git clone https://github.com/qingxuantang/postall.git
cd postall

# Install dependencies
pip install -e .

# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Run
python -m postall.cli --project projects/example/project.yaml daemon
```

### Basic Configuration

1. **Set up API keys** in `.env`:

```bash
ANTHROPIC_API_KEY=your_key_here
# or
OPENAI_API_KEY=your_key_here
# or
GEMINI_API_KEY=your_key_here
```

2. **Configure your brand** in `projects/example/project.yaml`:

```yaml
project_name: "My Brand"
brand:
  name: "My Brand"
  tagline: "Your Tagline"
  voice:
    tone: "professional yet friendly"
    characteristics:
      - "clear and concise"
      - "helpful and educational"
    avoid:
      - "aggressive sales language"
      - "technical jargon"

platforms:
  twitter:
    enabled: true
  linkedin:
    enabled: true
```

3. **Run content generation**:

```bash
# Generate content
python -m postall.cli generate --project projects/example/project.yaml

# Or run as daemon (auto generate + publish)
python -m postall.cli daemon --project projects/example/project.yaml
```

## 📁 Project Structure

```
postall/
├── postall/                    # Core library
│   ├── cli.py                  # Command-line interface
│   ├── config.py               # Configuration management
│   ├── cloud/                  # Cloud services
│   │   ├── daemon.py           # Background daemon
│   │   ├── generation_controller.py  # AI content generation
│   │   ├── telegram_bot.py     # Telegram bot interface
│   │   └── notifier.py         # Notifications
│   ├── director/               # AI review system
│   │   └── director.py         # Quality control
│   ├── executors/              # AI model executors
│   │   ├── claude_api_executor.py
│   │   ├── gemini_api_executor.py
│   │   └── gemini_image_executor.py
│   ├── publishers/             # Platform publishers
│   │   ├── twitter_publisher.py
│   │   ├── linkedin_publisher.py
│   │   ├── instagram_publisher.py
│   │   ├── pinterest_publisher.py
│   │   ├── threads_publisher.py
│   │   └── xhs_publisher.py    # Xiaohongshu
│   ├── generators/             # Content generators
│   │   └── xhs_cards.py        # Xiaohongshu cards
│   ├── learning/               # RLHF system
│   │   ├── feedback_collector.py
│   │   ├── rlhf_manager.py
│   │   └── rule_library.py
│   └── theory_framework/       # Content frameworks
│       ├── hook_types.py
│       ├── psychology_triggers.py
│       └── viral_scorer.py
├── projects/
│   └── example/                # Example project
│       ├── project.yaml        # Brand & strategy config
│       ├── output/             # Generated content
│       └── database/           # Persistent data
├── docs/                       # Landing page
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## 🔧 Configuration Guide

### Brand Configuration

Define your brand identity in `project.yaml`:

```yaml
brand:
  name: "Your Brand"
  tagline: "Your Tagline"
  website: "yourbrand.com"
  
  # Color palette (for image generation)
  colors:
    primary: "#3498DB"
    secondary: "#2ECC71"
    accent: "#E74C3C"
  
  # Voice guidelines
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
      - "clichés and buzzwords"
```

### Content Strategy

Configure content pillars and distribution:

```yaml
content_strategy:
  # Pillar distribution (must total 100%)
  pillars:
    product_education: 35    # Teaching about your product
    industry_insights: 25    # Industry trends and news
    tips_productivity: 20    # Tips and how-tos
    customer_stories: 10     # Success stories
    behind_scenes: 5         # Company culture
    lead_magnet: 5           # Free resources

  # Content themes
  themes:
    - "Getting Started"
    - "Best Practices"
    - "Common Mistakes"
    - "Success Stories"

  # Platform-specific hashtags
  hashtags:
    twitter:
      - "#YourBrand"
      - "#YourIndustry"
    linkedin:
      - "#Professional"
      - "#BusinessGrowth"
```

### Platform Settings

Configure each platform:

```yaml
platforms:
  twitter:
    enabled: true
    language: "en"
    
  linkedin:
    enabled: true
    language: "en"
    
  instagram:
    enabled: false  # Requires Meta Business setup
    
  pinterest:
    enabled: false
    
  threads:
    enabled: false
```

### Scheduling

Set optimal posting times:

```yaml
timezone: "America/Los_Angeles"

generation_schedule:
  day: "saturday"     # When to generate weekly content
  time: "09:00"

posting_times:
  twitter: ["08:00", "12:00", "18:00"]
  linkedin: ["07:30", "12:00"]
  instagram: ["08:00", "17:00"]
```

## 📝 CLI Commands

```bash
# Generate content for all platforms
python -m postall.cli generate --project project.yaml

# Generate for specific platform
python -m postall.cli generate --project project.yaml --platform twitter

# Generate with specific AI model
python -m postall.cli generate --project project.yaml --model claude

# Publish pending content
python -m postall.cli publish --project project.yaml

# Run as daemon (continuous operation)
python -m postall.cli daemon --project project.yaml

# Review generated content
python -m postall.cli review --project project.yaml

# Check system status
python -m postall.cli status --project project.yaml
```

## 🤖 How It Works

### Content Generation Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Brand Config   │────▶│  AI Generation  │────▶│ Director Review │
│  (project.yaml) │     │  (Claude/GPT)   │     │  (Quality Check)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Publishing    │◀────│  Human Review   │◀────│  Content Ready  │
│   (Platforms)   │     │   (Optional)    │     │   (Approved)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  RLHF Learning  │
                                                │  (Improvement)  │
                                                └─────────────────┘
```

### Director Review System

The Director is a second AI that reviews generated content for:

- **Brand Alignment** - Does it match your voice and tone?
- **Quality Standards** - Is it well-written and engaging?
- **Platform Fit** - Is it optimized for the target platform?
- **Factual Accuracy** - No fabricated statistics or claims
- **Fabricated Testimonials** - Detects invented user stories (named characters, fake quotes) without source material and rejects them outright
- **Compliance** - No problematic content

#### Per-Issue Actionable Feedback

For each deduction, the Director outputs a structured `ReviewIssue` with:

- `dimension` — which scoring axis was hit
- `deduction` — how many points lost
- `location` — where in the content (e.g. "第2段", "opening line")
- `original_text` — the exact problematic snippet
- `suggestion` — the specific replacement text

Example:
```json
{
  "dimension": "factual_accuracy",
  "deduction": -0.3,
  "location": "第2段",
  "original_text": "全球AI数据中心耗电量排世界第四",
  "suggestion": "据BloombergNEF数据，全球AI数据中心耗电量已跻身全球第四"
}
```

This turns review into a copy-paste editing workflow instead of a "go figure out what to fix" loop.

### Timeliness Context

Generated content can quickly age — references to "the new GPT-4 release" or "the latest from OpenAI" get stale fast. PostAll's timeliness module:

- Maintains a curated list of currently-hot AI tools, current-year trends, and outdated references
- On each generation cycle, fetches the Hacker News front page and auto-detects new tools mentioned
- Known tools are auto-added to `current_hot_tools`; unknown ones flag for human confirmation
- Injects the up-to-date list into generation prompts so produced content uses current tooling vocabulary

### Production Safety (Daemon Mode)

The publish daemon includes safeguards that matter the moment you run it on a real server:

- **Rate limit** — caps at `PUBLISH_RATE_LIMIT` posts per `PUBLISH_RATE_WINDOW_HOURS` (defaults: 3 per 2h). A daemon restart that finds a large queue won't drain it in one burst (which social platforms flag as bot behavior)
- **12-hour sliding window** — anything scheduled more than 12h in the past is considered abandoned and never auto-published; manually rescheduling is the explicit path
- **Atomic publish claims** — `claim_post_for_publishing` atomically transitions `scheduled → publishing` before the publisher call; concurrent loop iterations or daemon instances can't both publish the same post
- **Crash recovery on startup** — rows stuck in `publishing` from a SIGKILL / OOM are marked `failed` (not `scheduled`), preventing accidental re-publish on next restart
- **Pre-filter unconfigured platforms** — don't waste rate-limit quota on platforms you haven't set up

These are belt-and-suspenders: each one alone would help, but together they make daemon restarts safe even with a dirty queue.

### RLHF Learning

The system learns from your feedback:

1. **Rate Content** - Mark posts as good, bad, or needs improvement
2. **Custom Feedback** - Provide specific notes on what to change
3. **Auto-Learning** - System adjusts future generations based on patterns

## 📊 Supported Platforms

| Platform | Publishing | Image Support | Notes |
|----------|------------|---------------|-------|
| Twitter/X | ✅ | ✅ | Threads supported |
| LinkedIn | ✅ | ✅ | Personal & Company pages |
| Instagram | ✅ | ✅ | Requires Meta Business |
| Pinterest | ✅ | ✅ | Pin creation |
| Threads | ✅ | ✅ | Meta Threads API |
| Xiaohongshu | ✅ | ✅ | Card generation + publishing |

## 🔐 Environment Variables

```bash
# AI Providers (at least one required)
ANTHROPIC_API_KEY=       # Claude API
OPENAI_API_KEY=          # GPT-4 API
GEMINI_API_KEY=          # Gemini API

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

# Telegram Bot (optional, for notifications)
TELEGRAM_BOT_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## 🛠 Development

```bash
# Clone repository
git clone https://github.com/qingxuantang/postall.git
cd postall

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black postall/
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📖 Documentation

- **[Platform API Setup Guide](docs/PLATFORM_SETUP.md)** - How to get API credentials for each platform
- **[平台 API 设置指南](docs/PLATFORM_SETUP_CN.md)** - 如何获取各平台 API 凭证（中文）

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with:
- [Anthropic Claude](https://anthropic.com) - Primary AI engine
- [Google Gemini](https://ai.google.dev) - Image generation
- [OpenAI](https://openai.com) - Alternative AI provider

---

**Website:** [postall.live](https://postall.live)

**Questions?** Open an issue or start a discussion!
