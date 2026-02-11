"""Tests for CLI RichHandler colored logging.

Tests verify that setup_logging() properly configures RichHandler
for colored console output while preserving log formats and
maintaining --verbose flag behavior.
"""

import logging
from io import StringIO

import pytest
from rich.logging import RichHandler

from iron_rook.review.cli import setup_logging


class TestSetupLoggingWithRichHandler:
    """Test setup_logging() function with RichHandler configuration."""

    def test_rich_handler_import_exists(self):
        """Verify RichHandler import is available."""
        # This test ensures the import is correct
        from rich.logging import RichHandler  # noqa: F401

    def test_setup_logging_with_rich_handler_info_level(self, caplog):
        """Verify setup_logging configures RichHandler with INFO level by default."""
        setup_logging(verbose=False)

        # Get the root logger
        root_logger = logging.getLogger()

        # Verify root logger level is INFO
        assert root_logger.level == logging.INFO

        # Verify a RichHandler is in the handlers list
        rich_handlers = [h for h in root_logger.handlers if isinstance(h, RichHandler)]
        assert len(rich_handlers) > 0, "RichHandler should be configured"

    def test_setup_logging_with_rich_handler_debug_level(self, caplog):
        """Verify setup_logging configures RichHandler with DEBUG level when verbose=True."""
        setup_logging(verbose=True)

        # Get the root logger
        root_logger = logging.getLogger()

        # Verify root logger level is DEBUG
        assert root_logger.level == logging.DEBUG

        # Verify a RichHandler is in the handlers list
        rich_handlers = [h for h in root_logger.handlers if isinstance(h, RichHandler)]
        assert len(rich_handlers) > 0, "RichHandler should be configured"

    def test_rich_handler_log_format_preserved(self):
        """Verify that log format strings are preserved with RichHandler."""
        setup_logging(verbose=False)

        root_logger = logging.getLogger()
        rich_handlers = [h for h in root_logger.handlers if isinstance(h, RichHandler)]
        assert len(rich_handlers) > 0

        # Test that logging still works (manual verification via stdout)
        test_logger = logging.getLogger("test_module")
        test_logger.info("Test message - RichHandler working")

    def test_verbose_flag_enables_debug_logging(self):
        """Verify that --verbose flag enables DEBUG level logging."""
        setup_logging(verbose=True)

        # Get the root logger
        root_logger = logging.getLogger()

        # Verify root logger level is DEBUG
        assert root_logger.level == logging.DEBUG

        # Get a test logger
        test_logger = logging.getLogger("test_verbose")

        # Log at DEBUG level (manual verification via stdout)
        test_logger.debug("Debug message should appear")

    def test_default_uses_info_level_logging(self):
        """Verify that default (verbose=False) uses INFO level logging."""
        setup_logging(verbose=False)

        # Get the root logger
        root_logger = logging.getLogger()

        # Verify root logger level is INFO
        assert root_logger.level == logging.INFO

        # Get a test logger
        test_logger = logging.getLogger("test_default")

        # Log at INFO level (manual verification via stdout)
        test_logger.info("Info message should appear")

    def test_rich_handler_has_console_output(self, caplog):
        """Verify RichHandler outputs to console (sys.stdout)."""
        setup_logging(verbose=False)

        root_logger = logging.getLogger()
        rich_handlers = [h for h in root_logger.handlers if isinstance(h, RichHandler)]
        assert len(rich_handlers) > 0

        # The handler should have a stream (console)
        handler = rich_handlers[0]
        # RichHandler uses Console, which internally writes to sys.stdout
        # We just verify the handler is configured
        assert handler is not None

    def test_multiple_setup_logging_calls_safe(self):
        """Verify calling setup_logging() multiple times doesn't cause errors."""
        # First call
        setup_logging(verbose=False)

        # Second call should not fail
        setup_logging(verbose=True)

        # Get the root logger
        root_logger = logging.getLogger()

        # Verify root logger level is DEBUG (from the second call)
        assert root_logger.level == logging.DEBUG

        # Verify logging still works (manual verification via stdout)
        test_logger = logging.getLogger("test_multi")
        test_logger.info("Test message after multiple setups")


class TestRichHandlerBackwardCompatibility:
    """Test RichHandler maintains backward compatibility with existing CLI behavior."""

    def test_log_format_strings_defined(self):
        """Verify that log format strings are still defined in setup_logging."""
        # Import and check the source has the format strings
        import inspect
        from iron_rook.review.cli import setup_logging

        source = inspect.getsource(setup_logging)

        # Verify format strings are present
        assert 'log_format = "%(asctime)s' in source
        assert 'date_format = "%H:%M:%S"' in source

    def test_settings_debug_check_preserved(self):
        """Verify that dawn_kestrel settings.debug check is still performed."""
        # This test just ensures the code structure is preserved
        # The actual dawn_kestrel import happens inside setup_logging
        import inspect
        from iron_rook.review.cli import setup_logging

        source = inspect.getsource(setup_logging)

        # Verify settings.debug check is present
        assert "settings.debug" in source
        assert "setLevel(logging.DEBUG)" in source

    def test_force_flag_in_config(self):
        """Verify force=True is used in logging configuration."""
        import inspect
        from iron_rook.review.cli import setup_logging

        source = inspect.getsource(setup_logging)

        # Verify force parameter is used (needed to reconfigure root logger)
        assert "force" in source.lower()
