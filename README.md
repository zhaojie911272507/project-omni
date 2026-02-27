# Project Omni

全天候、多终端接入的个人专属 AI Agent。融合 **Manus** 的深度自主执行能力与 **OpenClaw** 的全渠道私人化体验。

## Quick Start

```bash
# 1. 创建虚拟环境 & 安装依赖
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY（或其他 LiteLLM 支持的 Provider）

# 3. 启动 CLI 交互
python main.py
```

启动后直接在终端对话，Agent 会通过 ReAct 循环自动调用工具完成任务。

## Architecture

```
┌──────────────────────────────────────────────────┐
│                   Gateway Layer                  │
│   /webhook/wecom  ·  /webhook/feishu  ·  CLI     │
└────────────────────────┬─────────────────────────┘
                         │
                ┌────────▼────────┐
                │  Agent (ReAct)  │   ← agent.py
                │  LiteLLM router │
                └────────┬────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     tools.py    tools_browser.py    (future)
    shell_exec   browser_search    MCP / sandbox
    read_file    & extract
    write_file
```

| 文件 | 职责 |
|---|---|
| `agent.py` | ReAct 循环核心 + `@tool` 装饰器注册表 |
| `tools.py` | 基础工具：Shell 执行、文件读写 |
| `tools_browser.py` | Playwright 浏览器搜索 & 正文抽取 |
| `main.py` | CLI 入口 |
| `server.py` | FastAPI 网关：WeCom + 飞书 Webhook |
| `SOUL.md` | Agent 人格 & 用户偏好（自动注入 System Prompt） |

## Phase 1 — CLI Agent

```bash
python main.py                    # 默认 gpt-4o-mini
python main.py gpt-4o             # GPT-4o
python main.py deepseek/deepseek-chat  # DeepSeek
python main.py ollama/llama3      # 本地 Ollama
```

CLI 命令：
- 输入任意自然语言指令，Agent 自主推理并调用工具
- `/clear` — 重置对话上下文
- `exit` — 退出

### 注册自定义工具

```python
from agent import tool

@tool(
    name="my_tool",
    description="What this tool does",
    parameters={
        "type": "object",
        "properties": {
            "arg1": {"type": "string", "description": "..."},
        },
        "required": ["arg1"],
    },
)
def my_tool(arg1: str) -> str:
    return f"result: {arg1}"
```

在 `main.py` 或 `server.py` 中 `import` 即可自动注册。

## Phase 2 — IM 网关

### 企业微信 (WeCom)

1. 在 [企业微信管理后台](https://work.weixin.qq.com/) 创建自建应用
2. 配置 `.env` 中的 `WECOM_*` 变量
3. 启动服务：
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000
   ```
4. 设置回调 URL：`https://your-domain/webhook/wecom`

### 飞书 (Feishu / Lark)

1. 在 [飞书开放平台](https://open.feishu.cn/) 创建应用，开启「机器人」能力
2. 订阅事件：`im.message.receive_v1`
3. 配置 `.env` 中的 `FEISHU_*` 变量
4. 启动服务并设置事件回调 URL：`https://your-domain/webhook/feishu`

**流式回复体验**：收到消息后，Agent 先发送「⏳ Thinking...」占位消息，推理完成后原地更新为最终答案，模拟流式推送效果。

### 本地开发调试

如果没有公网域名，可使用 ngrok 暴露本地端口：

```bash
ngrok http 8000
# 将生成的 https://xxx.ngrok.io 填入 IM 平台的回调 URL
```

## Phase 3 — 浏览器搜索

```bash
# 首次使用需安装 Chromium
playwright install chromium
```

Agent 会在需要时自动调用 `browser_search_and_extract` 工具：

```
You > 帮我搜索一下最近的 AI 行业大事件
  🔧 browser_search_and_extract(query='AI 行业 2026 大事件')
     --- [1] https://example.com ---
     ...content extracted...
```

底层使用 DuckDuckGo HTML 搜索 + Playwright 无头浏览器访问结果页面并抽取正文。

## Configuration

所有配置通过 `.env` 文件管理（参考 `.env.example`）：

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API Key |
| `ANTHROPIC_API_KEY` | Anthropic API Key（可选） |
| `DEEPSEEK_API_KEY` | DeepSeek API Key（可选） |
| `OMNI_MODEL` | 默认模型，如 `gpt-4o-mini` |
| `WECOM_CORP_ID` | 企业微信 Corp ID |
| `WECOM_APP_SECRET` | 企业微信应用 Secret |
| `WECOM_AGENT_ID` | 企业微信 Agent ID |
| `WECOM_TOKEN` | 企业微信回调 Token |
| `WECOM_ENCODING_AES_KEY` | 企业微信 AES Key（43 字符） |
| `FEISHU_APP_ID` | 飞书 App ID |
| `FEISHU_APP_SECRET` | 飞书 App Secret |
| `FEISHU_VERIFICATION_TOKEN` | 飞书 Verification Token |
| `FEISHU_ENCRYPT_KEY` | 飞书事件加密密钥（可选） |

## SOUL.md — 个性化

编辑项目根目录的 `SOUL.md` 来自定义 Agent 的人格和你的偏好：

```markdown
## 用户偏好
- 写 Python 时默认使用 Type Hint
- 回答尽量简洁
- 中文交流为主，技术术语保留英文
```

Agent 启动时会自动读取并注入 System Prompt。

## Tech Stack

- **LLM routing**: [LiteLLM](https://github.com/BerriAI/litellm) — 一套代码适配 OpenAI / Claude / DeepSeek / Ollama
- **Web framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Browser automation**: [Playwright](https://playwright.dev/python/)
- **Crypto**: [PyCryptodome](https://pycryptodome.readthedocs.io/) (WeCom & Feishu message encryption)

## License

Apache 2.0
