"""Replica proxy package.

Expose FastAPI app at package level for easy testing/imports.
"""
from .main import app  # noqa: F401

__all__ = ("app",)
__version__ = "0.1.0"
