#!/usr/bin/env python3
"""Local web console for ActivityWatch Daily Reporter."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from datetime import datetime, timedelta

from activity_daily_report import DEFAULT_CONFIG, deep_update, load_config, resolve_tz


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "activity_report_config.json"
REPORT_SCRIPT = ROOT / "activity_daily_report.py"
TASK_NAME = "ActivityWatch Daily Report"
MAX_REQUEST_BYTES = 1024 * 1024
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ActivityWatch 日报控制台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-2: #eef3f8;
      --text: #18212f;
      --muted: #657386;
      --line: #d9e1ea;
      --accent: #1769aa;
      --accent-2: #0d9276;
      --danger: #bd3f32;
      --shadow: 0 12px 30px rgba(21, 39, 63, 0.09);
      font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      min-width: 320px;
    }
    header {
      background: #12344d;
      color: #fff;
      padding: 20px 24px;
      border-bottom: 4px solid #2fa37f;
    }
    .header-inner {
      max-width: 1180px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      font-weight: 700;
      letter-spacing: 0;
    }
    .subtitle {
      color: #c7d8e5;
      margin-top: 5px;
      font-size: 13px;
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px 20px 34px;
      display: grid;
      grid-template-columns: 260px 1fr;
      gap: 18px;
    }
    nav {
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      border-radius: 8px;
      align-self: start;
      overflow: hidden;
    }
    .tab {
      width: 100%;
      border: 0;
      background: transparent;
      padding: 14px 16px;
      text-align: left;
      color: var(--text);
      font-size: 14px;
      cursor: pointer;
      border-bottom: 1px solid var(--line);
    }
    .tab:last-child { border-bottom: 0; }
    .tab.active {
      background: #e8f2f7;
      color: #0f568d;
      font-weight: 700;
    }
    .stack {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      border-radius: 8px;
      padding: 18px;
      display: none;
    }
    section.active { display: block; }
    h2 {
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: 0;
    }
    h3 {
      margin: 18px 0 10px;
      font-size: 15px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    label {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      min-height: 38px;
      padding: 8px 10px;
      font-size: 14px;
      font-family: inherit;
    }
    textarea {
      min-height: 108px;
      resize: vertical;
      line-height: 1.45;
    }
    .toggle {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 38px;
      color: var(--text);
      font-size: 14px;
    }
    .toggle input {
      width: 18px;
      height: 18px;
      min-height: 18px;
      accent-color: var(--accent);
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }
    button {
      border: 1px solid transparent;
      border-radius: 6px;
      min-height: 38px;
      padding: 8px 13px;
      background: var(--accent);
      color: #fff;
      font-size: 14px;
      cursor: pointer;
      font-family: inherit;
    }
    button.secondary {
      background: #fff;
      color: var(--accent);
      border-color: #9bc0d8;
    }
    button.success { background: var(--accent-2); }
    button.danger { background: var(--danger); }
    button:disabled {
      opacity: .55;
      cursor: wait;
    }
    .status {
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .provider-row {
      display: grid;
      grid-template-columns: 150px 1fr 1fr 1fr 92px;
      gap: 10px;
      padding: 10px 0;
      border-top: 1px solid var(--line);
      align-items: end;
    }
    .provider-row:first-of-type { border-top: 0; }
    .report-preview {
      height: 520px;
      overflow: auto;
      background: #fcfdff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      white-space: pre-wrap;
      line-height: 1.55;
      font-size: 13px;
    }
    .report-preview h1,
    .report-preview h2,
    .report-preview h3 {
      margin: 18px 0 10px;
      color: var(--text);
    }
    .report-preview h1 { font-size: 22px; border-bottom: 1px solid var(--line); padding-bottom: 10px; }
    .report-preview h2 { font-size: 18px; }
    .report-preview h3 { font-size: 15px; }
    .report-preview table {
      border-collapse: collapse;
      width: 100%;
      margin: 10px 0 16px;
      white-space: normal;
    }
    .report-preview th,
    .report-preview td {
      border: 1px solid var(--line);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
    }
    .report-preview th { background: #edf4f8; }
    .report-preview ul { padding-left: 22px; }
    .report-preview code {
      background: #eef3f8;
      padding: 1px 5px;
      border-radius: 4px;
    }
    .pill {
      display: inline-block;
      background: #eaf4ef;
      color: #1b6c58;
      border: 1px solid #b9ddce;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 12px;
    }
    .muted { color: var(--muted); }
    .hint {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 17px;
      height: 17px;
      border-radius: 50%;
      background: #dcebf3;
      color: #18577d;
      font-size: 12px;
      font-weight: 700;
      cursor: help;
      margin-left: 5px;
      position: relative;
    }
    .hint .tooltip {
      position: absolute;
      left: 50%;
      bottom: 130%;
      transform: translateX(-50%);
      min-width: 260px;
      max-width: 340px;
      background: #172434;
      color: #fff;
      border-radius: 6px;
      padding: 9px 10px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, .18);
      font-weight: 400;
      line-height: 1.45;
      text-align: left;
      visibility: hidden;
      opacity: 0;
      transition: opacity .12s ease;
      z-index: 20;
      pointer-events: none;
    }
    .hint:hover .tooltip,
    .hint:focus .tooltip {
      visibility: visible;
      opacity: 1;
    }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; }
      nav { display: grid; grid-template-columns: repeat(2, 1fr); }
      .tab { border-right: 1px solid var(--line); }
      .grid, .grid-3, .provider-row { grid-template-columns: 1fr; }
      .header-inner { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div>
        <h1>ActivityWatch 日报控制台</h1>
        <div class="subtitle">配置、生成、预览和自动化你的每日电脑使用日报</div>
      </div>
      <span id="awStatus" class="pill">检测中</span>
    </div>
  </header>
  <main>
    <nav>
      <button class="tab active" data-tab="general">基础配置</button>
      <button class="tab" data-tab="llm">大模型</button>
      <button class="tab" data-tab="automation">自动化</button>
      <button class="tab" data-tab="report">生成日报</button>
    </nav>
    <div class="stack">
      <section id="general" class="active">
        <h2>基础配置</h2>
        <div class="grid">
          <div><label>ActivityWatch 安装目录</label><input id="activitywatch_install_dir" /></div>
          <div><label>ActivityWatch API 地址</label><input id="api_base" /></div>
          <div><label>日报输出目录</label><input id="output_dir" /></div>
          <div><label>时区</label><input id="timezone" /></div>
          <div><label>统计日起始小时</label><input id="day_start_hour" type="number" min="0" max="23" /></div>
          <div><label>统计日结束小时</label><input id="day_end_hour" type="number" min="1" max="48" /></div>
          <div><label>最短事件秒数</label><input id="min_event_seconds" type="number" min="0" step="1" /></div>
          <div><label>排行榜数量</label><input id="top_n" type="number" min="3" max="50" /></div>
        </div>
        <h3>识别规则</h3>
        <div class="grid">
          <div><label>深度工作应用，每行一个</label><textarea id="focus_apps"></textarea></div>
          <div><label>可能分心关键词，每行一个</label><textarea id="distracting_keywords"></textarea></div>
        </div>
        <div class="actions">
          <button class="success" id="saveGeneral">保存配置</button>
          <button class="secondary" id="reloadConfig">重新读取</button>
        </div>
      </section>

      <section id="llm">
        <h2>大模型配置</h2>
        <div class="grid-3">
          <label class="toggle"><input id="llm_enabled" type="checkbox" />启用 LLM 增强日报</label>
          <div><label>默认 provider</label><select id="llm_provider"></select></div>
          <div><label>历史日报天数</label><input id="llm_history_days" type="number" min="0" max="90" /></div>
          <div><label>创意程度 <span class="hint" tabindex="0">?<span class="tooltip">对应大模型 API 的 temperature 参数。数值越低，输出越稳定、重复性越强；数值越高，表达越发散。日报建议 0.2-0.4。</span></span></label><input id="llm_temperature" type="number" min="0" max="2" step="0.1" /></div>
          <div><label>最大输出 tokens</label><input id="llm_max_output_tokens" type="number" min="100" step="100" /></div>
          <div><label>请求超时秒数</label><input id="llm_timeout_seconds" type="number" min="5" step="5" /></div>
        </div>
        <h3>Provider 列表</h3>
        <div class="status">API Key 可以填环境变量名，也可以直接填 api_key。直接保存 key 会写入本地配置文件。一个 provider 对应一个默认模型；如果同一家服务要用多个模型，可以新增多个 provider 别名。</div>
        <div class="grid-3" style="margin-top:12px">
          <div><label>新增 provider 名称</label><input id="new_provider_name" placeholder="例如 siliconflow" /></div>
          <div><label>API Base</label><input id="new_provider_base" placeholder="https://api.example.com/v1" /></div>
          <div><label>模型</label><input id="new_provider_model" placeholder="model-name" /></div>
          <div><label>API Key 环境变量</label><input id="new_provider_key_env" placeholder="SILICONFLOW_API_KEY" /></div>
          <div><label>直接 API Key，可留空</label><input id="new_provider_key" placeholder="sk-..." /></div>
        </div>
        <div class="actions">
          <button class="secondary" id="addProvider">添加并保存 provider</button>
        </div>
        <div id="providers"></div>
        <div class="actions">
          <button class="success" id="saveLlm">保存大模型配置</button>
          <button class="secondary" id="testLlm">测试当前 provider</button>
        </div>
      </section>

      <section id="automation">
        <h2>自动化</h2>
        <div class="grid">
          <label class="toggle"><input id="schedule_enabled" type="checkbox" />启用 Windows 每日任务</label>
          <div><label>每日生成时间</label><input id="schedule_time" type="time" /></div>
          <div><label>日报日期</label><select id="schedule_report_date"><option value="today">当天</option><option value="yesterday">昨天</option></select></div>
          <div><label>自动任务 LLM 模式</label><select id="schedule_llm"><option value="auto">跟随配置</option><option value="on">强制启用</option><option value="off">关闭</option></select></div>
          <div><label>自动任务 provider</label><select id="schedule_provider"></select></div>
          <label class="toggle"><input id="schedule_silent" type="checkbox" />静默运行，不弹出执行窗口</label>
        </div>
        <div class="actions">
          <button class="success" id="saveAutomation">保存并应用任务</button>
          <button class="secondary" id="refreshTask">刷新任务状态</button>
          <button class="danger" id="deleteTask">删除任务</button>
        </div>
        <h3>任务状态</h3>
        <div class="status" id="taskStatus">未读取</div>
      </section>

      <section id="report">
        <h2>生成日报</h2>
        <div class="grid-3">
          <div><label>日期</label><select id="report_date"><option value="today">今天</option><option value="yesterday">昨天</option></select></div>
          <div><label>LLM 模式</label><select id="report_llm"><option value="auto">跟随配置</option><option value="on">强制启用</option><option value="off">关闭</option></select></div>
          <div><label>Provider</label><select id="report_provider"></select></div>
        </div>
        <div class="actions">
          <button class="success" id="generateReport">生成日报</button>
          <button class="secondary" id="loadLatest">读取最新日报</button>
          <button class="secondary" id="openReports">查看历史日报</button>
        </div>
        <div class="status" id="reportTarget">目标日期：未计算</div>
        <h3>预览</h3>
        <div class="report-preview" id="preview"><p class="muted">还没有生成或读取日报。</p></div>
      </section>

      <div class="status" id="message">准备就绪。</div>
    </div>
  </main>
  <script>
    let config = {};
    const $ = (id) => document.getElementById(id);
    const lineArray = (text) => text.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    const toLines = (arr) => (arr || []).join("\n");

    async function api(path, options = {}) {
      const res = await fetch(path, {
        ...options,
        headers: {"Content-Type": "application/json", ...(options.headers || {})}
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || "请求失败");
      return data;
    }

    function setMessage(text) { $("message").textContent = text; }
    function setBusy(button, busy) { button.disabled = busy; }

    function providerNames() {
      return Object.keys(config.llm?.providers || {});
    }

    function fillProviderSelect(select, includeEmpty = false) {
      const current = select.value;
      select.innerHTML = "";
      if (includeEmpty) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "使用默认";
        select.appendChild(opt);
      }
      providerNames().forEach(name => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        select.appendChild(opt);
      });
      if ([...select.options].some(o => o.value === current)) select.value = current;
    }

    function renderConfig() {
      $("activitywatch_install_dir").value = config.activitywatch_install_dir || "";
      $("api_base").value = config.api_base || "";
      $("output_dir").value = config.output_dir || "";
      $("timezone").value = config.timezone || "";
      $("day_start_hour").value = config.day_start_hour ?? 0;
      $("day_end_hour").value = config.day_end_hour ?? 24;
      $("min_event_seconds").value = config.min_event_seconds ?? 1;
      $("top_n").value = config.top_n ?? 10;
      $("focus_apps").value = toLines(config.focus_apps);
      $("distracting_keywords").value = toLines(config.distracting_keywords);

      $("llm_enabled").checked = !!config.llm?.enabled;
      fillProviderSelect($("llm_provider"));
      fillProviderSelect($("schedule_provider"), true);
      fillProviderSelect($("report_provider"), true);
      $("llm_provider").value = config.llm?.provider || providerNames()[0] || "";
      $("llm_history_days").value = config.llm?.history_days ?? 7;
      $("llm_temperature").value = config.llm?.temperature ?? 0.3;
      $("llm_max_output_tokens").value = config.llm?.max_output_tokens ?? 1200;
      $("llm_timeout_seconds").value = config.llm?.timeout_seconds ?? 60;

      const schedule = config.schedule || {};
      $("schedule_enabled").checked = !!schedule.enabled;
      $("schedule_time").value = schedule.time || "23:55";
      $("schedule_report_date").value = schedule.report_date || "today";
      $("schedule_llm").value = schedule.llm || "auto";
      $("schedule_provider").value = schedule.provider || "";
      $("schedule_silent").checked = schedule.silent !== false;
      updateReportTarget();

      renderProviders();
    }

    function refreshProviderControls() {
      const selected = $("llm_provider").value || config.llm?.provider || "";
      fillProviderSelect($("llm_provider"));
      fillProviderSelect($("schedule_provider"), true);
      fillProviderSelect($("report_provider"), true);
      if ([...$("llm_provider").options].some(o => o.value === selected)) $("llm_provider").value = selected;
      $("schedule_provider").value = config.schedule?.provider || "";
      $("report_provider").value = "";
    }

    function collectConfig() {
      config.activitywatch_install_dir = $("activitywatch_install_dir").value.trim();
      config.api_base = $("api_base").value.trim();
      config.output_dir = $("output_dir").value.trim();
      config.timezone = $("timezone").value.trim();
      config.day_start_hour = Number($("day_start_hour").value);
      config.day_end_hour = Number($("day_end_hour").value);
      config.min_event_seconds = Number($("min_event_seconds").value);
      config.top_n = Number($("top_n").value);
      config.focus_apps = lineArray($("focus_apps").value);
      config.distracting_keywords = lineArray($("distracting_keywords").value);

      config.llm = config.llm || {};
      config.llm.enabled = $("llm_enabled").checked;
      config.llm.provider = $("llm_provider").value;
      config.llm.history_days = Number($("llm_history_days").value);
      config.llm.temperature = Number($("llm_temperature").value);
      config.llm.max_output_tokens = Number($("llm_max_output_tokens").value);
      config.llm.timeout_seconds = Number($("llm_timeout_seconds").value);
      collectProviders();

      config.schedule = {
        enabled: $("schedule_enabled").checked,
        time: $("schedule_time").value || "23:55",
        report_date: $("schedule_report_date").value,
        llm: $("schedule_llm").value,
        provider: $("schedule_provider").value,
        silent: $("schedule_silent").checked
      };
    }

    function formatLocalDate(date) {
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, "0");
      const d = String(date.getDate()).padStart(2, "0");
      return `${y}-${m}-${d}`;
    }

    function resolveReportDateValue(value) {
      const date = new Date();
      if (value === "yesterday") date.setDate(date.getDate() - 1);
      if (value === "today" || value === "yesterday") return formatLocalDate(date);
      return value;
    }

    function updateReportTarget() {
      if ($("reportTarget")) {
        $("reportTarget").textContent = `目标日期：${resolveReportDateValue($("report_date").value)}`;
      }
    }

    function renderProviders() {
      const wrap = $("providers");
      wrap.innerHTML = "";
      const providers = config.llm?.providers || {};
      Object.entries(providers).forEach(([name, p]) => {
        const row = document.createElement("div");
        row.className = "provider-row";
        row.dataset.provider = name;
        row.innerHTML = `
          <div><label>名称</label><input data-field="name" value="${escapeHtml(name)}" disabled /></div>
          <div><label>API Base</label><input data-field="api_base" value="${escapeHtml(p.api_base || "")}" /></div>
          <div><label>模型</label><input data-field="model" value="${escapeHtml(p.model || "")}" /></div>
          <div><label>Key 环境变量 / 直接 Key</label><input data-field="api_key_env" value="${escapeHtml(p.api_key_env || "")}" placeholder="环境变量名" /><input data-field="api_key" value="${escapeHtml(p.api_key || "")}" placeholder="直接 API Key，可留空" style="margin-top:6px" /></div>
          <div><button class="danger provider-delete" data-name="${escapeHtml(name)}" type="button">删除</button></div>
        `;
        wrap.appendChild(row);
      });
      document.querySelectorAll(".provider-delete").forEach(btn => {
        btn.addEventListener("click", () => {
          const name = btn.dataset.name;
          if (!name) return;
          delete config.llm.providers[name];
          if (config.llm.provider === name) config.llm.provider = providerNames()[0] || "";
          if (config.schedule?.provider === name) config.schedule.provider = "";
          renderProviders();
          refreshProviderControls();
          setMessage(`已删除 provider：${name}，保存后生效。`);
        });
      });
    }

    function collectProviders() {
      config.llm.providers = config.llm.providers || {};
      document.querySelectorAll(".provider-row").forEach(row => {
        const name = row.dataset.provider;
        const get = (field) => row.querySelector(`[data-field="${field}"]`).value.trim();
        config.llm.providers[name] = {
          api_base: get("api_base"),
          model: get("model"),
          api_key_env: get("api_key_env")
        };
        const key = get("api_key");
        if (key) config.llm.providers[name].api_key = key;
        else delete config.llm.providers[name].api_key;
      });
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
    }

    function inlineMarkdown(text) {
      return escapeHtml(text)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    }

    function renderMarkdown(markdown) {
      const lines = String(markdown || "").split(/\r?\n/);
      const html = [];
      let listOpen = false;
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (!line.trim()) {
          if (listOpen) { html.push("</ul>"); listOpen = false; }
          continue;
        }
        if (/^\|.+\|$/.test(line.trim()) && i + 1 < lines.length && /^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(lines[i + 1].trim())) {
          if (listOpen) { html.push("</ul>"); listOpen = false; }
          const headers = line.trim().slice(1, -1).split("|").map(c => inlineMarkdown(c.trim()));
          i += 2;
          const rows = [];
          while (i < lines.length && /^\|.+\|$/.test(lines[i].trim())) {
            rows.push(lines[i].trim().slice(1, -1).split("|").map(c => inlineMarkdown(c.trim())));
            i++;
          }
          i--;
          html.push("<table><thead><tr>" + headers.map(h => `<th>${h}</th>`).join("") + "</tr></thead><tbody>");
          rows.forEach(row => html.push("<tr>" + row.map(c => `<td>${c}</td>`).join("") + "</tr>"));
          html.push("</tbody></table>");
          continue;
        }
        const heading = line.match(/^(#{1,3})\s+(.+)$/);
        if (heading) {
          if (listOpen) { html.push("</ul>"); listOpen = false; }
          const level = heading[1].length;
          html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
          continue;
        }
        const bullet = line.match(/^-\s+(.+)$/);
        if (bullet) {
          if (!listOpen) { html.push("<ul>"); listOpen = true; }
          html.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
          continue;
        }
        if (listOpen) { html.push("</ul>"); listOpen = false; }
        html.push(`<p>${inlineMarkdown(line)}</p>`);
      }
      if (listOpen) html.push("</ul>");
      return html.join("\n");
    }

    function showReport(markdown) {
      $("preview").innerHTML = renderMarkdown(markdown || "未找到日报。");
    }

    async function loadConfig() {
      const data = await api("/api/config");
      config = data.config;
      renderConfig();
      await refreshTask();
      await health();
    }

    async function saveConfig() {
      collectConfig();
      await api("/api/config", {method: "POST", body: JSON.stringify({config})});
      setMessage("配置已保存。");
    }

    async function health() {
      try {
        const data = await api("/api/health");
        $("awStatus").textContent = data.activitywatch ? "ActivityWatch 已连接" : "ActivityWatch 未连接";
      } catch (err) {
        $("awStatus").textContent = "ActivityWatch 未连接";
      }
    }

    async function refreshTask() {
      const data = await api("/api/schedule/status");
      $("taskStatus").textContent = data.status || "未安装";
    }

    document.querySelectorAll(".tab").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
        document.querySelectorAll("section").forEach(s => s.classList.remove("active"));
        btn.classList.add("active");
        $(btn.dataset.tab).classList.add("active");
      });
    });

    $("reloadConfig").onclick = () => loadConfig().then(() => setMessage("已重新读取配置。")).catch(e => setMessage(e.message));
    $("report_date").addEventListener("change", updateReportTarget);
    $("addProvider").onclick = async (e) => {
      setBusy(e.target, true);
      collectConfig();
      try {
        const name = $("new_provider_name").value.trim();
        if (!/^[a-zA-Z0-9_-]{2,40}$/.test(name)) {
          setMessage("provider 名称只能包含字母、数字、下划线和短横线，长度 2-40。");
          return;
        }
        config.llm = config.llm || {};
        config.llm.providers = config.llm.providers || {};
        if (config.llm.providers[name]) {
          setMessage(`provider 已存在：${name}`);
          return;
        }
        const keyEnv = $("new_provider_key_env").value.trim() || `${name.toUpperCase().replace(/-/g, "_")}_API_KEY`;
        const provider = {
          api_base: $("new_provider_base").value.trim(),
          model: $("new_provider_model").value.trim(),
          api_key_env: keyEnv
        };
        const directKey = $("new_provider_key").value.trim();
        if (directKey) provider.api_key = directKey;
        if (!provider.api_base || !provider.model) {
          setMessage("新增 provider 需要填写 API Base 和模型。");
          return;
        }
        config.llm.providers[name] = provider;
        config.llm.provider = name;
        $("new_provider_name").value = "";
        $("new_provider_base").value = "";
        $("new_provider_model").value = "";
        $("new_provider_key_env").value = "";
        $("new_provider_key").value = "";
        renderProviders();
        refreshProviderControls();
        $("llm_provider").value = name;
        await saveConfig();
        setMessage(`已添加并保存 provider：${name}`);
      } catch (err) {
        setMessage(err.message);
      } finally {
        setBusy(e.target, false);
      }
    };
    $("saveGeneral").onclick = async (e) => { setBusy(e.target, true); try { await saveConfig(); } catch (err) { setMessage(err.message); } finally { setBusy(e.target, false); } };
    $("saveLlm").onclick = async (e) => { setBusy(e.target, true); try { await saveConfig(); } catch (err) { setMessage(err.message); } finally { setBusy(e.target, false); } };
    $("saveAutomation").onclick = async (e) => {
      setBusy(e.target, true);
      try {
        await saveConfig();
        const data = await api("/api/schedule/apply", {method: "POST", body: JSON.stringify({schedule: config.schedule})});
        $("taskStatus").textContent = data.status;
        setMessage("自动任务已应用。");
      } catch (err) { setMessage(err.message); } finally { setBusy(e.target, false); }
    };
    $("refreshTask").onclick = () => refreshTask().catch(e => setMessage(e.message));
    $("deleteTask").onclick = async (e) => {
      setBusy(e.target, true);
      try {
        await api("/api/schedule/delete", {method: "POST", body: "{}"});
        config.schedule = config.schedule || {};
        config.schedule.enabled = false;
        renderConfig();
        await saveConfig();
        await refreshTask();
        setMessage("自动任务已删除。");
      } catch (err) { setMessage(err.message); } finally { setBusy(e.target, false); }
    };
    $("testLlm").onclick = async (e) => {
      setBusy(e.target, true);
      try {
        await saveConfig();
        const data = await api("/api/llm/test", {method: "POST", body: JSON.stringify({provider: $("llm_provider").value})});
        setMessage(data.message);
      } catch (err) { setMessage(err.message); } finally { setBusy(e.target, false); }
    };
    $("generateReport").onclick = async (e) => {
      setBusy(e.target, true);
      try {
        await saveConfig();
        const targetDate = resolveReportDateValue($("report_date").value);
        const data = await api("/api/report/generate", {method: "POST", body: JSON.stringify({
          date: targetDate,
          llm: $("report_llm").value,
          provider: $("report_provider").value
        })});
        showReport(data.content);
        setMessage(`日报已生成：${data.path}（目标日期：${targetDate}）`);
      } catch (err) { setMessage(err.message); } finally { setBusy(e.target, false); }
    };
    $("loadLatest").onclick = async () => {
      try {
        const data = await api("/api/report/latest");
        showReport(data.content || "未找到日报。");
        setMessage(data.path ? `已读取：${data.path}` : "未找到日报。");
      } catch (err) { setMessage(err.message); }
    };
    $("openReports").onclick = async () => {
      try {
        await api("/api/reports/open", {method: "POST", body: "{}"});
        setMessage("已打开日报文件夹。");
      } catch (err) { setMessage(err.message); }
    };

    loadConfig().catch(err => setMessage(err.message));
  </script>
</body>
</html>
"""


def merged_config() -> Dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    if CONFIG_PATH.exists():
        user_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        deep_update(config, user_config)
        user_providers = user_config.get("llm", {}).get("providers")
        if isinstance(user_providers, dict):
            config.setdefault("llm", {})["providers"] = user_providers
    config.setdefault("schedule", {"enabled": False, "time": "23:55", "report_date": "today", "llm": "auto", "provider": "", "silent": True})
    return config


def write_config(config: Dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if not length:
        return {}
    if length > MAX_REQUEST_BYTES:
        raise ValueError("Request body is too large.")
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def run_command(args: list[str], timeout: int = 120) -> Tuple[int, str]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
        shell=False,
    )
    output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
    return proc.returncode, output


def powershell(command: str, timeout: int = 60) -> Tuple[int, str]:
    return run_command(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], timeout=timeout)


def is_allowed_host_header(host_header: str) -> bool:
    raw = (host_header or "").strip().lower()
    if raw.startswith("[") and "]" in raw:
        host = raw[1:raw.index("]")]
    else:
        host = raw.split(":", 1)[0]
    return host in ALLOWED_HOSTS


def schedule_status() -> str:
    code, out = powershell(
        f"$task = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue; "
        "if ($null -eq $task) { '未安装' } else { "
        "$info = Get-ScheduledTaskInfo -TaskName $task.TaskName; "
        "'状态: ' + $task.State + \"`n上次运行: \" + $info.LastRunTime + \"`n下次运行: \" + $info.NextRunTime + \"`n上次结果: \" + $info.LastTaskResult }"
    )
    return out if code == 0 else out or "无法读取任务状态"


def schedule_status_for_config(config: Dict[str, Any]) -> str:
    status = schedule_status()
    if config.get("schedule", {}).get("enabled") and "未安装" in status:
        status += "\n配置中已启用，但系统任务尚未安装。请点击“保存并应用任务”。"
    latest_log = ROOT / "logs" / "latest.log"
    if latest_log.exists():
        try:
            lines = latest_log.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(lines[-8:])
            status += f"\n\n最近任务日志：\n{tail}"
        except OSError:
            pass
    return status


def apply_schedule(schedule: Dict[str, Any]) -> str:
    if not schedule.get("enabled"):
        delete_schedule()
        return "未启用，已删除计划任务。"
    at = schedule.get("time") or "23:55"
    report_date = schedule.get("report_date") or "today"
    llm = schedule.get("llm") or "auto"
    provider = schedule.get("provider") or ""
    silent = bool(schedule.get("silent", True))
    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ROOT / "install_daily_task.ps1"),
        "-At",
        at,
        "-ReportDate",
        report_date,
        "-Llm",
        llm,
    ]
    if provider:
        args.extend(["-Provider", provider])
    if silent:
        args.append("-Silent")
    code, out = run_command(args)
    if code != 0:
        raise RuntimeError(out or "安装任务失败")
    return schedule_status()


def delete_schedule() -> str:
    code, out = powershell(f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue; '已删除或原本不存在。'")
    if code != 0:
        raise RuntimeError(out or "删除任务失败")
    return out


def open_reports_folder(config: Dict[str, Any]) -> str:
    output_dir = output_dir_from_config(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt" and hasattr(os, "startfile"):
        os.startfile(str(output_dir))
        return f"已打开: {output_dir}"
    code, out = run_command(["explorer", str(output_dir)])
    if code != 0:
        raise RuntimeError(out or "打开日报文件夹失败")
    return out or f"已打开: {output_dir}"


def check_activitywatch(config: Dict[str, Any]) -> bool:
    url = str(config.get("api_base", "http://127.0.0.1:5600/api/0")).rstrip("/") + "/buckets/"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def output_dir_from_config(config: Dict[str, Any]) -> Path:
    output_dir = Path(str(config.get("output_dir") or "reports"))
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    return output_dir


def latest_report(config: Dict[str, Any]) -> Tuple[str, str]:
    reports = sorted(output_dir_from_config(config).glob("*.md"), reverse=True)
    if not reports:
        return "", ""
    path = reports[0]
    return str(path), path.read_text(encoding="utf-8")


def report_path_for_date(config: Dict[str, Any], report_date: str) -> Path:
    tz = resolve_tz(str(config.get("timezone", "Asia/Shanghai")))
    today = datetime.now(tz).date()
    if report_date == "today":
        day = today
    elif report_date == "yesterday":
        day = today - timedelta(days=1)
    else:
        day = datetime.fromisoformat(report_date).date()
    return output_dir_from_config(config) / f"{day.isoformat()}.md"


def report_for_date(config: Dict[str, Any], report_date: str) -> Tuple[str, str]:
    path = report_path_for_date(config, report_date)
    if not path.exists():
        return str(path), ""
    return str(path), path.read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def reject_disallowed_host(self) -> bool:
        if is_allowed_host_header(self.headers.get("Host", "")):
            return False
        json_response(self, 403, {"ok": False, "error": "Host is not allowed. Use 127.0.0.1 or localhost."})
        return True

    def do_GET(self) -> None:
        try:
            if self.reject_disallowed_host():
                return
            if self.path in {"/", "/index.html"}:
                body = INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/api/config":
                json_response(self, 200, {"ok": True, "config": merged_config()})
                return
            if self.path == "/api/health":
                config = merged_config()
                json_response(self, 200, {"ok": True, "activitywatch": check_activitywatch(config)})
                return
            if self.path == "/api/schedule/status":
                json_response(self, 200, {"ok": True, "status": schedule_status_for_config(merged_config())})
                return
            if self.path == "/api/report/latest":
                path, content = latest_report(merged_config())
                json_response(self, 200, {"ok": True, "path": path, "content": content})
                return
            json_response(self, 404, {"ok": False, "error": "Not found"})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        try:
            if self.reject_disallowed_host():
                return
            payload = read_json(self)
            if self.path == "/api/config":
                config = payload.get("config")
                if not isinstance(config, dict):
                    json_response(self, 400, {"ok": False, "error": "config must be an object"})
                    return
                write_config(config)
                json_response(self, 200, {"ok": True})
                return
            if self.path == "/api/schedule/apply":
                status = apply_schedule(payload.get("schedule") or {})
                json_response(self, 200, {"ok": True, "status": status})
                return
            if self.path == "/api/schedule/delete":
                status = delete_schedule()
                json_response(self, 200, {"ok": True, "status": status})
                return
            if self.path == "/api/reports/open":
                message = open_reports_folder(merged_config())
                json_response(self, 200, {"ok": True, "message": message})
                return
            if self.path == "/api/report/generate":
                report_date = payload.get("date") or "today"
                llm = payload.get("llm") or "auto"
                provider = payload.get("provider") or ""
                args = [sys.executable, str(REPORT_SCRIPT), "--date", report_date, "--llm", llm, "--save-json"]
                if provider:
                    args.extend(["--provider", provider])
                code, out = run_command(args, timeout=240)
                if code != 0:
                    json_response(self, 500, {"ok": False, "error": out})
                    return
                path, content = report_for_date(merged_config(), report_date)
                if not content:
                    json_response(self, 500, {"ok": False, "error": f"Report was generated but not found at {path}. Command output:\n{out}"})
                    return
                json_response(self, 200, {"ok": True, "message": out, "path": path, "content": content})
                return
            if self.path == "/api/llm/test":
                config = load_config(CONFIG_PATH)
                provider_name = payload.get("provider") or config.get("llm", {}).get("provider")
                providers = config.get("llm", {}).get("providers", {})
                provider = providers.get(provider_name, {})
                api_base = str(provider.get("api_base", "")).rstrip("/")
                api_key = provider.get("api_key") or os.environ.get(str(provider.get("api_key_env", "")), "")
                if not api_base:
                    json_response(self, 400, {"ok": False, "error": "当前 provider 缺少 api_base"})
                    return
                if not api_key:
                    json_response(self, 400, {"ok": False, "error": "当前 provider 缺少 API Key 或环境变量"})
                    return
                json_response(self, 200, {"ok": True, "message": f"{provider_name} 配置已具备 api_base 和 API Key。实际生成日报时会进行模型调用。"})
                return
            json_response(self, 404, {"ok": False, "error": "Not found"})
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ActivityWatch Daily Reporter web console.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"ActivityWatch Daily Reporter UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
