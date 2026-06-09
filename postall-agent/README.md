# PostAll Agent CLI

AI-friendly command line interface for content generation and publishing.

Designed for **OpenClaw**, **Claude**, and other AI agents.

## Features

- 🤖 **AI-First**: All output is JSON for easy parsing
- 🇨🇳 **Chinese Platforms**: WeChat, Xiaohongshu (小红书) support
- 🌍 **Multi-Platform**: Twitter, LinkedIn, Instagram, and more
- 🎨 **AI Images**: Generate cover images with Gemini
- 📝 **Draft System**: Generate → Review → Publish workflow

## Installation

```bash
pip install postall-agent
```

Or from source:

```bash
cd postall-agent
pip install -e .
```

## Quick Start

### Generate Content

```bash
# Generate content for multiple platforms
postall-agent generate \
  --topic "为什么 AI Agent 是下一个大趋势" \
  --platforms twitter,linkedin,wechat,xhs
```

Output:
```json
{
  "success": true,
  "draft_id": "abc123",
  "topic": "为什么 AI Agent 是下一个大趋势",
  "platforms": ["twitter", "linkedin", "wechat", "xhs"],
  "contents": {
    "twitter": {"thread": ["推文1...", "推文2...", "推文3..."]},
    "linkedin": {"post": "LinkedIn content..."},
    "wechat": {"title": "标题", "article": "正文..."},
    "xhs": {"title": "标题", "content": "正文...", "tags": ["AI", "Agent"]}
  },
  "image_prompt": "A futuristic illustration..."
}
```

### Generate Image

```bash
postall-agent image --draft abc123
```

### Publish

```bash
# Publish to specific platforms
postall-agent publish --draft abc123 --platforms twitter,linkedin

# Publish to all platforms in draft
postall-agent publish --draft abc123
```

### List Drafts

```bash
postall-agent list --status draft
```

### Show Draft Details

```bash
postall-agent show --draft abc123
```

### Check Configured Accounts

```bash
postall-agent accounts
```

### Add Twitter/X Source Context

Before generating a Twitter/X draft that depends on current posts, replies,
profiles, follower context, visible metrics, or media references, collect a
small source packet and include it in the topic notes.

OpenClaw users can install TweetClaw as an optional source-context plugin:

```bash
openclaw plugins install npm:@xquik/tweetclaw@1.6.31
```

Use TweetClaw for source collection only, then let PostAll handle generation,
Director review, scheduling, and publishing:

```bash
postall-agent generate \
  --topic "Launch recap with source packet: <tweet URLs, reply notes, user context, claims to verify>" \
  --platforms twitter,linkedin
```

Keep credentials, cookies, raw sessions, API keys, direct messages, and raw
private exports out of prompts, logs, and draft files. Keep posting, replying,
direct messages, media uploads, monitors, webhooks, and giveaway actions in a
separate explicit approval flow.

## Supported Platforms

| Platform | Generate | Publish | Notes |
|----------|----------|---------|-------|
| Twitter/X | ✅ | ✅ | Thread support |
| LinkedIn | ✅ | ✅ | Professional posts |
| WeChat (公众号) | ✅ | ✅ | Chinese articles |
| Xiaohongshu (小红书) | ✅ | ✅ | Chinese notes |
| Instagram | ✅ | ✅ | Captions + hashtags |

## Environment Variables

```bash
# Claude API (for content generation)
ANTHROPIC_API_KEY=sk-ant-...

# Gemini API (for image generation)
GOOGLE_API_KEY=...

# Twitter
TWITTER_BEARER_TOKEN=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_TOKEN_SECRET=...

# LinkedIn
LINKEDIN_ACCESS_TOKEN=...

# WeChat
WECHAT_APP_ID=...
WECHAT_APP_SECRET=...

# Xiaohongshu (cookie-based)
XHS_COOKIE=...
```

## For AI Agents

All commands output valid JSON with consistent structure:

```json
{
  "success": true,
  "timestamp": "2024-01-01T00:00:00Z",
  ...
}
```

Error responses:

```json
{
  "success": false,
  "error": "error_code",
  "message": "Human readable message"
}
```

### OpenClaw Integration

Add to your OpenClaw SKILL.md:

```yaml
---
name: postall
description: Generate and publish content to multiple social platforms
---

# PostAll Agent CLI

Use `postall-agent` for content operations.

## Generate content
postall-agent generate --topic "..." --platforms twitter,wechat,xhs

## Generate image
postall-agent image --draft <id>

## Publish
postall-agent publish --draft <id>
```

## License

Apache 2.0
