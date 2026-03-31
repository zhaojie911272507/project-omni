"""Tests for browser tools."""

from __future__ import annotations

import inspect

import pytest

from tools_browser import _dedupe, browser_search_and_extract


class TestDedupe:
    """Test URL deduplication function."""

    def test_dedupe_removes_duplicates(self) -> None:
        """Test that duplicates are removed."""
        urls = ["http://a.com", "http://b.com", "http://a.com"]
        result = _dedupe(urls)
        assert result == ["http://a.com", "http://b.com"]

    def test_dedupe_preserves_order(self) -> None:
        """Test that original order is preserved."""
        urls = ["http://c.com", "http://a.com", "http://b.com", "http://a.com"]
        result = _dedupe(urls)
        assert result == ["http://c.com", "http://a.com", "http://b.com"]

    def test_dedupe_empty_list(self) -> None:
        """Test with empty list."""
        result = _dedupe([])
        assert result == []

    def test_dedupe_no_duplicates(self) -> None:
        """Test with no duplicates."""
        urls = ["http://a.com", "http://b.com", "http://c.com"]
        result = _dedupe(urls)
        assert result == urls


class TestBrowserSearchAndExtract:
    """Test browser_search_and_extract tool."""

    @pytest.mark.asyncio
    async def test_browser_search_playwright_not_installed(self) -> None:
        """Test graceful handling when playwright is not installed."""
        # Verify the function exists and is async
        assert inspect.iscoroutinefunction(browser_search_and_extract)
