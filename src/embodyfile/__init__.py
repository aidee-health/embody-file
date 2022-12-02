"""Initialize the embodyfile package."""
import importlib.metadata


try:
    __version__ = importlib.metadata.version("embody-file")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"
