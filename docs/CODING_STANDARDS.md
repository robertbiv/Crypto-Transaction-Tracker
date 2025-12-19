# Crypto Transaction Tracker - Coding Standards

## Documentation Style Guide

### File Header Format

All Python files must include a standardized header block with the following format:

```python
"""
================================================================================
MODULE NAME - Brief Description
================================================================================

Detailed description of the module's purpose and functionality.

[Sections vary by file type - see examples below]

Author: robertbiv
Last Modified: [Month Year]
[Optional: Version info for major components]
================================================================================
"""
```

### Header Sections by File Type

#### Core Business Logic Files
```python
"""
================================================================================
    TRACKER ENGINE - Core Activity Processing Engine
================================================================================

Brief overview of the module.

Key Components:
    1. Component A - Description
    2. Component B - Description
    3. Component C - Description

Features:
    - Feature 1
    - Feature 2
    - Feature 3

Technical Details:
    - Implementation notes
    - Algorithm choices
    - Performance considerations

Integration:
    - How this module integrates with others
    - Dependencies
    - Public API

Author: robertbiv
Last Modified: December 2025
================================================================================
"""
```

#### Utility Modules
```python
"""
================================================================================
CONFIG - Configuration Management
================================================================================

Description of utility purpose.

Exported Functions:
    - function_a() - Description
    - function_b() - Description

Usage:
    from src.utils.config import load_config
    config = load_config()

Author: robertbiv
Last Modified: December 2025
================================================================================
"""
```

#### Test Files
```python
"""
================================================================================
TEST: Feature Name
================================================================================

Description of what is being tested.

Test Coverage:
    - Scenario 1
    - Scenario 2
    - Edge cases

Test Methodology:
    - Test approach
    - Fixtures used
    - Assertions verified

Author: robertbiv
================================================================================
"""
```

### Function/Method Documentation

Use Google-style docstrings for all functions:

```python
def calculate_capital_gains(sales: pd.DataFrame, method: str = 'FIFO') -> dict:
    """
    Calculate capital gains for cryptocurrency sales.
    
    Args:
        sales: DataFrame containing sale transactions with columns:
               ['date', 'coin', 'amount', 'price_usd', 'fee']
        method: Accounting method - 'FIFO', 'HIFO', or 'LIFO'
                Default: 'FIFO' (IRS recommended)
    
    Returns:
        Dictionary containing:
            - 'short_term': List of short-term gains/losses
            - 'long_term': List of long-term gains/losses
            - 'total_gain': Net capital gain/loss
    
    Raises:
        ValueError: If method is not recognized
        KeyError: If required columns are missing
    
    Example:
        >>> sales_df = pd.DataFrame({...})
        >>> gains = calculate_capital_gains(sales_df, method='FIFO')
        >>> print(f"Total gain: ${gains['total_gain']:.2f}")
    """
    # Implementation
```

### Class Documentation

```python
class TransactionEngine:
    """
    Main Transaction calculation engine for cryptocurrency transactions.
    
    This class orchestrates the entire Transaction calculation workflow including:
    data ingestion, price fetching, basis tracking, and report generation.
    
    Attributes:
        db (DatabaseManager): Transaction database connection
        year (int): Transaction year being processed
        holdings_by_source (dict): Cost basis lots organized by wallet/exchange
        tt (list): Transaction table for Export export
        inc (list): Income events (staking, mining, airdrops)
    
    Configuration:
        Behavior is controlled by config.json settings:
        - accounting.method: FIFO, HIFO, or LIFO
        - compliance.strict_broker_mode: Isolate custodial sources
        - compliance.wash_sale_rule: Enable/disable wash sale detection
    
    Example:
        >>> engine = TransactionEngine(db, year=2024)
        >>> engine.run()
        >>> engine.export()
    """
```

### Inline Comments

#### When to Use Inline Comments

1. **Complex Logic**: Explain non-obvious algorithms
2. **Regulatory Compliance**: Reference IRS rules or regulations
3. **Bug Workarounds**: Document why unusual code exists
4. **Performance Optimizations**: Explain why a specific approach was chosen

#### Comment Style

```python
# Good: Explains WHY
# Use timezone-aware datetime for wash sale detection to handle
# transactions across different timezones (UTC normalization required by IRS)
cutoff_date = pd.Timestamp(datetime(2025, 1, 1), tz='UTC')

# Bad: Explains WHAT (obvious from code)
# Set cutoff_date to January 1, 2025
cutoff_date = pd.Timestamp(datetime(2025, 1, 1), tz='UTC')
```

#### Section Comments

Use separator comments for major code sections:

```python
# ==========================================
# Transaction CALCULATION LOGIC
# ==========================================

# ==========================================
# DATA VALIDATION
# ==========================================

# ==========================================
# REPORT GENERATION
# ==========================================
```

### Constants and Configuration

Document constants with inline comments explaining their purpose and source:

```python
# IRS wash sale rule: 30 days before and after sale (61-day total window)
# Reference: IRC Section 1091
WASH_SALE_WINDOW_DAYS = 30

# Long-term capital gains threshold per IRC Section 1222
# Holding period must exceed 365 days (366 for leap years)
LONG_TERM_HOLDING_DAYS = 365

# PBKDF2 iterations per OWASP 2023 recommendation for password hashing
# Provides resistance against brute-force attacks (2^19 iterations)
DB_ENCRYPTION_ITERATIONS = 480000
```

### Type Hints

Use type hints for all function signatures:

```python
from typing import List, Dict, Optional, Union
from decimal import Decimal
from datetime import datetime

def process_trades(
    trades: List[Dict[str, Union[str, float, int]]],
    transaction_year: int,
    method: str = 'FIFO'
) -> Dict[str, List[Decimal]]:
    """Process trade transactions and calculate gains."""
    pass
```

### Error Handling

Document expected errors and their meanings:

```python
try:
    result = calculate_basis(trades)
except ValueError as e:
    # Invalid trade data (missing fields or negative amounts)
    logger.error(f"Trade validation failed: {e}")
    raise
except KeyError as e:
    # Required column missing from DataFrame
    logger.error(f"Data structure error: {e}")
    raise
except Exception as e:
    # Unexpected error - log for debugging
    logger.exception("Unexpected error in basis calculation")
    raise
```

### Deprecation Warnings

When deprecating features:

```python
def old_function():
    """
    Old function that will be removed in v31.
    
    .. deprecated:: v30
        Use :func:`new_function` instead. This function will be
        removed in version 31 (June 2026).
    """
    import warnings
    warnings.warn(
        "old_function is deprecated, use new_function instead",
        DeprecationWarning,
        stacklevel=2
    )
    # Implementation
```

## Best Practices

1. **Write comments for future you**: Assume you'll revisit code after 6 months
2. **Reference regulations**: Link to IRS publications when implementing Transaction rules
3. **Explain non-obvious choices**: Document why you chose a specific approach
4. **Keep comments updated**: When changing code, update related comments
5. **Use TODO markers**: `# TODO: Implement wash sale detection for 2026`
6. **Document assumptions**: Make implicit assumptions explicit
7. **Explain magic numbers**: Constants should have explanatory comments