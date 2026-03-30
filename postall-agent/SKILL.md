---
name: postall
description: Generate and publish social media posts via PostAll workflow. Supports multi-platform content generation (Twitter, LinkedIn, XHS) with AI-powered content creation and quality review.
---

# PostAll - Multi-Platform Content Publishing

Generate and publish content to Twitter, LinkedIn, and Xiaohongshu via PostAll.

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/qingxuantang/postall.git
cd postall
docker-compose up -d

# 2. Configure your project
cp projects/example/project.yaml projects/myproject/project.yaml
# Edit project.yaml with your settings

# 3. Run content generation
docker exec postall python /app/run_topic_example.py
```

## Workflow

### 1. Content Extraction (Optional)

For YouTube videos, extract content first:

```bash
# Download audio
yt-dlp -x --audio-format mp3 -o "/tmp/%(id)s.%(ext)s" "<youtube_url>"

# Transcribe with Whisper API
curl -s https://api.openai.com/v1/audio/transcriptions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F file="@/tmp/<video_id>.mp3" \
  -F model="whisper-1" \
  -F response_format="text" > transcript.txt
```

### 2. Create Topic Script

Copy an existing script as template:

```bash
cp projects/example/run_topic_template.py projects/myproject/run_topic_<name>.py
```

Edit only these sections:
- `TOPIC_NAME` - Unique identifier (lowercase, no spaces)
- `TOPIC` - Your content/topic details
- `RELATED_HITLIST` - Related talking points (optional)

### 3. Run Pipeline

```bash
docker exec postall python /app/run_topic_<name>.py
```

The pipeline will:
1. Generate Twitter thread
2. Generate LinkedIn post
3. Generate article content
4. Run Director quality review
5. Generate cover image

### 4. Director Quality Gate

Check the Director review before publishing:

```bash
docker exec postall cat /app/output/single_topics/<topic>/director_review_report.md
```

| Score | Decision | Action |
|-------|----------|--------|
| ≥7.0 | Approve | Proceed to publish |
| <7.0 | Reject/Revise | Review feedback and regenerate |

### 5. Publish

```bash
# Copy clean_and_publish.py to container
docker cp clean_and_publish.py postall:/tmp/

# Twitter
docker exec postall python /tmp/clean_and_publish.py twitter <content_file> <image_file>

# LinkedIn
docker exec postall python /tmp/clean_and_publish.py linkedin <content_file> <image_file>

# Xiaohongshu
docker exec postall python /tmp/clean_and_publish.py xhs <cards_dir> <title>
```

## Timeliness System

PostAll includes a timeliness context system to ensure generated content references current tools and trends.

```bash
# Update context
docker exec postall python -m postall.utils.timeliness_context refresh

# View current context
docker exec postall python -m postall.utils.timeliness_context show
```

Edit `data/timeliness_manual_context.json` to customize:
- `current_hot_tools`: Current trending AI tools
- `current_trends`: Current industry trends
- `outdated_references`: Tools no longer considered "cutting edge"

## LinkedIn Token Management

LinkedIn tokens expire every 60 days. Use the auto-refresh script:

```bash
# Initial setup
export LINKEDIN_CLIENT_ID="your_client_id"
export LINKEDIN_CLIENT_SECRET="your_client_secret"
python3 linkedin_auto_refresh.py --init <access_token> <refresh_token>

# Test token
python3 linkedin_auto_refresh.py --test

# Publish with auto-refresh
python3 publish_linkedin.py <content_file> [image_file]
```

## Critical Rules

1. **NO parentheses** - Can cause LinkedIn truncation issues
2. **NO AI clichés** - Avoid overused AI phrases
3. **NO fabricated data** - Only use real information from sources
4. **Image prompts in English** - Gemini cannot generate Chinese text
5. **Twitter rate limits** - If hit, reschedule for next day
6. **No tweet numbering** - Avoid "1/ 2/ 3/" format, looks AI-generated

## Output Structure

```
output/single_topics/<topic>/
├── x-tweets/           # Twitter content
│   └── twitter_content.md
├── linkedin-posts/     # LinkedIn content
│   └── linkedin_content.md
├── wechat-posts/       # Article content
│   └── wechat_content.md
├── xhs-cards/          # Xiaohongshu cards (if generated)
│   ├── card_01.png
│   └── ...
└── image.png           # Cover image
```

## Project Configuration

See `projects/example/project.yaml` for configuration options:
- Brand voice and style
- Platform-specific CTA links
- Content pillars
- Target audience

## API Requirements

- **Claude API** (Anthropic) - Content generation
- **Gemini API** (Google) - Image generation
- **OpenAI API** (optional) - Whisper transcription
- **Platform APIs** - Twitter, LinkedIn, Xiaohongshu
