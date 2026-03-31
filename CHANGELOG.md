# Changelog

All notable changes to Project Omni will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- MCP (Model Context Protocol) support for third-party integrations
- Memory system for long-term context retention
- Web UI dashboard for monitoring and management
- Multi-agent collaboration features
- Voice input support via Whisper

## [0.1.0] - 2026-03-31

### Added
- **Core Agent System**
  - ReAct (Reason + Act) loop implementation
  - Tool registration system with `@tool` decorator
  - LiteLLM integration for multi-provider support
  - SOUL.md for agent personality and user preferences

- **Built-in Tools**
  - `shell_exec` - Execute shell commands
  - `read_file` - Read file contents
  - `write_file` - Write/create files
  - `browser_search_and_extract` - Web search and content extraction

- **CLI Interface**
  - Interactive chat mode
  - Model selection via command line arguments
  - `/clear` command to reset context
  - Pretty-printed tool execution output

- **IM Gateway (Server)**
  - FastAPI-based webhook server
  - Enterprise WeChat (企业微信) integration
  - Feishu/Lark (飞书) integration with streaming-style replies
  - AES encryption support for message security

- **Deployment**
  - Docker support with Playwright base image
  - Docker Compose configuration
  - Health check endpoint (`/health`)

- **Documentation**
  - README.md with quick start guide
  - SOUL.md for agent personality
  - PRD documentation

### Fixed
- Browser tool gracefully handles Playwright import errors
- Message chunking for long responses in WeChat/Feishu

### Technical Stack
- **LLM Routing**: LiteLLM
- **Web Framework**: FastAPI
- **Browser Automation**: Playwright
- **Cryptography**: PyCryptodome

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.1.0 | 2026-03-31 | Initial release with Phase 1 (CLI) and Phase 2 (IM Gateway) features |
