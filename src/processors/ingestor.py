"""Compatibility wrapper for Ingestor.

The Ingestor remains implemented in src.core.engine; this module exposes it
through the processors namespace to begin migration toward dedicated processor
modules without breaking existing imports.
"""

from src.core.engine import Ingestor

__all__ = ["Ingestor"]
