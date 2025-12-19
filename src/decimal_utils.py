from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from typing import Any


# ============================================================================
# PRECISION CONSTANTS (IRS & Crypto Standards)
# ============================================================================

# Bitcoin precision (satoshi = 1e-8 BTC)
SATOSHI = Decimal('0.00000001')

# USD/fiat precision (cents)
USD_PRECISION = Decimal('0.01')

# Fee/Transaction percentage precision (basis points = 0.01%)
BASIS_POINT = Decimal('0.0001')

# Large transaction threshold (for structuring detection)
STRUCTURING_THRESHOLD = Decimal('10000.00')


# ============================================================================
# Transaction COMPLIANCE ROUNDING (IRS ROUND_HALF_UP)
# ============================================================================

def set_transaction_rounding_context() -> None:
    """
    Set global Decimal context for transaction calculations.
    Uses ROUND_HALF_UP (0.5 always rounds up) per IRS requirements.
    Call this once at application startup.
    """
    ctx = getcontext()
    ctx.rounding = ROUND_HALF_UP
    ctx.prec = 28  # Support up to 28 significant digits


# Initialize Transaction rounding on module load
set_transaction_rounding_context()


# ============================================================================
# DECIMAL COERCION HELPER
# ============================================================================

def to_decimal(value: Any, default: Decimal = Decimal(0)) -> Decimal:
    """
    Safely coerce any value to a Decimal, preserving precision for financial calculations.
    
    This function is critical for accurate crypto transaction calculations. It ensures:
    - No float precision loss (e.g., 0.1 + 0.2 = 0.3 exact)
    - Consistent handling of edge cases (None, invalid strings, etc.)
    - Satoshi-level precision preserved (0.00000001 BTC)
    
    Args:
        value: Any value to convert. Supports int, float, str, Decimal, bool, None.
        default: Decimal fallback if conversion fails. Defaults to Decimal(0).
    
    Returns:
        Decimal: Precise numeric value, or default if conversion fails.
    
    Examples:
        >>> to_decimal('45000.123')
        Decimal('45000.123')
        >>> to_decimal(1.5) == Decimal('1.5')
        True
        >>> to_decimal('invalid') == Decimal(0)
        True
        >>> to_decimal(None, Decimal('-1')) == Decimal('-1')
        True
    
    Note:
        - Floats are coerced via str() to preserve precision
        - Existing Decimals are passed through unchanged
        - None and invalid strings return default (no exception)
        - Satoshi precision (1e-8) is fully supported
    """
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default

