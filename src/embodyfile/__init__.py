"""Initialize the embodyfile package."""

import importlib.metadata
import logging

# Configure NullHandler by default to prevent unwanted logging output
_library_logger = logging.getLogger("embodyfile")
if not _library_logger.handlers:
    _library_logger.addHandler(logging.NullHandler())


try:
    __version__ = importlib.metadata.version("embody-file")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"
