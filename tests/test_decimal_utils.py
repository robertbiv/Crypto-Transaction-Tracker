"""
Unit tests for decimal utility functions.
Ensures accurate numeric handling across edge cases.
"""

import pytest
from decimal import Decimal, InvalidOperation
from src.decimal_utils import to_decimal


class TestToDecimal:
    """Test suite for to_decimal helper function."""
    
    def test_valid_int(self):
        """Test conversion from int."""
        assert to_decimal(42) == Decimal('42')
    
    def test_valid_float(self):
        """Test conversion from float (via str to avoid precision issues)."""
        assert to_decimal(3.14159) == Decimal('3.14159')
    
    def test_valid_string(self):
        """Test conversion from string."""
        assert to_decimal('123.456') == Decimal('123.456')
    
    def test_valid_decimal(self):
        """Test pass-through of existing Decimal."""
        d = Decimal('999.99')
        assert to_decimal(d) is d
    
    def test_zero(self):
        """Test zero values."""
        assert to_decimal(0) == Decimal('0')
        assert to_decimal('0') == Decimal('0')
        assert to_decimal(0.0) == Decimal('0.0')
    
    def test_negative(self):
        """Test negative numbers."""
        assert to_decimal(-42) == Decimal('-42')
        assert to_decimal('-123.45') == Decimal('-123.45')
    
    def test_scientific_notation(self):
        """Test scientific notation strings."""
        assert to_decimal('1e6') == Decimal('1000000')
        assert to_decimal('1.5e3') == Decimal('1500')
    
    def test_very_large_number(self):
        """Test very large numbers (high precision)."""
        large = '123456789012345678901234567890.123456789'
        result = to_decimal(large)
        assert result == Decimal(large)
    
    def test_very_small_number(self):
        """Test very small numbers (satoshi precision)."""
        small = '0.00000001'  # 1 satoshi
        result = to_decimal(small)
        assert result == Decimal(small)
    
    def test_none_returns_default(self):
        """Test None returns default (0)."""
        assert to_decimal(None) == Decimal(0)
    
    def test_none_with_custom_default(self):
        """Test None with custom default."""
        custom_default = Decimal('999')
        assert to_decimal(None, custom_default) == custom_default
    
    def test_empty_string_returns_default(self):
        """Test empty string falls back to default."""
        assert to_decimal('') == Decimal(0)
    
    def test_invalid_string_returns_default(self):
        """Test invalid string returns default."""
        assert to_decimal('not_a_number') == Decimal(0)
        assert to_decimal('12.34.56') == Decimal(0)
    
    def test_invalid_string_with_custom_default(self):
        """Test invalid string with custom default."""
        custom_default = Decimal('-1')
        assert to_decimal('abc', custom_default) == custom_default
    
    def test_boolean(self):
        """Test boolean values coerce correctly."""
        # str(True) -> 'True', which is invalid for Decimal, so returns default
        assert to_decimal(True) == Decimal(0)
        assert to_decimal(False) == Decimal(0)
    
    def test_list_returns_default(self):
        """Test invalid type (list) returns default."""
        assert to_decimal([1, 2, 3]) == Decimal(0)
    
    def test_dict_returns_default(self):
        """Test invalid type (dict) returns default."""
        assert to_decimal({'a': 1}) == Decimal(0)
    
    def test_precision_preserved(self):
        """Test that precision is fully preserved (not truncated)."""
        precise = '0.123456789012345678901234567890'
        result = to_decimal(precise)
        assert str(result) == precise
    
    def test_financial_rounding_scenario(self):
        """Test realistic financial computation."""
        # BTC at $45000, 1.5 BTC
        price = to_decimal('45000.00')
        amount = to_decimal('1.5')
        total = price * amount
        assert total == Decimal('67500.00')
    
    def test_satoshi_calculation(self):
        """Test satoshi-level precision."""
        satoshi = to_decimal('0.00000001')
        count = to_decimal('1000000')
        total = satoshi * count
        assert total == Decimal('0.01')
    
    def test_fee_calculation_high_precision(self):
        """Test high-precision fee calculation."""
        total = to_decimal('12345.6789')
        fee_pct = to_decimal('0.5')
        fee = (total * fee_pct) / Decimal('100')
        # Verify no float rounding errors
        assert fee == Decimal('61.7283945')
    
    def test_average_calculation(self):
        """Test averaging without precision loss."""
        amounts = [to_decimal(x) for x in ['100.111', '200.222', '300.333']]
        avg = sum(amounts) / Decimal(len(amounts))
        assert avg == Decimal('200.222')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
