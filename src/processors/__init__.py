"""Processor module proxies

This package re-exports processing classes from the legacy core module to
prepare for a staged migration into dedicated processor modules. Import
from src.processors to avoid depending on src.core.engine directly.
"""

from src.core.engine import Ingestor, PriceFetcher, NetworkRetry, StakeActivityCSVManager

__all__ = [
    "Ingestor",
    "PriceFetcher",
    "NetworkRetry",
    "StakeActivityCSVManager",
]
