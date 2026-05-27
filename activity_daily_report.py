#!/usr/bin/env python3
"""Generate a daily ActivityWatch usage report.

The script reads ActivityWatch data through the local aw-server HTTP API and
creates a Markdown report for one day. It intentionally uses only Python's
standard library so it can run from Task Scheduler without a virtualenv.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


BROWSER_APPS = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "slbrowser.exe",
    "browser.exe",
}

DEFAULT_CONFIG = {
    "activitywatch_install_dir": "",
    "api_base": "http://127.0.0.1:5600/api/0",
    "timezone": "Asia/Shanghai",
    "day_start_hour": 0,
    "day_end_hour": 24,
    "min_event_seconds": 1,
    "top_n": 10,
    "output_dir": "reports",
    "category_rules": [
        {"category": "开发/创作", "apps": ["Code.exe", "Cursor.exe", "Codex.exe", "pycharm64.exe", "idea64.exe", "WindowsTerminal.exe", "cmd.exe", "powershell.exe"], "title_keywords": ["github", "stackoverflow", "文档", "docs"]},
        {"category": "沟通", "apps": ["Weixin.exe", "WXWork.exe", "DingTalk.exe", "Feishu.exe", "Teams.exe", "Telegram.exe", "QQ.exe"], "title_keywords": ["微信", "消息"]},
        {"category": "学习/阅读", "apps": [], "title_keywords": ["bilibili", "哔哩哔哩", "知乎", "课程", "论文", "教程", "GitHub"]},
        {"category": "电商/运营", "apps": [], "title_keywords": ["ozon", "ERP", "卖家", "商品", "店铺", "淘宝", "天猫", "京东", "拼多多", "抖音"]},
        {"category": "系统/文件", "apps": ["explorer.exe", "ApplicationFrameHost.exe", "SystemSettings.exe"], "title_keywords": ["设置", "文件资源管理器"]},
        {"category": "娱乐/视频", "apps": [], "title_keywords": ["游戏", "视频", "稍后再看", "直播", "youtube", "YouTube"]},
    ],
    "focus_apps": ["Code.exe", "Cursor.exe", "Codex.exe", "pycharm64.exe", "idea64.exe", "WindowsTerminal.exe", "powershell.exe"],
    "distracting_keywords": ["bilibili", "哔哩哔哩", "游戏", "直播", "短视频"],
    "llm": {
        "enabled": False,
        "provider": "deepseek",
        "history_days": 7,
        "timeout_seconds": 60,
        "max_output_tokens": 1200,
        "temperature": 0.3,
        "providers": {
            "openai": {
                "api_base": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-4.1-mini"
            },
            "deepseek": {
                "api_base": "https://api.deepseek.com/v1",
                "api_key_env": "DEEPSEEK_API_KEY",
                "model": "deepseek-chat"
            },
            "qwen": {
                "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key_env": "DASHSCOPE_API_KEY",
                "model": "qwen-plus"
            },
            "zhipu": {
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
                "api_key_env": "ZHIPU_API_KEY",
                "model": "glm-4-flash"
            },
            "moonshot": {
                "api_base": "https://api.moonshot.cn/v1",
                "api_key_env": "MOONSHOT_API_KEY",
                "model": "moonshot-v1-8k"
            },
            "openrouter": {
                "api_base": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "model": "openai/gpt-4.1-mini"
            },
            "ollama": {
                "api_base": "http://127.0.0.1:11434/v1",
                "api_key_env": "OLLAMA_API_KEY",
                "api_key": "ollama",
                "model": "qwen2.5:7b"
            }
        }
    },
}


@dataclass
class Event:
    start: datetime
    end: datetime
    duration: float
    data: Dict[str, Any]


def load_config(path: Path) -> Dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    if path.exists():
        user_config = json.loads(path.read_text(encoding="utf-8"))
        deep_update(config, user_config)
    return config


def deep_update(base: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value


def resolve_tz(name: str) -> timezone:
    if name in {"Asia/Shanghai", "China", "CST", "+08:00"}:
        return timezone(timedelta(hours=8), name="Asia/Shanghai")
    if re.fullmatch(r"[+-]\d{2}:\d{2}", name):
        sign = 1 if name[0] == "+" else -1
        hours, minutes = map(int, name[1:].split(":"))
        return timezone(sign * timedelta(hours=hours, minutes=minutes), name=name)
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        raise SystemExit(f"Unsupported timezone '{name}'. Use Asia/Shanghai or an offset like +08:00.")


def parse_day(value: str, tz: timezone) -> date:
    if value == "today":
        return datetime.now(tz).date()
    if value == "yesterday":
        return (datetime.now(tz) - timedelta(days=1)).date()
    return date.fromisoformat(value)


def day_bounds(day: date, config: Dict[str, Any], tz: timezone) -> Tuple[datetime, datetime]:
    start_hour = int(config.get("day_start_hour", 0))
    end_hour = int(config.get("day_end_hour", 24))
    start = datetime.combine(day, time.min, tzinfo=tz) + timedelta(hours=start_hour)
    end = datetime.combine(day, time.min, tzinfo=tz) + timedelta(hours=end_hour)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def api_get(api_base: str, path: str, params: Optional[Dict[str, str]] = None) -> Any:
    api_base = api_base.rstrip("/")
    url = f"{api_base}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(
            "Cannot read ActivityWatch API. Make sure ActivityWatch is running "
            f"and reachable at {api_base}. Details: {exc}"
        )


def list_buckets(api_base: str) -> Dict[str, Any]:
    buckets = api_get(api_base, "buckets/")
    if not isinstance(buckets, dict):
        raise SystemExit("Unexpected ActivityWatch buckets response.")
    return buckets


def choose_bucket(buckets: Dict[str, Any], bucket_type: str, client_prefix: str) -> Optional[str]:
    candidates = []
    for bucket_id, bucket in buckets.items():
        if bucket.get("type") == bucket_type or str(bucket.get("client", "")).startswith(client_prefix):
            candidates.append((bucket.get("last_updated", ""), bucket_id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def fetch_events(api_base: str, bucket_id: str, start: datetime, end: datetime, min_seconds: float) -> List[Event]:
    raw_events = api_get(
        api_base,
        f"buckets/{urllib.parse.quote(bucket_id, safe='')}/events",
        {"start": start.isoformat(), "end": end.isoformat()},
    )
    events = []
    for raw in raw_events:
        duration = float(raw.get("duration") or 0)
        if duration < min_seconds:
            continue
        event_start = parse_timestamp(raw["timestamp"]).astimezone(start.tzinfo)
        event_end = event_start + timedelta(seconds=duration)
        clipped_start = max(event_start, start)
        clipped_end = min(event_end, end)
        clipped_duration = (clipped_end - clipped_start).total_seconds()
        if clipped_duration >= min_seconds:
            events.append(Event(clipped_start, clipped_end, clipped_duration, raw.get("data") or {}))
    events.sort(key=lambda event: event.start)
    return events


def parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def human_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes:02d}分"
    if minutes:
        return f"{minutes}分{sec:02d}秒"
    return f"{sec}秒"


def percent(part: float, total: float) -> str:
    if total <= 0:
        return "0%"
    return f"{part / total * 100:.1f}%"


def clean_app(app: str) -> str:
    return app or "Unknown"


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    return title if title else "(空标题)"


def infer_category(app: str, title: str, config: Dict[str, Any]) -> str:
    app_lower = app.lower()
    title_lower = title.lower()
    for rule in config.get("category_rules", []):
        apps = [str(item).lower() for item in rule.get("apps", [])]
        keywords = [str(item).lower() for item in rule.get("title_keywords", [])]
        if app_lower in apps or any(keyword in title_lower for keyword in keywords):
            return rule.get("category", "其他")
    return "浏览器" if app_lower in BROWSER_APPS else "其他"


def build_stats(window_events: List[Event], afk_events: List[Event], config: Dict[str, Any]) -> Dict[str, Any]:
    app_seconds = Counter()
    title_seconds = Counter()
    category_seconds = Counter()
    timeline_hours = defaultdict(float)
    focus_seconds = 0.0
    distraction_seconds = 0.0
    raw_window_seconds = sum(event.duration for event in window_events)
    afk_intervals = [
        (event.start, event.end)
        for event in afk_events
        if str(event.data.get("status", "")).lower() == "afk"
    ]
    active_window_events = subtract_intervals(window_events, afk_intervals)

    focus_apps = {item.lower() for item in config.get("focus_apps", [])}
    distracting_keywords = [item.lower() for item in config.get("distracting_keywords", [])]

    for event in active_window_events:
        app = clean_app(str(event.data.get("app", "")))
        title = clean_title(str(event.data.get("title", "")))
        key = f"{app} | {title}"
        app_seconds[app] += event.duration
        title_seconds[key] += event.duration
        category_seconds[infer_category(app, title, config)] += event.duration
        add_to_hourly_timeline(timeline_hours, event)
        if app.lower() in focus_apps:
            focus_seconds += event.duration
        if any(keyword in title.lower() for keyword in distracting_keywords):
            distraction_seconds += event.duration

    afk_seconds = 0.0
    not_afk_seconds = 0.0
    for event in afk_events:
        status = str(event.data.get("status", "")).lower()
        if status == "afk":
            afk_seconds += event.duration
        elif status == "not-afk":
            not_afk_seconds += event.duration

    active_seconds = sum(app_seconds.values())

    return {
        "tracked_seconds": raw_window_seconds,
        "active_seconds": active_seconds,
        "afk_seconds": afk_seconds,
        "app_seconds": app_seconds,
        "title_seconds": title_seconds,
        "category_seconds": category_seconds,
        "timeline_hours": timeline_hours,
        "focus_seconds": focus_seconds,
        "distraction_seconds": distraction_seconds,
    }


def subtract_intervals(events: List[Event], blocked: List[Tuple[datetime, datetime]]) -> List[Event]:
    if not blocked:
        return list(events)
    blocked = sorted(blocked)
    result = []
    for event in events:
        fragments = [(event.start, event.end)]
        for block_start, block_end in blocked:
            next_fragments = []
            for frag_start, frag_end in fragments:
                if block_end <= frag_start or block_start >= frag_end:
                    next_fragments.append((frag_start, frag_end))
                    continue
                if block_start > frag_start:
                    next_fragments.append((frag_start, min(block_start, frag_end)))
                if block_end < frag_end:
                    next_fragments.append((max(block_end, frag_start), frag_end))
            fragments = next_fragments
            if not fragments:
                break
        for frag_start, frag_end in fragments:
            duration = (frag_end - frag_start).total_seconds()
            if duration > 0:
                result.append(Event(frag_start, frag_end, duration, event.data))
    return result


def add_to_hourly_timeline(timeline: Dict[int, float], event: Event) -> None:
    cursor = event.start
    while cursor < event.end:
        next_hour = (cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        chunk_end = min(event.end, next_hour)
        timeline[cursor.hour] += (chunk_end - cursor).total_seconds()
        cursor = chunk_end


def table(counter: Counter, total: float, top_n: int) -> str:
    rows = ["| 项目 | 时长 | 占比 |", "| --- | ---: | ---: |"]
    for key, seconds in counter.most_common(top_n):
        rows.append(f"| {escape_md(str(key))} | {human_duration(seconds)} | {percent(seconds, total)} |")
    return "\n".join(rows)


def escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def timeline_bar(hour_seconds: Dict[int, float]) -> str:
    if not hour_seconds:
        return "无可用时间线数据。"
    max_seconds = max(hour_seconds.values()) or 1
    lines = []
    for hour in range(24):
        seconds = hour_seconds.get(hour, 0)
        if seconds <= 0:
            continue
        width = max(1, int(math.ceil(seconds / max_seconds * 20)))
        lines.append(f"- {hour:02d}:00 {'█' * width} {human_duration(seconds)}")
    return "\n".join(lines)


def counter_items(counter: Counter, top_n: int) -> List[Dict[str, Any]]:
    return [
        {"name": str(name), "seconds": round(seconds, 3), "duration": human_duration(seconds)}
        for name, seconds in counter.most_common(top_n)
    ]


def stats_payload(report_day: date, stats: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    top_n = int(config.get("top_n", 10))
    return {
        "date": report_day.isoformat(),
        "tracked_seconds": round(stats["tracked_seconds"], 3),
        "active_seconds": round(stats["active_seconds"], 3),
        "afk_seconds": round(stats["afk_seconds"], 3),
        "focus_seconds": round(stats["focus_seconds"], 3),
        "distraction_seconds": round(stats["distraction_seconds"], 3),
        "top_apps": counter_items(stats["app_seconds"], top_n),
        "top_categories": counter_items(stats["category_seconds"], top_n),
        "top_titles": counter_items(stats["title_seconds"], top_n),
        "hourly_seconds": {f"{hour:02d}:00": round(seconds, 3) for hour, seconds in sorted(stats["timeline_hours"].items())},
    }


def load_history_reports(output_dir: Path, report_day: date, history_days: int) -> List[Dict[str, str]]:
    reports = []
    for path in sorted(output_dir.glob("*.md"), reverse=True):
        if len(reports) >= history_days:
            break
        if path.stem >= report_day.isoformat():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        reports.append({"date": path.stem, "content": text[:6000]})
    return list(reversed(reports))


def resolve_llm_provider(config: Dict[str, Any], provider_name: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    llm_config = config.get("llm", {})
    name = provider_name or llm_config.get("provider")
    providers = llm_config.get("providers", {})
    if name not in providers:
        available = ", ".join(sorted(providers)) or "(none)"
        raise SystemExit(f"Unknown LLM provider '{name}'. Available providers: {available}")
    provider = dict(providers[name])
    return name, provider


def should_use_llm(config: Dict[str, Any], mode: str) -> bool:
    if mode == "on":
        return True
    if mode == "off":
        return False
    return bool(config.get("llm", {}).get("enabled", False))


def make_llm_summary(
    report_day: date,
    stats: Dict[str, Any],
    config: Dict[str, Any],
    output_dir: Path,
    provider_name: Optional[str],
) -> str:
    llm_config = config.get("llm", {})
    name, provider = resolve_llm_provider(config, provider_name)
    api_base = str(provider.get("api_base", "")).rstrip("/")
    model = str(provider.get("model", ""))
    api_key = str(provider.get("api_key") or os.environ.get(str(provider.get("api_key_env", "")), ""))
    if not api_base or not model:
        raise SystemExit(f"LLM provider '{name}' needs api_base and model.")
    if not api_key:
        env_name = provider.get("api_key_env", "API_KEY")
        raise SystemExit(f"LLM provider '{name}' needs an API key. Set environment variable {env_name}, or add api_key in config.")

    history = load_history_reports(output_dir, report_day, int(llm_config.get("history_days", 7)))
    payload = {
        "today": stats_payload(report_day, stats, config),
        "history_reports": history,
        "user_preferences": {
            "timezone": config.get("timezone"),
            "focus_apps": config.get("focus_apps", []),
            "distracting_keywords": config.get("distracting_keywords", []),
            "category_rules": config.get("category_rules", []),
        },
    }
    system_prompt = (
        "你是一个严谨的个人时间审计和复盘助手。你只基于用户提供的 ActivityWatch 统计数据和历史日报写分析，"
        "不要编造未出现的事情。输出中文 Markdown，语气直接、具体、有帮助。"
    )
    user_prompt = (
        "请根据下面的当天结构化数据和历史日报，生成更精确的日报增强总结。\n"
        "要求：\n"
        "1. 先给 3-5 条关键观察，包含趋势或异常。\n"
        "2. 指出可能的高价值时间、低价值时间和上下文切换问题。\n"
        "3. 给出明天最多 3 条可执行建议。\n"
        "4. 不要重复完整排行榜，不要输出空泛鸡汤。\n\n"
        f"数据 JSON：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(llm_config.get("temperature", 0.3)),
        "max_tokens": int(llm_config.get("max_output_tokens", 1200)),
    }
    req = urllib.request.Request(
        f"{api_base}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=int(llm_config.get("timeout_seconds", 60))) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"LLM provider '{name}' returned HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot call LLM provider '{name}' at {api_base}: {exc}")
    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise SystemExit(f"Unexpected LLM response from provider '{name}': {data}")
    return f"由 `{name}` / `{model}` 生成。\n\n{content}"


def make_insights(stats: Dict[str, Any], config: Dict[str, Any]) -> List[str]:
    insights = []
    total = stats["tracked_seconds"]
    active = stats["active_seconds"]
    afk = stats["afk_seconds"]
    focus = stats["focus_seconds"]
    distraction = stats["distraction_seconds"]
    top_app = stats["app_seconds"].most_common(1)
    top_category = stats["category_seconds"].most_common(1)

    if top_app:
        insights.append(f"今天最主要的应用是 {top_app[0][0]}，累计 {human_duration(top_app[0][1])}。")
    if top_category:
        insights.append(f"最高占比类别是 {top_category[0][0]}，约占活跃使用时间的 {percent(top_category[0][1], active)}。")
    if active:
        insights.append(f"活跃使用时间约 {human_duration(active)}，空闲时间约 {human_duration(afk)}。")
    if focus:
        insights.append(f"可归为深度工作/创作工具的时间约 {human_duration(focus)}，占活跃时间 {percent(focus, active)}。")
    if distraction:
        insights.append(f"可能分散注意力的内容约 {human_duration(distraction)}，占活跃时间 {percent(distraction, active)}。")
    if total and len(stats["app_seconds"]) >= 8:
        insights.append("应用切换较多，可以关注是否存在频繁上下文切换。")
    return insights or ["今天的数据较少，建议保持 ActivityWatch 运行一整天后再看趋势。"]


def render_report(
    report_day: date,
    start: datetime,
    end: datetime,
    buckets: Dict[str, Optional[str]],
    stats: Dict[str, Any],
    config: Dict[str, Any],
    llm_summary: Optional[str] = None,
) -> str:
    top_n = int(config.get("top_n", 10))
    total = stats["tracked_seconds"]
    active = stats["active_seconds"]
    generated_at = datetime.now(start.tzinfo).strftime("%Y-%m-%d %H:%M:%S %Z")
    insights = "\n".join(f"- {item}" for item in make_insights(stats, config))
    llm_section = f"\n\n## 大模型增强分析\n\n{llm_summary}\n" if llm_summary else "\n"

    return f"""# 电脑使用日报 - {report_day.isoformat()}

生成时间：{generated_at}
统计区间：{start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%Y-%m-%d %H:%M')}
数据来源：window bucket `{buckets.get('window') or '未找到'}`；afk bucket `{buckets.get('afk') or '未找到'}`

## 总览

- 窗口记录时长：{human_duration(total)}
- 活跃使用时长：{human_duration(active)}
- 空闲/离开时长：{human_duration(stats['afk_seconds'])}
- 深度工作/创作工具：{human_duration(stats['focus_seconds'])}（{percent(stats['focus_seconds'], active)}）
- 可能分心内容：{human_duration(stats['distraction_seconds'])}（{percent(stats['distraction_seconds'], active)}）

## 自动总结

{insights}{llm_section}
## 应用排行

{table(stats['app_seconds'], active, top_n)}

## 类别排行

{table(stats['category_seconds'], active, top_n)}

## 主要窗口/网页

{table(stats['title_seconds'], active, top_n)}

## 小时分布

{timeline_bar(stats['timeline_hours'])}

## 明日建议

- 把最高占比的非目标类别设为一个明确的时间盒，而不是全天散落出现。
- 如果深度工作占比偏低，明天优先安排一个 60-90 分钟的无打断时段。
- 如果窗口切换很多，收尾时记录今天最消耗注意力的 1-2 个入口，并考虑关闭通知或固定浏览器标签。
"""


def write_report(content: str, output_dir: Path, report_day: date) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report_day.isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a daily ActivityWatch Markdown report.")
    parser.add_argument("--date", default="today", help="Date to report: today, yesterday, or YYYY-MM-DD.")
    parser.add_argument("--config", default="activity_report_config.json", help="Path to JSON config.")
    parser.add_argument("--output-dir", help="Override report output directory.")
    parser.add_argument("--llm", choices=["auto", "on", "off"], default="auto", help="Use optional LLM enhancement.")
    parser.add_argument("--provider", help="LLM provider name from config, such as deepseek, openai, qwen, zhipu, moonshot, openrouter, ollama.")
    parser.add_argument("--save-json", action="store_true", help="Write the structured daily data next to the Markdown report.")
    parser.add_argument("--print", action="store_true", help="Print report to stdout as well as writing it.")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config = load_config(config_path)
    if args.output_dir:
        config["output_dir"] = args.output_dir

    tz = resolve_tz(str(config.get("timezone", "Asia/Shanghai")))
    report_day = parse_day(args.date, tz)
    start, end = day_bounds(report_day, config, tz)

    buckets = list_buckets(str(config["api_base"]))
    window_bucket = choose_bucket(buckets, "currentwindow", "aw-watcher-window")
    afk_bucket = choose_bucket(buckets, "afkstatus", "aw-watcher-afk")
    if not window_bucket:
        raise SystemExit("No ActivityWatch window bucket found. Is aw-watcher-window running?")

    min_seconds = float(config.get("min_event_seconds", 1))
    window_events = fetch_events(str(config["api_base"]), window_bucket, start, end, min_seconds)
    afk_events = fetch_events(str(config["api_base"]), afk_bucket, start, end, min_seconds) if afk_bucket else []
    stats = build_stats(window_events, afk_events, config)

    output_dir = Path(str(config["output_dir"]))
    llm_summary = None
    if should_use_llm(config, args.llm):
        try:
            llm_summary = make_llm_summary(report_day, stats, config, output_dir, args.provider)
        except BaseException as exc:
            llm_summary = (
                "LLM 增强分析生成失败，已保留基础统计日报。\n\n"
                f"错误信息：`{escape_md(type(exc).__name__ + ': ' + str(exc))}`"
            )

    report = render_report(report_day, start, end, {"window": window_bucket, "afk": afk_bucket}, stats, config, llm_summary)
    report_path = write_report(report, output_dir, report_day)
    if args.save_json:
        json_path = output_dir / f"{report_day.isoformat()}.json"
        json_path.write_text(json.dumps(stats_payload(report_day, stats, config), ensure_ascii=False, indent=2), encoding="utf-8")
    if args.print:
        print(report)
    print(f"Report written: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
