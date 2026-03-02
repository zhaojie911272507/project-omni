# Project Omni — Docker image (CLI + WeCom/Feishu gateway, with Playwright)
# Use Playwright base image for browser tool support; fallback to python:3.12-slim for smaller image
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy AS base

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agent.py main.py server.py tools.py ./
COPY SOUL.md ./

# Browser tool (optional — app works without it)
COPY tools_browser.py ./
# Chromium already installed in Playwright base image

# Non-root user for security
RUN useradd -m -u 1000 omni && chown -R omni:omni /app
USER omni

EXPOSE 8000

# Default: run FastAPI gateway; override for CLI: python main.py
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
