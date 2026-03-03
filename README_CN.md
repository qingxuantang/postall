# PostAll 📮

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**[English](./README.md) | [中文](#postall-)**

> AI 驱动的多平台社交媒体内容生成与自动发布工具

PostAll 是一个完整的内容自动化流水线，它能根据你的品牌指南和内容策略生成平台优化的帖子，通过 AI 质量控制进行审核，并自动发布到多个社交平台。

## ✨ 功能特点

- **🤖 AI 内容生成** - 支持 Claude、GPT-4 和 Gemini
- **🎯 Director 审核系统** - AI 质量控制，发布前检查品牌一致性
- **📱 多平台发布** - Twitter/X、LinkedIn、Instagram、Pinterest、Threads、小红书
- **🎨 图片生成** - AI 自动生成配图
- **📊 内容策略** - 定义内容支柱、主题，保持均衡的内容组合
- **📈 RLHF 学习** - 系统从你的反馈中持续改进
- **⏰ 智能排期** - 每个平台的最佳发布时间
- **🔄 守护进程模式** - 持续运行，自动生成和发布

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Docker（可选，推荐）
- AI 服务商 API 密钥（Anthropic、OpenAI 或 Google）

### 安装

#### 方式一：Docker（推荐）

```bash
git clone https://github.com/qingxuantang/postall.git
cd postall

# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入你的 API 密钥

# 使用 Docker 启动
docker-compose up -d
```

#### 方式二：本地安装

```bash
git clone https://github.com/qingxuantang/postall.git
cd postall

# 安装依赖
pip install -e .

# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入你的 API 密钥

# 运行
python -m postall.cli --project projects/example/project.yaml daemon
```

### 基础配置

1. **设置 API 密钥**（`.env` 文件）：

```bash
ANTHROPIC_API_KEY=your_key_here
# 或
OPENAI_API_KEY=your_key_here
# 或
GEMINI_API_KEY=your_key_here
```

2. **配置你的品牌**（`projects/example/project.yaml`）：

```yaml
project_name: "我的品牌"
brand:
  name: "我的品牌"
  tagline: "品牌标语"
  voice:
    tone: "专业但友好"
    characteristics:
      - "清晰简洁"
      - "有帮助且有教育意义"
    avoid:
      - "激进的销售语言"
      - "技术术语"

platforms:
  twitter:
    enabled: true
  linkedin:
    enabled: true
```

3. **运行内容生成**：

```bash
# 生成内容
python -m postall.cli generate --project projects/example/project.yaml

# 或以守护进程运行（自动生成 + 发布）
python -m postall.cli daemon --project projects/example/project.yaml
```

## 📁 项目结构

```
postall/
├── postall/                    # 核心库
│   ├── cli.py                  # 命令行接口
│   ├── config.py               # 配置管理
│   ├── cloud/                  # 云服务
│   │   ├── daemon.py           # 后台守护进程
│   │   ├── generation_controller.py  # AI 内容生成
│   │   ├── telegram_bot.py     # Telegram 机器人
│   │   └── notifier.py         # 通知服务
│   ├── director/               # AI 审核系统
│   │   └── director.py         # 质量控制
│   ├── executors/              # AI 模型执行器
│   │   ├── claude_api_executor.py
│   │   ├── gemini_api_executor.py
│   │   └── gemini_image_executor.py
│   ├── publishers/             # 平台发布器
│   │   ├── twitter_publisher.py
│   │   ├── linkedin_publisher.py
│   │   ├── instagram_publisher.py
│   │   ├── pinterest_publisher.py
│   │   ├── threads_publisher.py
│   │   └── xhs_publisher.py    # 小红书
│   ├── generators/             # 内容生成器
│   │   └── xhs_cards.py        # 小红书卡片
│   ├── learning/               # RLHF 系统
│   │   ├── feedback_collector.py
│   │   ├── rlhf_manager.py
│   │   └── rule_library.py
│   └── theory_framework/       # 内容框架
│       ├── hook_types.py
│       ├── psychology_triggers.py
│       └── viral_scorer.py
├── projects/
│   └── example/                # 示例项目
│       ├── project.yaml        # 品牌和策略配置
│       ├── output/             # 生成的内容
│       └── database/           # 持久化数据
├── docs/                       # 落地页
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## 🔧 配置指南

### 品牌配置

在 `project.yaml` 中定义你的品牌身份：

```yaml
brand:
  name: "你的品牌"
  tagline: "品牌标语"
  website: "yourbrand.com"
  
  # 色彩方案（用于图片生成）
  colors:
    primary: "#3498DB"
    secondary: "#2ECC71"
    accent: "#E74C3C"
  
  # 语言风格指南
  voice:
    tone: "专业但友好"
    characteristics:
      - "清晰简洁"
      - "有帮助且有教育意义"
      - "真实可信"
    avoid:
      - "激进的销售语言"
      - "过度承诺或炒作"
      - "技术术语"
      - "陈词滥调"
```

### 内容策略

配置内容支柱和分布：

```yaml
content_strategy:
  # 内容支柱分布（总计需为100%）
  pillars:
    product_education: 35    # 产品教育
    industry_insights: 25    # 行业洞察
    tips_productivity: 20    # 技巧和方法
    customer_stories: 10     # 客户故事
    behind_scenes: 5         # 幕后花絮
    lead_magnet: 5           # 免费资源

  # 内容主题
  themes:
    - "入门指南"
    - "最佳实践"
    - "常见错误"
    - "成功案例"

  # 平台特定标签
  hashtags:
    twitter:
      - "#你的品牌"
      - "#你的行业"
    linkedin:
      - "#职场"
      - "#商业增长"
```

### 平台设置

配置每个平台：

```yaml
platforms:
  twitter:
    enabled: true
    language: "zh"    # 中文
    
  linkedin:
    enabled: true
    language: "en"    # 英文
    
  instagram:
    enabled: false    # 需要 Meta Business 设置
    
  pinterest:
    enabled: false
    
  threads:
    enabled: false
```

### 发布排期

设置最佳发布时间：

```yaml
timezone: "Asia/Shanghai"

generation_schedule:
  day: "saturday"     # 每周生成内容的日期
  time: "09:00"

posting_times:
  twitter: ["08:00", "12:00", "18:00"]
  linkedin: ["07:30", "12:00"]
  instagram: ["08:00", "17:00"]
```

## 📝 命令行命令

```bash
# 为所有平台生成内容
python -m postall.cli generate --project project.yaml

# 为特定平台生成内容
python -m postall.cli generate --project project.yaml --platform twitter

# 使用特定 AI 模型生成
python -m postall.cli generate --project project.yaml --model claude

# 发布待发内容
python -m postall.cli publish --project project.yaml

# 以守护进程运行（持续运行）
python -m postall.cli daemon --project project.yaml

# 审核生成的内容
python -m postall.cli review --project project.yaml

# 检查系统状态
python -m postall.cli status --project project.yaml
```

## 🤖 工作原理

### 内容生成流程

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    品牌配置     │────▶│    AI 生成      │────▶│  Director 审核  │
│ (project.yaml)  │     │  (Claude/GPT)   │     │   (质量检查)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│      发布       │◀────│    人工审核     │◀────│    内容就绪     │
│   (各平台)      │     │    (可选)       │     │    (已通过)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │   RLHF 学习     │
                                                │    (改进)       │
                                                └─────────────────┘
```

### Director 审核系统

Director 是第二个 AI，用于审核生成的内容：

- **品牌一致性** - 是否符合你的语言风格和调性？
- **质量标准** - 是否写得好、有吸引力？
- **平台适配** - 是否针对目标平台进行了优化？
- **事实准确性** - 没有编造的统计数据或声明
- **合规性** - 没有问题内容

### RLHF 学习

系统从你的反馈中学习：

1. **评价内容** - 将帖子标记为好、差或需要改进
2. **自定义反馈** - 提供具体的修改意见
3. **自动学习** - 系统根据模式调整未来的生成

## 📊 支持的平台

| 平台 | 发布 | 图片支持 | 备注 |
|------|------|----------|------|
| Twitter/X | ✅ | ✅ | 支持推文串 |
| LinkedIn | ✅ | ✅ | 个人和公司页面 |
| Instagram | ✅ | ✅ | 需要 Meta Business |
| Pinterest | ✅ | ✅ | Pin 创建 |
| Threads | ✅ | ✅ | Meta Threads API |
| 小红书 | ✅ | ✅ | 卡片生成 + 发布 |

## 🔐 环境变量

```bash
# AI 服务商（至少需要一个）
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

# Telegram 机器人（可选，用于通知）
TELEGRAM_BOT_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## 🛠 开发

```bash
# 克隆仓库
git clone https://github.com/qingxuantang/postall.git
cd postall

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows 使用 `venv\Scripts\activate`

# 以开发模式安装
pip install -e ".[dev]"

# 运行测试
pytest

# 格式化代码
black postall/
```

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request。

1. Fork 仓库
2. 创建你的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📖 文档

- **[平台 API 设置指南](docs/PLATFORM_SETUP_CN.md)** - 如何获取各平台 API 凭证
- **[Platform API Setup Guide](docs/PLATFORM_SETUP.md)** - How to get API credentials (English)

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

基于以下技术构建：
- [Anthropic Claude](https://anthropic.com) - 主要 AI 引擎
- [Google Gemini](https://ai.google.dev) - 图片生成
- [OpenAI](https://openai.com) - 备选 AI 服务商

---

**网站：** [postall.live](https://postall.live)

**有问题？** 欢迎提 Issue 或发起讨论！
