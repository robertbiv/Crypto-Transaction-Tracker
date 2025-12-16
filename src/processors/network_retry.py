"""Compatibility wrapper for NetworkRetry.

NetworkRetry remains defined in src.core.engine. Importing from this module
keeps future refactors contained within the processors namespace.
"""

from src.core.engine import NetworkRetry

__all__ = ["NetworkRetry"]
