"""Scheduler for Project Omni.

APScheduler-based定时任务 and proactive message推送.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from agent import tool

# ─────────────────────────────────────────────────────────────────────────────
# Scheduler Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────────────────────
# Scheduler Setup
# ─────────────────────────────────────────────────────────────────────────────

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APschedulerAvailable = True
except ImportError:
    APschedulerAvailable = False


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""
    id: str
    name: str
    description: str
    schedule: str  # cron, interval, or once
    cron: str | None = None  # cron expression
    interval_seconds: int | None = None  # for interval trigger
    task_type: str = "message"  # message, webhook, agent
    message: str | None = None
    webhook_url: str | None = None
    agent_prompt: str | None = None
    enabled: bool = True


class OmniScheduler:
    """Manages scheduled tasks for Project Omni."""

    def __init__(self):
        self.scheduler: AsyncIOScheduler | None = None
        self.tasks: dict[str, ScheduledTask] = {}
        self._scheduler_started = False

    def _ensure_scheduler(self) -> bool:
        """Ensure scheduler is initialized."""
        if not APschedulerAvailable:
            return False

        if not SCHEDULER_ENABLED:
            return False

        if self.scheduler is None:
            self.scheduler = AsyncIOScheduler()

        return True

    def start(self) -> bool:
        """Start the scheduler."""
        if not self._ensure_scheduler():
            return False

        if not self._scheduler_started:
            self.scheduler.start()
            self._scheduler_started = True

        return True

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler and self._scheduler_started:
            self.scheduler.shutdown()
            self._scheduler_started = False

    def add_task(self, task: ScheduledTask) -> str:
        """Add a scheduled task."""
        if not self._ensure_scheduler():
            return "Scheduler not available. Run: pip install apscheduler"

        # Store task
        self.tasks[task.id] = task

        if not task.enabled:
            return f"Task {task.id} added (disabled)"

        # Schedule based on type
        try:
            if task.cron:
                self.scheduler.add_job(
                    self._run_task,
                    CronTrigger.from_crontab(task.cron),
                    args=[task.id],
                    id=task.id,
                    name=task.name,
                )
            elif task.interval_seconds:
                self.scheduler.add_job(
                    self._run_task,
                    IntervalTrigger(seconds=task.interval_seconds),
                    args=[task.id],
                    id=task.id,
                    name=task.name,
                )
            else:
                return f"Invalid schedule for task {task.id}"

            return f"Task {task.id} scheduled: {task.name}"
        except Exception as exc:  # noqa: BLE001
            return f"Error scheduling task: {exc}"

    def remove_task(self, task_id: str) -> str:
        """Remove a scheduled task."""
        if task_id in self.tasks:
            del self.tasks[task_id]

        if self.scheduler:
            self.scheduler.remove_job(task_id)

        return f"Task {task_id} removed"

    async def _run_task(self, task_id: str) -> None:
        """Execute a scheduled task."""
        task = self.tasks.get(task_id)
        if not task:
            return

        if task.task_type == "message":
            # For now, just log - in production would send to IM
            print(f"[Scheduler] Running task {task_id}: {task.message}")
        elif task.task_type == "webhook" and task.webhook_url:
            import httpx

            async with httpx.AsyncClient() as client:
                await client.post(
                    task.webhook_url,
                    json={"task": task.name, "time": datetime.utcnow().isoformat()},
                )
        elif task.task_type == "agent" and task.agent_prompt:
            from agent import Agent

            agent = Agent(model=os.getenv("OMNI_MODEL", "gpt-4o-mini"))
            await agent.chat(task.agent_prompt)

    def list_tasks(self) -> list[dict]:
        """List all scheduled tasks."""
        return [
            {
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "schedule": task.schedule,
                "cron": task.cron,
                "interval_seconds": task.interval_seconds,
                "task_type": task.task_type,
                "enabled": task.enabled,
            }
            for task in self.tasks.values()
        ]

    def get_jobs(self) -> list[dict]:
        """Get current scheduler jobs."""
        if not self.scheduler:
            return []

        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in self.scheduler.get_jobs()
        ]


# Global scheduler
_scheduler: OmniScheduler | None = None


def get_scheduler() -> OmniScheduler:
    """Get or create scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = OmniScheduler()
    return _scheduler


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler Tools
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="scheduler_start",
    description="Start the scheduler service.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def scheduler_start() -> str:
    """Start the scheduler."""
    scheduler = get_scheduler()
    success = scheduler.start()

    if success:
        return "Scheduler started"
    return "Failed to start scheduler. Check if SCHEDULER_ENABLED=true in .env"


@tool(
    name="scheduler_stop",
    description="Stop the scheduler service.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def scheduler_stop() -> str:
    """Stop the scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()
    return "Scheduler stopped"


@tool(
    name="scheduler_add_task",
    description="Add a scheduled task.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Task name"},
            "description": {"type": "string", "description": "Task description"},
            "schedule": {
                "type": "string",
                "description": "Schedule type: cron, interval, once",
                "enum": ["cron", "interval", "once"],
            },
            "cron": {
                "type": "string",
                "description": "Cron expression (e.g., '0 9 * * *' for daily 9am)",
            },
            "interval_seconds": {
                "type": "integer",
                "description": "Interval in seconds",
            },
            "task_type": {
                "type": "string",
                "description": "Task type: message, webhook, agent",
                "enum": ["message", "webhook", "agent"],
            },
            "message": {
                "type": "string",
                "description": "Message to send (for message type)",
            },
            "webhook_url": {
                "type": "string",
                "description": "Webhook URL (for webhook type)",
            },
            "agent_prompt": {
                "type": "string",
                "description": "Prompt for agent (for agent type)",
            },
        },
        "required": ["name", "schedule", "task_type"],
    },
)
def scheduler_add_task(
    name: str,
    description: str = "",
    schedule: str = "cron",
    cron: str | None = None,
    interval_seconds: int | None = None,
    task_type: str = "message",
    message: str | None = None,
    webhook_url: str | None = None,
    agent_prompt: str | None = None,
) -> str:
    """Add a scheduled task."""
    import uuid

    task_id = str(uuid.uuid4())[:8]

    task = ScheduledTask(
        id=task_id,
        name=name,
        description=description,
        schedule=schedule,
        cron=cron,
        interval_seconds=interval_seconds,
        task_type=task_type,
        message=message,
        webhook_url=webhook_url,
        agent_prompt=agent_prompt,
    )

    scheduler = get_scheduler()
    return scheduler.add_task(task)


@tool(
    name="scheduler_remove_task",
    description="Remove a scheduled task by ID.",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID to remove"},
        },
        "required": ["task_id"],
    },
)
def scheduler_remove_task(task_id: str) -> str:
    """Remove a scheduled task."""
    scheduler = get_scheduler()
    return scheduler.remove_task(task_id)


@tool(
    name="scheduler_list_tasks",
    description="List all scheduled tasks.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def scheduler_list_tasks() -> str:
    """List scheduled tasks."""
    scheduler = get_scheduler()
    tasks = scheduler.list_tasks()

    if not tasks:
        return "No scheduled tasks"

    output = "Scheduled Tasks:\n\n"
    for task in tasks:
        schedule_info = task.get("cron") or f"{task.get('interval_seconds')}s"
        output += f"- {task['name']} ({task['id']})\n"
        output += f"  Schedule: {task['schedule']} - {schedule_info}\n"
        output += f"  Type: {task['task_type']}\n"
        output += f"  Enabled: {task['enabled']}\n\n"

    return output


@tool(
    name="scheduler_status",
    description="Get scheduler status and jobs.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def scheduler_status() -> str:
    """Get scheduler status."""
    if not APschedulerAvailable:
        return "APScheduler not installed. Run: pip install apscheduler"

    scheduler = get_scheduler()

    output = f"Scheduler Status:\n"
    output += f"- Enabled: {SCHEDULER_ENABLED}\n"
    output += f"- Running: {scheduler._scheduler_started}\n"

    jobs = scheduler.get_jobs()
    if jobs:
        output += "\nActive Jobs:\n"
        for job in jobs:
            output += f"- {job['name']}: {job.get('next_run', 'N/A')}\n"
    else:
        output += "\nNo active jobs"

    return output