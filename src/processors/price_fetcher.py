"""Compatibility wrapper for PriceFetcher.

PriceFetcher is still implemented in src.core.engine; this module re-exports it
for callers expecting processor-specific modules.
"""

from src.core.engine import PriceFetcher

__all__ = ["PriceFetcher"]
