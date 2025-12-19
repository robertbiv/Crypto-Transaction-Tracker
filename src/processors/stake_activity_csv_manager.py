"""Compatibility wrapper for StakeActivityCSVManager.

StakeActivityCSVManager is still implemented in src.core.engine; this module makes it
available under src.processors for forward compatibility.
"""

from src.core.engine import StakeActivityCSVManager

__all__ = ["StakeActivityCSVManager"]
