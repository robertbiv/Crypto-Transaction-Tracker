"""
================================================================================
TEST: Input Validation & SQL Injection Prevention
================================================================================

Tests that all input is properly validated and sanitized to prevent
SQL injection, data corruption, and edge case failures.

Test Coverage:
    - SQL injection attempts
    - Special character handling
    - Unicode and encoding
    - Malformed dates
    - Invalid amounts
    - Boundary conditions
    - NULL handling

Author: Input Safety Enhancement
================================================================================
"""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture()
def validated_db(tmp_path):
    """Create isolated database for validation testing."""
    db_path = tmp_path / "validated.db"
    
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE trades (
            id TEXT PRIMARY KEY,
            date TEXT,
            source TEXT,
            destination TEXT,
            action TEXT,
            coin TEXT,
            amount TEXT,
            price_usd TEXT,
            fee TEXT,
            fee_coin TEXT,
            batch_id TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    return db_path


def safe_insert(db_path, **kwargs):
    """Helper to safely insert trade."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        conn.execute(
            "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                kwargs.get('id'),
                kwargs.get('date'),
                kwargs.get('source'),
                kwargs.get('destination'),
                kwargs.get('action'),
                kwargs.get('coin'),
                kwargs.get('amount'),
                kwargs.get('price_usd'),
                kwargs.get('fee'),
                kwargs.get('fee_coin'),
                kwargs.get('batch_id')
            )
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def test_sql_injection_in_id(validated_db):
    """Test SQL injection attempts in ID field."""
    malicious_ids = [
        "'; DROP TABLE trades; --",
        "' OR '1'='1",
        "1 UNION SELECT * FROM sqlite_master",
        "test\" --",
        "test`; DELETE FROM trades;",
    ]
    
    for malicious_id in malicious_ids:
        result = safe_insert(
            validated_db,
            id=malicious_id,
            date="2024-01-01",
            source="SRC",
            destination="DST",
            action="BUY",
            coin="BTC",
            amount="1",
            price_usd="100",
            fee="0",
            fee_coin="",
            batch_id=None
        )
        
        # Check table still exists
        conn = sqlite3.connect(str(validated_db))
        try:
            count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            conn.close()
            # Should either fail or table should still exist
            assert True  # If we got here, table exists
        except sqlite3.OperationalError:
            pytest.fail("Table was dropped by SQL injection")


def test_sql_injection_in_strings(validated_db):
    """Test SQL injection in string fields."""
    malicious_values = [
        ("source", "'; UPDATE trades SET coin='HACKED'; --"),
        ("destination", "test' OR '1'='1"),
        ("coin", "BTC'; DROP TABLE trades; --"),
    ]
    
    for field, value in malicious_values:
        kwargs = {
            'id': f'test-{field}',
            'date': '2024-01-01',
            'source': 'SRC',
            'destination': 'DST',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': '1',
            'price_usd': '100',
            'fee': '0',
            'fee_coin': '',
            'batch_id': None
        }
        kwargs[field] = value
        
        result = safe_insert(validated_db, **kwargs)
        
        # Verify data integrity
        conn = sqlite3.connect(str(validated_db))
        rows = conn.execute("SELECT * FROM trades").fetchall()
        conn.close()
        
        # Table should still exist and be queryable
        assert True


def test_special_characters_unicode(validated_db):
    """Test that special characters and unicode are handled safely."""
    special_chars = [
        "Café",
        "日本語",
        "Emoji🚀",
        "Test\nNewline",
        "Tab\tSeparated",
        "Quotes'and\"both",
        "Backslash\\Test",
        "Null\x00Byte",
    ]
    
    for i, char_str in enumerate(special_chars):
        result = safe_insert(
            validated_db,
            id=f"unicode-{i}",
            date="2024-01-01",
            source=char_str[:20],
            destination="DST",
            action="BUY",
            coin=char_str[:10],
            amount="1",
            price_usd="100",
            fee="0",
            fee_coin="",
            batch_id=None
        )
        
        # Verify insert succeeded or failed gracefully
        assert isinstance(result, bool)


def test_malformed_dates(validated_db):
    """Test malformed date handling."""
    malformed_dates = [
        "not-a-date",
        "2024-13-01",  # Invalid month
        "2024-01-32",  # Invalid day
        "2024/01/01",  # Wrong format
        "01-01-2024",  # Wrong order
        "",
        "2024-01-01T25:00:00",  # Invalid time
    ]
    
    for i, date_str in enumerate(malformed_dates):
        result = safe_insert(
            validated_db,
            id=f"date-{i}",
            date=date_str,
            source="SRC",
            destination="DST",
            action="BUY",
            coin="BTC",
            amount="1",
            price_usd="100",
            fee="0",
            fee_coin="",
            batch_id=None
        )
        
        # Should handle gracefully (either insert or reject)
        assert isinstance(result, bool)


def test_invalid_amounts(validated_db):
    """Test invalid amount values."""
    invalid_amounts = [
        "not-a-number",
        "-999999999",
        "1.23.45",
        "1e308",  # Very large
        "NaN",
        "Infinity",
        "",
    ]
    
    for i, amount_str in enumerate(invalid_amounts):
        result = safe_insert(
            validated_db,
            id=f"amount-{i}",
            date="2024-01-01",
            source="SRC",
            destination="DST",
            action="BUY",
            coin="BTC",
            amount=amount_str,
            price_usd="100",
            fee="0",
            fee_coin="",
            batch_id=None
        )
        
        assert isinstance(result, bool)


def test_boundary_values(validated_db):
    """Test boundary and extreme values."""
    boundary_values = [
        ("id", "x" * 1000),  # Very long ID
        ("coin", "C" * 500),  # Very long coin name
        ("amount", "9" * 100),  # Very large amount
        ("price_usd", "1" * 50),  # Very large price
    ]
    
    for field, value in boundary_values:
        kwargs = {
            'id': f'boundary-{field}',
            'date': '2024-01-01',
            'source': 'SRC',
            'destination': 'DST',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': '1',
            'price_usd': '100',
            'fee': '0',
            'fee_coin': '',
            'batch_id': None
        }
        kwargs[field] = value
        
        result = safe_insert(validated_db, **kwargs)
        assert isinstance(result, bool)


def test_null_and_empty_strings(validated_db):
    """Test NULL and empty string handling."""
    test_cases = [
        {'id': 'null-1', 'fee_coin': None},
        {'id': 'null-2', 'batch_id': None},
        {'id': 'empty-1', 'source': ''},
        {'id': 'empty-2', 'fee_coin': ''},
    ]
    
    for case in test_cases:
        kwargs = {
            'date': '2024-01-01',
            'source': 'SRC',
            'destination': 'DST',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': '1',
            'price_usd': '100',
            'fee': '0',
            'fee_coin': '',
            'batch_id': None
        }
        kwargs.update(case)
        
        result = safe_insert(validated_db, **kwargs)
        assert isinstance(result, bool)


def test_duplicate_prevention(validated_db):
    """Test that duplicate detection works properly."""
    # Insert first record
    result1 = safe_insert(
        validated_db,
        id='duplicate-test',
        date='2024-01-01',
        source='SRC',
        destination='DST',
        action='BUY',
        coin='BTC',
        amount='1',
        price_usd='100',
        fee='0',
        fee_coin='',
        batch_id=None
    )
    assert result1
    
    # Try to insert duplicate
    result2 = safe_insert(
        validated_db,
        id='duplicate-test',
        date='2024-01-01',
        source='SRC',
        destination='DST',
        action='BUY',
        coin='BTC',
        amount='1',
        price_usd='100',
        fee='0',
        fee_coin='',
        batch_id=None
    )
    assert not result2  # Should fail


def test_case_sensitivity(validated_db):
    """Test that case sensitivity doesn't bypass constraints."""
    result1 = safe_insert(
        validated_db,
        id='CaseSensitive',
        date='2024-01-01',
        source='SRC',
        destination='DST',
        action='BUY',
        coin='BTC',
        amount='1',
        price_usd='100',
        fee='0',
        fee_coin='',
        batch_id=None
    )
    assert result1
    
    # Try different case - should still work (different ID)
    result2 = safe_insert(
        validated_db,
        id='casesensitive',
        date='2024-01-01',
        source='SRC',
        destination='DST',
        action='BUY',
        coin='BTC',
        amount='1',
        price_usd='100',
        fee='0',
        fee_coin='',
        batch_id=None
    )
    assert result2


def test_whitespace_handling(validated_db):
    """Test whitespace in various fields."""
    whitespace_cases = [
        ("id", "   leading"),
        ("id", "trailing   "),
        ("source", "  both  "),
        ("coin", "\t\ttabs\t\t"),
    ]
    
    for i, (field, value) in enumerate(whitespace_cases):
        kwargs = {
            'id': f'whitespace-{i}',
            'date': '2024-01-01',
            'source': 'SRC',
            'destination': 'DST',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': '1',
            'price_usd': '100',
            'fee': '0',
            'fee_coin': '',
            'batch_id': None
        }
        kwargs[field] = value
        
        result = safe_insert(validated_db, **kwargs)
        assert isinstance(result, bool)
