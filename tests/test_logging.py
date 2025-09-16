"""Test logging behavior for the embodyfile library."""

import io
import logging
from contextlib import redirect_stderr, redirect_stdout

from embodyfile.logging import get_logger


def test_library_silent_by_default():
    """Library should produce no output by default."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
        logger = get_logger("test_module")
        logger.info("This should not appear")
        logger.warning("This should not appear")
        logger.error("This should not appear")
        logger.debug("This should not appear")

    stdout_output = stdout_capture.getvalue()
    stderr_output = stderr_capture.getvalue()

    assert stdout_output == "", f"Expected no stdout output, got: {stdout_output}"
    assert stderr_output == "", f"Expected no stderr output, got: {stderr_output}"


def test_library_logging_when_configured():
    """Library should produce output when explicitly configured."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)

    embodyfile_logger = logging.getLogger("embodyfile")
    embodyfile_logger.handlers.clear()
    embodyfile_logger.addHandler(handler)
    embodyfile_logger.setLevel(logging.INFO)
    embodyfile_logger.propagate = False

    logger = get_logger("test_module")
    logger.info("This should appear")

    output = stream.getvalue()
    assert "This should appear" in output


def test_get_logger_hierarchy():
    """Test logger hierarchy is properly established."""
    root_logger = get_logger()
    module_logger = get_logger("test_module")

    assert root_logger.name == "embodyfile"
    assert module_logger.name == "embodyfile.test_module"
    assert module_logger.parent == root_logger
