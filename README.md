# ActivityWatch Daily Reporter

ActivityWatch Daily Reporter 是一个基于 [ActivityWatch](https://activitywatch.net/) 本地数据的每日电脑使用日报工具。它会读取本机 `aw-server` API，统计应用、窗口、空闲时间和使用节奏，并生成 Markdown 日报。你也可以选择接入兼容 OpenAI Chat Completions 的大模型，让日报结合历史记录做更细的复盘。

项目只依赖 Python 标准库，不需要安装 npm 包或 Python 第三方库。

## 功能

- 从 ActivityWatch 本地 API 读取窗口记录和 AFK 空闲记录
- 生成每日 Markdown 日报和可选 JSON 结构化数据
- 按应用、类别、窗口标题和小时分布统计使用时间
- 自动扣除 AFK 时间，避免离开电脑时的窗口停留被误算为活跃使用
- 提供本地 Web 控制台，用于配置、生成、预览和自动化日报
- 可选 LLM 增强总结，支持 OpenAI-compatible API
- 支持 Windows 任务计划程序每日自动生成日报

## 适用环境

- Windows 10/11
- Python 3.9+
- ActivityWatch 正在运行

默认读取：

```text
http://127.0.0.1:5600/api/0
```

## 快速开始

1. 克隆或下载本项目。
2. 确保 ActivityWatch 正在运行。
3. 复制示例配置：

```powershell
Copy-Item .\activity_report_config.example.json .\activity_report_config.json
```

4. 启动 Web 控制台：

```powershell
.\start_web_ui.bat
```

浏览器会打开：

```text
http://127.0.0.1:8765
```

也可以手动启动：

```powershell
python .\web_ui.py
```

## 命令行使用

生成今天的日报：

```powershell
python .\activity_daily_report.py --date today --print
```

生成昨天的日报：

```powershell
python .\activity_daily_report.py --date yesterday
```

生成指定日期：

```powershell
python .\activity_daily_report.py --date 2026-05-26
```

同时保存结构化 JSON：

```powershell
python .\activity_daily_report.py --date today --save-json
```

默认输出到：

```text
reports/YYYY-MM-DD.md
reports/YYYY-MM-DD.json
```

## Web 控制台

Web 控制台可以完成：

- 修改 ActivityWatch API、日报输出目录、统计时间范围
- 设置分类规则、深度工作应用、分心关键词
- 开关 LLM 增强
- 新增、删除和测试 LLM provider
- 设置 Windows 每日自动任务
- 手动生成今天或昨天的日报
- 在页面内以 Markdown 形式预览日报
- 打开日报输出文件夹查看历史日报

控制台默认只监听本机：

```text
127.0.0.1:8765
```

不要把它绑定到公网地址。控制台可以修改本地配置、创建 Windows 计划任务，并可能保存 API Key。

## LLM 增强

默认不启用 LLM，不配置 API Key 也可以正常生成基础日报。

临时启用：

```powershell
python .\activity_daily_report.py --date today --llm on --provider deepseek
```

在 Web 控制台中启用后，默认 `--llm auto` 会跟随配置。

内置 provider 示例：

- `openai`
- `deepseek`
- `qwen`
- `zhipu`
- `moonshot`
- `openrouter`
- `ollama`

也可以在 Web 控制台新增任何兼容 OpenAI Chat Completions 的服务，例如 SiliconFlow、NVIDIA、OpenAI-compatible 私有代理等。

推荐使用环境变量保存 API Key：

```powershell
$env:DEEPSEEK_API_KEY = "your-api-key"
```

也可以在 Web 控制台直接填写 API Key，但这会写入本地 `activity_report_config.json`。不要把这个文件提交到 GitHub。

“创意程度”对应大模型 API 的 `temperature` 参数：

- `0-0.3`：更稳定，更适合日报
- `0.4-0.7`：表达更灵活
- `0.8+`：更发散，更适合头脑风暴

## Windows 自动化

通过 Web 控制台的“自动化”页可以启用每日任务。

也可以直接使用脚本：

```powershell
.\install_daily_task.ps1 -At 23:55 -ReportDate today -Silent
```

每天早上生成昨天的日报：

```powershell
.\install_daily_task.ps1 -At 08:30 -ReportDate yesterday
```

自动任务启用 LLM：

```powershell
.\install_daily_task.ps1 -At 23:55 -ReportDate today -Llm on -Provider deepseek
```

如果不希望静默运行，可以去掉 `-Silent`。非静默模式会显示执行窗口，并在完成后短暂停留，方便确认是否生成成功。

无副作用预览任务命令：

```powershell
.\install_daily_task.ps1 -At 23:55 -ReportDate today -Llm auto -Provider deepseek -Silent -Preview
```

计划任务实际运行的是 `run_daily_report.ps1`，它会把每次执行日志写入：

```text
logs/latest.log
logs/daily-report-YYYYMMDD-HHMMSS.log
```

如果任务窗口一闪而过但没有生成日报，请先查看 `logs/latest.log`。如果启用了 LLM 但模型调用失败，工具仍会生成基础日报，并在日报的“大模型增强分析”部分写明失败原因。

## 配置文件

本地配置文件：

```text
activity_report_config.json
```

示例配置：

```text
activity_report_config.example.json
```

常用配置项：

- `api_base`：ActivityWatch API 地址
- `timezone`：统计时区
- `output_dir`：日报输出目录
- `category_rules`：按应用名或窗口标题关键词归类
- `focus_apps`：计入深度工作/创作工具的应用
- `distracting_keywords`：计入可能分心内容的标题关键词
- `llm.enabled`：是否启用 LLM
- `llm.providers`：多模型 provider 配置
- `schedule`：Windows 每日任务配置

## 隐私与安全

ActivityWatch 数据包含应用名、窗口标题和网页标题，可能暴露个人隐私。使用 LLM 增强时，脚本会把当天统计数据和最近历史日报发送给你配置的模型服务。

建议：

- 默认先关闭 LLM，确认基础日报符合预期后再启用
- 优先通过环境变量保存 API Key
- 不要提交 `activity_report_config.json`
- 不要提交 `reports/`
- 不要把 Web 控制台暴露到公网
- 开源前检查是否有真实 API Key 或私人日报

本项目的 `.gitignore` 已默认忽略：

```text
activity_report_config.json
reports/
logs/
__pycache__/
```

## 数据来源

脚本会自动选择最近更新的：

- `currentwindow` / `aw-watcher-window` bucket
- `afkstatus` / `aw-watcher-afk` bucket

如果 ActivityWatch 端口不是默认的 `5600`，请在 Web 控制台或配置文件中修改 `api_base`。

## 项目文件

- `activity_daily_report.py`：日报生成核心逻辑
- `web_ui.py`：本地 Web 控制台
- `install_daily_task.ps1`：Windows 计划任务安装脚本
- `run_daily_report.ps1`：计划任务运行 wrapper，负责写日志和调用日报脚本
- `start_web_ui.bat`：Windows 一键启动器
- `start_web_ui.ps1`：PowerShell 启动器
- `activity_report_config.example.json`：示例配置

## 开源前检查清单

- `activity_report_config.json` 未提交
- `reports/` 未提交
- 没有真实 API Key
- README 中的路径没有个人机器路径
- 使用 `python -m py_compile activity_daily_report.py web_ui.py` 检查语法
- 使用 `.\install_daily_task.ps1 -Preview` 检查任务命令
