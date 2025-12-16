"""Compatibility wrapper for StakeTaxCSVManager.

StakeTaxCSVManager is still implemented in src.core.engine; this module makes it
available under src.processors for forward compatibility.
"""

from src.core.engine import StakeTaxCSVManager

__all__ = ["StakeTaxCSVManager"]
