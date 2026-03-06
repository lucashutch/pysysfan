"""pysysfan - Windows fan control daemon."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("pysysfan")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
