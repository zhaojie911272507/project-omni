1. 产品愿景 (Product Vision)
构建一个全天候、多终端接入的个人专属 AI Agent。它既具备 Manus 那种极其强大的“深度自主执行与闭环”能力（接到任务后自己查网页、写代码、做报表），又拥有 OpenClaw 那种“无处不在、极度私人化”的体验（直接在微信/Telegram/Discord 里聊天，数据保留在本地，拥有持久化记忆）。

2. 核心优势融合 (Synergy)
吸收 Manus 的核心优势（深度执行力）：

“Do-it-for-me” 体验： 用户只需给出一个宏大目标（如：“帮我调研一下本周的 AI 行业动态并总结到 Notion”），Agent 会自动进行长程规划（Long-horizon planning），并在云端或本地沙盒中自动化操作浏览器和各类 API，直到完成任务。

自治纠错： 在执行过程中遇到报错（如网页改版、代码运行失败），能自主反思并尝试替代方案，而不是立刻停机报错。

吸收 OpenClaw 的核心优势（全渠道与本地掌控）：

无缝接入日常 IM： 抛弃独立的 App，将 Agent 接入 Telegram、Discord、Slack、飞书、企业微信 等日常聊天工具。用户在通勤路上发条语音，家里的 Agent 就开始干活。

个人心智模型（SOUL.md）： 使用极其简单的 Markdown 文件（如 MEMORY.md 和 SOUL.md）来定义 Agent 的性格、用户的偏好和长期上下文。

本地优先与隐私： 核心控制面（Gateway）在本地或个人 VPS 运行，结合 Ollama 支持本地大模型，确保隐私数据不外泄。

3. 核心机制设计 (Core Mechanisms)
3.1 Planning (规划与推理机制)
Agent 不应是简单的“一问一答”，而需要一套复杂任务的拆解引擎。

ReAct (Reason + Act) 循环： 每个任务进入后，强制 Agent 输出 Thought（我在想什么） -> Action（我要调什么工具） -> Observation（工具返回了什么）。

Plan-and-Solve (先计划后执行)： 面对复杂 Prompt，先生成一个多步骤的 Task List。每完成一步，打个勾，并根据结果动态调整后续步骤。

Vibecoding 指导（Prompt 设计）： 在系统提示词中，明确要求模型在调用终极回答工具前，必须穷尽验证步骤。

3.2 Tool Use (工具调用生态)
基础通信工具： 读写本地文件系统、执行 Shell 脚本。

Manus 级高阶工具： * Browser Use: 通过 Playwright/Puppeteer 提供的无头浏览器控制能力，让 Agent 能够“看”网页并点击。

Data Analytics: 内置 Python 沙盒执行环境（Jupyter kernel 或 Docker 沙盒），用于处理表格、生成图表。

MCP (Model Context Protocol) 支持： 拥抱标准化，通过 MCP 无缝接入 GitHub、Google Drive、Notion 等第三方生态。

3.3 记忆与状态管理 (Memory & State)
短期工作流记忆 (Working Memory)： 记录当前任务的执行链条，一旦任务完成即提炼。

长期人格记忆 (SOUL.md)： 将用户的喜好（如“我讨厌长篇大论”、“帮我写 Python 时默认使用 Type Hint”）作为全局 Context 注入。

4. 系统架构 (System Architecture)
采用模块化解耦架构，方便 AI 助手分批次生成代码：

Gateway Layer (网关接入层)：

负责接收来自 Telegram / Discord / WebUI / wechat / 飞书 的 Webhook 请求。

处理鉴权、限流、语音转文字（Whisper）。

Cognitive Engine (认知决策层)：

调度 LLM (如 Claude 3.5 Sonnet / GPT-4o / 本地 DeepSeek)。

运行 Planning 逻辑，维护对话历史窗口。

Action Sandbox (执行沙盒层)：

隔离执行 Agent 生成的 Python/Shell 代码。

挂载 tools/ 目录下的所有可用函数（Function Calling）。