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

# ── Agent Pulse: optional evidence-backed AI-industry event feed ──
# Agent Pulse (https://github.com/barretlee/agent-pulse, MIT-licensed code)
# publishes a daily-refreshed static feed of scored, evidence-backed AI-industry
# events. We consume the public allowlisted feed (titles, summaries, scores,
# canonical evidence links, and Agent Pulse's original synthesis) purely to
# inform generation prompts — we do not redistribute its content verbatim.
# The feed's DATA is NOT MIT-licensed; see docs/LEGAL.md in that repo. Attribution
# is preserved in the injected prompt block. Disable with env AGENT_PULSE_ENABLED=0.
import os

AGENT_PULSE_ENABLED = os.getenv("AGENT_PULSE_ENABLED", "1") not in ("0", "false", "no")
AGENT_PULSE_URL = os.getenv(
    "AGENT_PULSE_URL",
    "https://barretlee.github.io/agent-pulse/data/timeline.json",
)
AGENT_PULSE_CACHE_FILE = DATA_DIR / "agent_pulse_cache.json"
AGENT_PULSE_CACHE_TTL_HOURS = int(os.getenv("AGENT_PULSE_CACHE_TTL_HOURS", "24"))
# Default widened 30->90 on 2026-09-09: the feed publishes high-impact events
# with a multi-week lag while filling recent days with low-signal release-tag
# noise; a 30-day window intersected with impact>=80 yielded 0 events. See the
# ref_now comment in fetch_agent_pulse_events for the full root cause.
AGENT_PULSE_RECENT_DAYS = int(os.getenv("AGENT_PULSE_RECENT_DAYS", "90"))
AGENT_PULSE_MIN_IMPACT = int(os.getenv("AGENT_PULSE_MIN_IMPACT", "80"))
AGENT_PULSE_MIN_CONFIDENCE = int(os.getenv("AGENT_PULSE_MIN_CONFIDENCE", "70"))
AGENT_PULSE_TOP_K = int(os.getenv("AGENT_PULSE_TOP_K", "8"))
AGENT_PULSE_ATTRIBUTION = "Agent Pulse (barretlee.github.io/agent-pulse)"


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


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (tolerant of trailing Z)."""
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_agent_pulse_events(force: bool = False) -> List[Dict]:
    """
    Fetch and filter recent high-signal AI-industry events from Agent Pulse.

    Consumes the public daily-refreshed feed, caches it locally for
    AGENT_PULSE_CACHE_TTL_HOURS, and returns the top-K most impactful recent
    events. Degrades to [] on any failure or when disabled — never raises, so
    it can never block generation.

    Returns a list of dicts: {title, summary, category, company, evidence_url,
    impact, published_at}.
    """
    if not AGENT_PULSE_ENABLED:
        return []

    payload = None

    # 1) Try fresh-enough cache
    if not force and AGENT_PULSE_CACHE_FILE.exists():
        try:
            cached = json.loads(AGENT_PULSE_CACHE_FILE.read_text())
            fetched_at = _parse_iso(cached.get("cached_at"))
            if fetched_at:
                age_h = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
                if age_h < AGENT_PULSE_CACHE_TTL_HOURS:
                    payload = cached.get("payload")
        except Exception:
            payload = None

    # 2) Cache miss/stale -> fetch live, refresh cache
    if payload is None:
        raw = fetch_url(AGENT_PULSE_URL, timeout=15)
        if not raw:
            # Fall back to a stale cache if we have one, else give up quietly
            if AGENT_PULSE_CACHE_FILE.exists():
                try:
                    payload = json.loads(AGENT_PULSE_CACHE_FILE.read_text()).get("payload")
                except Exception:
                    return []
            else:
                return []
        else:
            try:
                payload = json.loads(raw)
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                AGENT_PULSE_CACHE_FILE.write_text(json.dumps({
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                    "source": AGENT_PULSE_URL,
                    "payload": payload,
                }, ensure_ascii=False))
            except Exception:
                return []

    if not payload:
        return []

    events = payload.get("events") or []
    # Anchor the recency window to the FRESHEST event actually present in the
    # feed (fallback: generatedAt, then now). This decouples recency from
    # generatedAt, which can drift from the real event dates.
    #
    # Root cause of the silent "0 events injected" bug (diagnosed 2026-09-09):
    # Agent Pulse's RECENT entries are low-signal noise (release tags / build
    # numbers like "v5.16.0", impactScore ~55), while the genuine high-impact
    # events (GPT-5.6 impact 98, Grok 4.5 impact 97, GLM-5.2 impact 97) cluster
    # 6-8 weeks back. With impact>=80 AND a 30-day window, the two sets are
    # mutually exclusive -> intersection empty -> 0 events reach the prompt,
    # silently. Fix: keep the impact bar high (so the version-bump noise stays
    # OUT) but widen the window (AGENT_PULSE_RECENT_DAYS default 30->90) so the
    # high-impact events, which the feed publishes with a lag, get through.
    # top-K by impact means noise never makes the cut even inside the window.
    # NOTE: this surfaces the freshest *high-impact* cluster the feed has; it
    # does NOT make an upstream-stale feed current (that is item 3.2 / the
    # manual-seed refresh, tracked separately).
    _event_dates = [
        d for d in (_parse_iso(e.get("publishedAt") or e.get("happenedAt")) for e in events)
        if d
    ]
    ref_now = max(_event_dates) if _event_dates else \
        (_parse_iso(payload.get("generatedAt")) or datetime.now(timezone.utc))

    scored = []
    for e in events:
        pub = _parse_iso(e.get("publishedAt") or e.get("happenedAt"))
        if not pub:
            continue
        age_days = (ref_now - pub).days
        impact = e.get("impactScore", 0) or 0
        conf = e.get("confidenceScore", 0) or 0
        if age_days <= AGENT_PULSE_RECENT_DAYS and impact >= AGENT_PULSE_MIN_IMPACT \
                and conf >= AGENT_PULSE_MIN_CONFIDENCE:
            evidence = e.get("evidence") or []
            scored.append((impact, e.get("heatScore", 0) or 0, {
                "title": e.get("title", "").strip(),
                "summary": (e.get("summary") or e.get("factSummary") or "").strip(),
                "category": e.get("category", ""),
                "company": e.get("company", ""),
                "evidence_url": evidence[0]["url"] if evidence else "",
                "impact": impact,
                "published_at": (e.get("publishedAt") or e.get("happenedAt") or "")[:10],
            }))

    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [item[2] for item in scored[:AGENT_PULSE_TOP_K]]


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
    # Optional evidence-backed industry events (never raises, [] if unavailable)
    industry_events = fetch_agent_pulse_events()

    # Try fetched context first
    if FETCHED_CONTEXT_FILE.exists():
        try:
            context = json.loads(FETCHED_CONTEXT_FILE.read_text())
            summary = context.get("summary", {})
            summary["industry_events"] = industry_events
            return summary
        except:
            pass

    # Fallback to manual context
    manual = load_manual_context()
    return {
        "current_hot_ai_tools": manual.get("current_hot_tools", []),
        "current_trends": manual.get("current_trends_2026", []),
        "recent_ai_headlines": [],
        "industry_events": industry_events,
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

    industry_events = ctx.get("industry_events", [])
    if industry_events:
        lines.append("")
        lines.append("近期 AI 行业重大事件（evidence-backed，按影响力排序）：")
        for e in industry_events:
            head = e.get("title", "")
            meta = " · ".join(x for x in [e.get("company", ""), e.get("published_at", "")] if x)
            lines.append(f"  - {head}" + (f" [{meta}]" if meta else ""))
            if e.get("summary"):
                lines.append(f"    {e['summary']}")
            if e.get("evidence_url"):
                lines.append(f"    来源: {e['evidence_url']}")
        lines.append("")
        lines.append(f"（行业事件来源: {AGENT_PULSE_ATTRIBUTION}）")

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

        elif cmd == "agent-pulse":
            events = fetch_agent_pulse_events(force="--force" in sys.argv)
            print(f"Fetched {len(events)} events from {AGENT_PULSE_ATTRIBUTION}\n")
            print(json.dumps(events, indent=2, ensure_ascii=False))
        
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
