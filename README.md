# PostAll 📮

**AI-powered multi-platform social media content generation and publishing workflow.**

PostAll is an automated content pipeline that generates platform-specific posts from your brand guidelines and content strategy, then publishes them across multiple social platforms.

## ✨ Features

- **Multi-Platform Publishing**: Twitter/X, LinkedIn, Instagram, Pinterest, Xiaohongshu
- **AI Content Generation**: Claude, GPT-4, Gemini support
- **Director Review System**: AI-powered quality control before publishing
- **Brand Consistency**: Define your voice, tone, and style once — apply everywhere
- **Smart Scheduling**: Optimal posting times per platform
- **Content Pillars**: Balanced content mix (education, insights, tips, stories)
- **RLHF Learning**: Improves from your feedback over time
- **Image Generation**: Auto-generate matching visuals with AI
- **Xiaohongshu Cards**: Generate image cards for Chinese social platforms

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/postall.git
cd postall

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

### 2. Configure Your Project

Edit `projects/example/project.yaml`:

```yaml
project_name: "My Brand"
brand:
  name: "My Brand"
  tagline: "Your Tagline Here"
  voice:
    tone: "professional yet friendly"
    
platforms:
  twitter:
    enabled: true
  linkedin:
    enabled: true
```

### 3. Run with Docker

```bash
docker-compose up -d
```

Or run locally:

```bash
pip install -e .
python -m postall.cli --project projects/example/project.yaml daemon
```

## 📁 Project Structure

```
postall/
├── postall/              # Core library
│   ├── cli.py            # Command-line interface
│   ├── config.py         # Configuration management
│   ├── director/         # AI review system
│   ├── executors/        # Content generation
│   ├── generators/       # Platform-specific generators
│   ├── publishers/       # Platform publishers
│   ├── learning/         # RLHF feedback system
│   └── utils/            # Utilities
├── projects/
│   └── example/          # Example project config
│       ├── project.yaml  # Brand & strategy config
│       ├── output/       # Generated content
│       └── database/     # Persistent data
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## 🔧 Configuration

### Brand Configuration

Define your brand identity in `project.yaml`:

```yaml
brand:
  name: "Your Brand"
  tagline: "Your Tagline"
  
  voice:
    tone: "professional yet friendly"
    characteristics:
      - "clear and concise"
      - "helpful and educational"
    avoid:
      - "aggressive sales language"
      - "technical jargon"
```

### Content Strategy

Configure content pillars and themes:

```yaml
content_strategy:
  pillars:
    product_education: 35
    industry_insights: 25
    tips_productivity: 20
    customer_stories: 10
    behind_scenes: 5
    lead_magnet: 5
    
  posting_times:
    twitter: ["08:00", "12:00", "18:00"]
    linkedin: ["07:30", "12:00"]
```

### Platform Setup

Enable/disable platforms and configure credentials in `.env`:

```bash
TWITTER_ENABLED=true
TWITTER_API_KEY=your_key
TWITTER_API_SECRET=your_secret
# ... etc
```

## 📝 CLI Commands

```bash
# Generate content for all platforms
python -m postall.cli generate --project project.yaml

# Generate for specific platform
python -m postall.cli generate --project project.yaml --platform twitter

# Publish pending content
python -m postall.cli publish --project project.yaml

# Run as daemon (auto generate + publish on schedule)
python -m postall.cli daemon --project project.yaml

# Review generated content
python -m postall.cli review --project project.yaml
```

## 🤖 How It Works

1. **Content Generation**: Based on your brand guidelines and content pillars, AI generates platform-optimized posts
2. **Director Review**: Another AI agent reviews content for quality, brand alignment, and potential issues
3. **Human Review** (optional): Preview and approve content before publishing
4. **Publishing**: Auto-publish to configured platforms at optimal times
5. **Learning**: RLHF system learns from your feedback to improve future content

## 📊 Supported Platforms

| Platform | Publishing | Image Support | Notes |
|----------|------------|---------------|-------|
| Twitter/X | ✅ | ✅ | Threads supported |
| LinkedIn | ✅ | ✅ | Personal & Company pages |
| Instagram | ✅ | ✅ | Requires Meta Business |
| Pinterest | ✅ | ✅ | |
| Xiaohongshu | ✅ | ✅ | Card generation + publishing |

## 🛠 Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black postall/
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

Built with:
- [Anthropic Claude](https://anthropic.com) - Primary AI engine
- [Google Gemini](https://ai.google.dev) - Image generation
- [OpenAI](https://openai.com) - Alternative AI provider

---

**Questions?** Open an issue or reach out!
