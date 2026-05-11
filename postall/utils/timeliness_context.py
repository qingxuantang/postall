#!/usr/bin/env python3
"""
Timeliness Context Module for PostAll

Fetches current/trending information from authoritative sources
to ensure generated content is up-to-date.

Weekly batch workflow:
1. smart_update_context() - 自动更新明显变化，争议变化发通知
2. refresh_timeliness_context() - 抓取最新数据
3. get_context_for_prompt() - 注入到 prompt

Usage:
    from postall.utils.timeliness_context import smart_update_context, get_context_for_prompt
"""

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from html.parser import HTMLParser


# File paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
MANUAL_CONTEXT_FILE = DATA_DIR / "timeliness_manual_context.json"
FETCHED_CONTEXT_FILE = DATA_DIR / "timeliness_context.json"

# Sources to fetch
SOURCES = {
    "ai_tools": [
        {
            "url": "https://www.producthunt.com/topics/artificial-intelligence",
            "name": "Product Hunt AI",
            "extract": "product_names"
        },
    ],
    "tech_news": [
        {
            "url": "https://news.ycombinator.com/",
            "name": "Hacker News",
            "extract": "headlines"
        },
    ],
}

# Known AI coding tools (for matching)
KNOWN_AI_TOOLS = {
    "claude code", "cursor", "windsurf", "devin", "github copilot",
    "copilot", "v0", "bolt", "lovable", "replit", "codeium", "tabnine",
    "amazon q", "gemini code", "codex", "aider", "continue", "sourcegraph cody",
    "supermaven", "blackbox ai", "kodezi", "pieces", "phind"
}


def load_manual_context() -> Dict:
    """Load manual context from JSON file."""
    if MANUAL_CONTEXT_FILE.exists():
        try:
            return json.loads(MANUAL_CONTEXT_FILE.read_text())
        except:
            pass
    
    # Default fallback
    return {
        "current_hot_tools": ["Claude Code", "Cursor", "Windsurf", "Devin", "GitHub Copilot"],
        "outdated_references": [],
        "current_trends_2026": ["AI agents", "Multi-agent systems"],
        "last_updated": "unknown",
        "updated_by": "default"
    }


def save_manual_context(context: Dict):
    """Save manual context to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    context["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    MANUAL_CONTEXT_FILE.write_text(json.dumps(context, indent=2, ensure_ascii=False))


def fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    """Fetch URL content."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; PostAll/1.0)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[timeliness] Failed to fetch {url}: {e}")
        return None


def extract_hn_headlines(html: str) -> List[str]:
    """Extract headlines from Hacker News."""
    headlines = []
    pattern = r'class="titleline"[^>]*>.*?<a[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, html, re.DOTALL)
    for match in matches[:20]:
        headline = match.strip()
        if headline and len(headline) > 10:
            headlines.append(headline)
    return headlines


def extract_ai_tools_from_headlines(headlines: List[str]) -> List[str]:
    """Extract AI tool names from headlines."""
    found_tools = []
    for headline in headlines:
        headline_lower = headline.lower()
        for tool in KNOWN_AI_TOOLS:
            if tool in headline_lower:
                # Capitalize properly
                found_tools.append(tool.title())
    return list(set(found_tools))


def smart_update_context() -> Dict:
    """
    Smart update: auto-apply obvious changes, flag controversial ones.
    
    Returns:
        {
            "auto_applied": [...],  # Changes applied automatically
            "needs_confirmation": [...],  # Changes needing Mark's approval
            "current_context": {...}
        }
    """
    result = {
        "auto_applied": [],
        "needs_confirmation": [],
        "current_context": None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Load current manual context
    manual = load_manual_context()
    current_tools = set(t.lower() for t in manual.get("current_hot_tools", []))
    
    print("[timeliness] Fetching latest data...")
    
    # Fetch from sources
    new_tools_found = []
    
    # Fetch HN
    hn_html = fetch_url("https://news.ycombinator.com/")
    if hn_html:
        headlines = extract_hn_headlines(hn_html)
        ai_headlines = [h for h in headlines if any(kw in h.lower() for kw in 
                       ['ai', 'gpt', 'claude', 'llm', 'agent', 'openai', 'anthropic', 'coding'])]
        
        # Extract tools from headlines
        tools_in_news = extract_ai_tools_from_headlines(headlines)
        for tool in tools_in_news:
            if tool.lower() not in current_tools:
                new_tools_found.append(tool)
    
    # Analyze changes
    for tool in new_tools_found:
        # Check if it's a well-known tool (auto-apply) or unknown (needs confirmation)
        if tool.lower() in KNOWN_AI_TOOLS:
            # Auto-apply: add to current_hot_tools
            if tool not in manual["current_hot_tools"]:
                manual["current_hot_tools"].append(tool)
                result["auto_applied"].append(f"新增工具: {tool}")
                print(f"[timeliness] Auto-added: {tool}")
        else:
            # Unknown tool, needs confirmation
            result["needs_confirmation"].append({
                "action": "add_tool",
                "tool": tool,
                "reason": "在 Hacker News 上被提及，但不在已知工具列表中"
            })
    
    # Check for tools that might be outdated (not mentioned in news for a while)
    # This is a controversial change, so always flag for confirmation
    # (We don't auto-remove tools)
    
    # Save if there were auto-applied changes
    if result["auto_applied"]:
        manual["updated_by"] = "auto"
        save_manual_context(manual)
        print(f"[timeliness] Saved {len(result['auto_applied'])} auto-applied changes")
    
    result["current_context"] = manual
    return result


def refresh_timeliness_context() -> Dict:
    """
    Full refresh: fetch from sources and update context file.
    Called during weekly batch generation.
    """
    # First do smart update
    update_result = smart_update_context()
    
    # Load manual context (possibly just updated)
    manual = load_manual_context()
    
    # Build full context
    context = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "manual": manual,
        "fetched": {},
        "summary": {},
        "update_result": update_result
    }
    
    # Fetch headlines for context
    hn_html = fetch_url("https://news.ycombinator.com/")
    if hn_html:
        headlines = extract_hn_headlines(hn_html)
        ai_headlines = [h for h in headlines if any(kw in h.lower() for kw in 
                       ['ai', 'gpt', 'claude', 'llm', 'agent', 'openai', 'anthropic'])]
        context["fetched"]["ai_headlines"] = ai_headlines[:5]
    
    # Generate summary
    context["summary"] = {
        "current_hot_ai_tools": manual.get("current_hot_tools", []),
        "current_trends": manual.get("current_trends_2026", []),
        "recent_ai_headlines": context["fetched"].get("ai_headlines", []),
        "last_updated": manual.get("last_updated"),
    }
    
    # Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FETCHED_CONTEXT_FILE.write_text(json.dumps(context, indent=2, ensure_ascii=False))
    
    return context


def get_timeliness_context() -> Dict:
    """Get timeliness context for prompt injection."""
    # Try fetched context first
    if FETCHED_CONTEXT_FILE.exists():
        try:
            context = json.loads(FETCHED_CONTEXT_FILE.read_text())
            return context.get("summary", {})
        except:
            pass
    
    # Fallback to manual context
    manual = load_manual_context()
    return {
        "current_hot_ai_tools": manual.get("current_hot_tools", []),
        "current_trends": manual.get("current_trends_2026", []),
        "recent_ai_headlines": [],
        "last_updated": manual.get("last_updated"),
    }


def get_context_for_prompt() -> str:
    """Get formatted context string for injection into prompts."""
    ctx = get_timeliness_context()
    
    lines = [
        "【时效性参考 - 2026年】",
        "",
        "当前热门 AI 开发工具（按热度排序）：",
    ]
    
    for tool in ctx.get("current_hot_ai_tools", [])[:8]:
        lines.append(f"  - {tool}")
    
    lines.append("")
    lines.append("2026年 AI 趋势：")
    for trend in ctx.get("current_trends", [])[:5]:
        lines.append(f"  - {trend}")
    
    if ctx.get("recent_ai_headlines"):
        lines.append("")
        lines.append("近期 AI 相关新闻：")
        for headline in ctx.get("recent_ai_headlines", [])[:3]:
            lines.append(f"  - {headline}")
    
    lines.append("")
    lines.append(f"（数据更新于: {ctx.get('last_updated', 'unknown')}）")
    lines.append("")
    lines.append("⚠️ 提及 AI 工具时，请参考上述清单，避免将旧工具描述为\"最新\"或\"前沿\"。")
    
    return "\n".join(lines)


def format_update_notification(update_result: Dict) -> str:
    """Format update result as Telegram notification."""
    lines = ["📋 **PostAll 时效性清单更新**", ""]
    
    if update_result.get("auto_applied"):
        lines.append("✅ **已自动更新：**")
        for change in update_result["auto_applied"]:
            lines.append(f"  - {change}")
        lines.append("")
    
    if update_result.get("needs_confirmation"):
        lines.append("❓ **需要确认：**")
        for item in update_result["needs_confirmation"]:
            lines.append(f"  - {item['action']}: {item['tool']}")
            lines.append(f"    原因: {item['reason']}")
        lines.append("")
        lines.append("回复「确认」采纳这些变更，或告诉我具体要改什么。")
    
    if not update_result.get("auto_applied") and not update_result.get("needs_confirmation"):
        lines.append("✅ 清单已是最新，无需更新。")
    
    return "\n".join(lines)


# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "refresh":
            result = refresh_timeliness_context()
            print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
        
        elif cmd == "smart-update":
            result = smart_update_context()
            print(format_update_notification(result))
        
        elif cmd == "prompt":
            print(get_context_for_prompt())
        
        elif cmd == "show":
            ctx = load_manual_context()
            print(json.dumps(ctx, indent=2, ensure_ascii=False))
        
        else:
            print("Usage:")
            print("  python timeliness_context.py refresh       # Full refresh")
            print("  python timeliness_context.py smart-update  # Smart update only")
            print("  python timeliness_context.py prompt        # Show prompt context")
            print("  python timeliness_context.py show          # Show current manual context")
    else:
        print(get_context_for_prompt())
