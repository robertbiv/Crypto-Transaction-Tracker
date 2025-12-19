from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(value: Any, default: Decimal = Decimal(0)) -> Decimal:
    """
    Safely coerce any value to a Decimal, preserving precision for financial calculations.
    
    This function is critical for accurate crypto tax calculations. It ensures:
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
