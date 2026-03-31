"""Tests for built-in tools."""

from __future__ import annotations

from pathlib import Path

from tools import read_file, shell_exec, write_file


class TestShellExec:
    """Test shell_exec tool."""

    def test_shell_exec_echo(self) -> None:
        """Test executing echo command."""
        result = shell_exec("echo 'Hello World'")
        assert "Hello World" in result
        assert "[exit_code=" not in result or "[exit_code=0]" in result

    def test_shell_exec_ls(self) -> None:
        """Test executing ls command."""
        result = shell_exec("ls -la")
        assert "total" in result or "drwx" in result

    def test_shell_exec_invalid_command(self) -> None:
        """Test executing invalid command."""
        result = shell_exec("nonexistent_command_xyz_123")
        assert "[exit_code=" in result or "not found" in result.lower()

    def test_shell_exec_with_stderr(self) -> None:
        """Test command that produces stderr output."""
        result = shell_exec("ls /nonexistent/path 2>&1")
        # Should contain error info
        assert len(result) > 0


class TestReadFile:
    """Test read_file tool."""

    def test_read_file_existing(self, temp_file: Path) -> None:
        """Test reading an existing file."""
        result = read_file(str(temp_file))
        assert "test content" in result

    def test_read_file_nonexistent(self) -> None:
        """Test reading a non-existent file."""
        result = read_file("/nonexistent/path/file.txt")
        assert "[error]" in result

    def test_read_file_empty(self, tmp_path: Path) -> None:
        """Test reading an empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        result = read_file(str(empty_file))
        assert result == ""


class TestWriteFile:
    """Test write_file tool."""

    def test_write_file_new(self, tmp_path: Path) -> None:
        """Test writing to a new file."""
        new_file = tmp_path / "new_file.txt"
        content = "Hello, World!"
        result = write_file(str(new_file), content)

        assert "wrote" in result
        assert str(len(content)) in result
        assert new_file.read_text() == content

    def test_write_file_overwrite(self, temp_file: Path) -> None:
        """Test overwriting an existing file."""
        new_content = "New content"
        result = write_file(str(temp_file), new_content)

        assert "wrote" in result
        assert temp_file.read_text() == new_content

    def test_write_file_create_directories(self, tmp_path: Path) -> None:
        """Test that write_file creates parent directories."""
        nested_file = tmp_path / "subdir" / "nested" / "file.txt"
        content = "Nested content"
        result = write_file(str(nested_file), content)

        assert "wrote" in result
        assert nested_file.read_text() == content

    def test_write_file_permission_error(self) -> None:
        """Test writing to a protected path."""
        result = write_file("/root/protected_file.txt", "content")
        assert "[error]" in result


class TestToolIntegration:
    """Test tools working together."""

    def test_write_then_read(self, tmp_path: Path) -> None:
        """Test writing a file and reading it back."""
        test_file = tmp_path / "test.txt"
        content = "Test content for integration"

        write_result = write_file(str(test_file), content)
        assert "wrote" in write_result

        read_result = read_file(str(test_file))
        assert read_result == content

    def test_shell_exec_file_operation(self, tmp_path: Path) -> None:
        """Test using shell to operate on files."""
        test_file = tmp_path / "shell_test.txt"
        test_file.write_text("shell test content")

        # Use cat to read the file
        result = shell_exec(f"cat {test_file}")
        assert "shell test content" in result
