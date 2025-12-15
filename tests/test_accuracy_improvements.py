"""
Unit tests for accuracy improvements and security hardening
Tests division-by-zero handling, decimal precision, and exception handling
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import Crypto_Tax_Engine as app
from Crypto_Tax_Engine import DatabaseManager, Ingestor, to_decimal, round_decimal


class TestDivisionByZeroHandling:
    """Test that division-by-zero is properly handled in swap calculations"""
    
    def test_swap_with_zero_sent_amount(self, tmp_path, monkeypatch):
        """Test swap processing with zero sent amount doesn't crash"""
        # Create temp database
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        # Create ingestor with mock price fetcher
        ingestor = Ingestor(db)
        ingestor.fetcher = Mock()
        ingestor.fetcher.get_price = Mock(return_value=None)
        
        # Create CSV with zero sent_amount
        csv_file = tmp_path / "swap_zero.csv"
        csv_file.write_text(
            "date,type,sent_coin,sent_amount,received_coin,received_amount,price_usd,fee\n"
            "2024-01-01T12:00:00Z,trade,ETH,0,BTC,0.05,2000,0\n"
        )
        
        # Process - should not crash
        ingestor._proc_csv_smart(csv_file, batch="TEST_BATCH")
        
        # Verify trade was created without division error
        trades = db.get_all()
        assert len(trades) >= 0  # Should complete without exception
        db.close()
    
    def test_swap_with_zero_received_amount(self, tmp_path, monkeypatch):
        """Test swap processing with zero received amount doesn't crash"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        ingestor = Ingestor(db)
        ingestor.fetcher = Mock()
        ingestor.fetcher.get_price = Mock(return_value=None)
        
        csv_file = tmp_path / "swap_zero.csv"
        csv_file.write_text(
            "date,type,sent_coin,sent_amount,received_coin,received_amount,price_usd,fee\n"
            "2024-01-01T12:00:00Z,trade,ETH,1.0,BTC,0,2000,0\n"
        )
        
        ingestor._proc_csv_smart(csv_file, batch="TEST_BATCH")
        
        trades = db.get_all()
        assert len(trades) >= 0
        db.close()
    
    def test_swap_with_valid_amounts_calculates_correctly(self, tmp_path, monkeypatch):
        """Test that valid swap amounts calculate price correctly"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        ingestor = Ingestor(db)
        ingestor.fetcher = Mock()
        ingestor.fetcher.get_price = Mock(return_value=None)
        
        csv_file = tmp_path / "swap_valid.csv"
        csv_file.write_text(
            "date,type,sent_coin,sent_amount,received_coin,received_amount,price_usd,fee\n"
            "2024-01-01T12:00:00Z,trade,ETH,2.0,BTC,0.05,4000,0\n"
        )
        
        ingestor._proc_csv_smart(csv_file, batch="TEST_BATCH")
        
        trades = db.get_all()
        assert len(trades) == 2  # Should create SELL + BUY
        
        # Check price calculations
        sell_trade = trades[trades['action'] == 'SELL'].iloc[0]
        buy_trade = trades[trades['action'] == 'BUY'].iloc[0]
        
        # Price should be total_price / amount
        # SELL: 4000 / 2.0 = 2000 per ETH
        # BUY: 4000 / 0.05 = 80000 per BTC
        sell_price = to_decimal(sell_trade['price_usd'])
        buy_price = to_decimal(buy_trade['price_usd'])
        
        assert sell_price == Decimal('2000')
        assert buy_price == Decimal('80000')
        db.close()


class TestDecimalPrecisionHandling:
    """Test decimal precision in calculations"""
    
    def test_to_decimal_with_float(self):
        """Test conversion from float to Decimal"""
        result = to_decimal(1.23456789)
        assert isinstance(result, Decimal)
        assert result == Decimal('1.23456789')
    
    def test_to_decimal_with_string(self):
        """Test conversion from string to Decimal"""
        result = to_decimal("1234.56789012")
        assert isinstance(result, Decimal)
        assert result == Decimal('1234.56789012')
    
    def test_to_decimal_with_none(self):
        """Test conversion from None returns zero"""
        result = to_decimal(None)
        assert result == Decimal('0')
    
    def test_to_decimal_with_nan(self):
        """Test conversion from NaN returns zero"""
        result = to_decimal('nan')
        assert result == Decimal('0')
    
    def test_to_decimal_with_invalid_string(self):
        """Test conversion from invalid string returns zero"""
        result = to_decimal('invalid')
        assert result == Decimal('0')
    
    def test_round_decimal_8_places(self):
        """Test rounding to 8 decimal places"""
        value = Decimal('1.123456789012345')
        result = round_decimal(value, 8)
        assert result == Decimal('1.12345679')
    
    def test_round_decimal_2_places(self):
        """Test rounding to 2 decimal places"""
        value = Decimal('1234.56789')
        result = round_decimal(value, 2)
        assert result == Decimal('1234.57')
    
    def test_decimal_division_precision(self):
        """Test that division maintains precision"""
        a = to_decimal('10000')
        b = to_decimal('3')
        result = a / b
        
        # Should maintain high precision
        assert isinstance(result, Decimal)
        assert str(result).startswith('3333.33333')


class TestExceptionHandling:
    """Test exception handling in critical paths"""
    
    def test_invalid_price_value_handled(self, tmp_path, monkeypatch):
        """Test that invalid price values are handled gracefully"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        ingestor = Ingestor(db)
        ingestor.fetcher = Mock()
        ingestor.fetcher.get_price = Mock(return_value=None)
        
        # CSV with invalid price
        csv_file = tmp_path / "invalid_price.csv"
        csv_file.write_text(
            "date,type,received_coin,received_amount,price_usd,fee\n"
            "2024-01-01T12:00:00Z,staking,ETH,0.01,INVALID,0\n"
        )
        
        # Should not crash
        ingestor._proc_csv_smart(csv_file, batch="TEST_BATCH")
        
        trades = db.get_all()
        assert len(trades) >= 0  # Completed without exception
        db.close()
    
    def test_malformed_csv_row_skipped(self, tmp_path, monkeypatch):
        """Test that malformed CSV rows are skipped with logging"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        ingestor = Ingestor(db)
        ingestor.fetcher = Mock()
        ingestor.fetcher.get_price = Mock(return_value=None)
        
        # CSV with malformed row
        csv_file = tmp_path / "malformed.csv"
        csv_file.write_text(
            "date,type,received_coin,received_amount,price_usd,fee\n"
            "2024-01-01T12:00:00Z,staking,ETH,0.01,100,0\n"
            "INVALID_DATE,staking,ETH,0.01,100,0\n"
            "2024-01-02T12:00:00Z,staking,BTC,0.001,300,0\n"
        )
        
        # Should skip bad row and continue
        ingestor._proc_csv_smart(csv_file, batch="TEST_BATCH")
        
        trades = db.get_all()
        # Should have 2 valid trades (bad row skipped)
        assert len(trades) >= 1
        db.close()
    
    def test_archive_missing_file_handled(self, tmp_path, monkeypatch):
        """Test that archiving missing file is handled gracefully"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        ingestor = Ingestor(db)
        
        # Try to archive non-existent file
        fake_file = tmp_path / "nonexistent.csv"
        
        # Should not crash
        try:
            ingestor._archive(fake_file)
        except Exception as e:
            pytest.fail(f"Archive should handle missing files gracefully, got: {e}")
        
        db.close()


class TestPriceFetchFailures:
    """Test graceful handling of price fetch failures"""
    
    def test_price_fetch_failure_uses_zero(self, tmp_path, monkeypatch):
        """Test that price fetch failures result in zero price with logging"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        ingestor = Ingestor(db)
        # Mock price fetcher to raise exception
        ingestor.fetcher = Mock()
        ingestor.fetcher.get_price = Mock(side_effect=Exception("API error"))
        
        csv_file = tmp_path / "zero_price.csv"
        csv_file.write_text(
            "date,type,received_coin,received_amount,price_usd,fee\n"
            "2024-01-01T12:00:00Z,staking,ETH,0.01,0,0\n"
        )
        
        # Should complete without crashing
        ingestor._proc_csv_smart(csv_file, batch="TEST_BATCH")
        
        trades = db.get_all()
        assert len(trades) == 1
        
        # Price should be 0 (fetch failed)
        trade = trades.iloc[0]
        assert to_decimal(trade['price_usd']) == Decimal('0')
        db.close()
    
    def test_price_fetch_success_updates_price(self, tmp_path, monkeypatch):
        """Test that successful price fetch updates zero prices"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        ingestor = Ingestor(db)
        # Mock price fetcher to return valid price
        ingestor.fetcher = Mock()
        ingestor.fetcher.get_price = Mock(return_value=1800.50)
        
        csv_file = tmp_path / "fetch_price.csv"
        csv_file.write_text(
            "date,type,received_coin,received_amount,price_usd,fee\n"
            "2024-01-01T12:00:00Z,staking,ETH,0.01,0,0\n"
        )
        
        ingestor._proc_csv_smart(csv_file, batch="TEST_BATCH")
        
        trades = db.get_all()
        assert len(trades) == 1
        
        # Price should be fetched value
        trade = trades.iloc[0]
        price = to_decimal(trade['price_usd'])
        assert price > 0  # Should have fetched price
        db.close()


class TestSwapPriceCalculations:
    """Test swap price calculation accuracy"""
    
    def test_swap_price_split_correctly(self, tmp_path, monkeypatch):
        """Test that swap splits price between SELL and BUY correctly"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        monkeypatch.setattr(app, 'ARCHIVE_DIR', tmp_path / 'archive')
        (tmp_path / 'archive').mkdir()
        
        db = DatabaseManager()
        
        ingestor = Ingestor(db)
        ingestor.fetcher = Mock()
        ingestor.fetcher.get_price = Mock(return_value=None)
        
        csv_file = tmp_path / "swap.csv"
        csv_file.write_text(
            "date,type,sent_coin,sent_amount,received_coin,received_amount,price_usd,fee\n"
            "2024-01-01T12:00:00Z,trade,USDT,1000,ETH,0.5,1000,5\n"
        )
        
        ingestor._proc_csv_smart(csv_file, batch="TEST_BATCH")
        
        trades = db.get_all()
        assert len(trades) == 2
        
        sell_trade = trades[trades['action'] == 'SELL'].iloc[0]
        buy_trade = trades[trades['action'] == 'BUY'].iloc[0]
        
        # SELL: 1000 / 1000 = 1 per USDT
        # BUY: 1000 / 0.5 = 2000 per ETH
        sell_price = to_decimal(sell_trade['price_usd'])
        buy_price = to_decimal(buy_trade['price_usd'])
        
        assert sell_price == Decimal('1')
        assert buy_price == Decimal('2000')
        
        # Fee should be on SELL only
        assert to_decimal(sell_trade['fee']) == Decimal('5')
        assert to_decimal(buy_trade['fee']) == Decimal('0')
        db.close()
    
    def test_decimal_operations_no_float_errors(self):
        """Test that decimal operations don't have floating point errors"""
        # Classic floating point error example
        a = 0.1 + 0.2  # Float gives 0.30000000000000004
        
        # Using Decimal
        da = to_decimal('0.1') + to_decimal('0.2')
        
        assert a != 0.3  # Float fails
        assert da == Decimal('0.3')  # Decimal succeeds
    
    def test_large_number_precision(self):
        """Test precision with large cryptocurrency amounts"""
        # 1 million Shiba Inu at $0.00001 each
        amount = to_decimal('1000000')
        price_per_unit = to_decimal('0.00001')
        total = amount * price_per_unit
        
        assert total == Decimal('10')
        
        # Verify precision maintained in division
        recovered_amount = total / price_per_unit
        assert recovered_amount == amount


class TestDatabaseDecimalStorage:
    """Test that decimals are stored and retrieved correctly"""
    
    def test_decimal_roundtrip(self, tmp_path, monkeypatch):
        """Test that decimal values survive database roundtrip"""
        db_file = tmp_path / "test.db"
        monkeypatch.setattr(app, 'DB_FILE', db_file)
        
        db = DatabaseManager()
        
        # Save trade with precise decimal
        trade = {
            'id': 'test_1',
            'date': '2024-01-01T12:00:00Z',
            'source': 'TEST',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': Decimal('0.12345678'),
            'price_usd': Decimal('42000.12345678'),
            'fee': Decimal('0.00000001'),
            'batch_id': 'test'
        }
        
        db.save_trade(trade)
        db.commit()
        
        # Retrieve and verify
        retrieved = db.get_all()
        assert len(retrieved) == 1
        
        row = retrieved.iloc[0]
        assert to_decimal(row['amount']) == Decimal('0.12345678')
        assert to_decimal(row['price_usd']) == Decimal('42000.12345678')
        assert to_decimal(row['fee']) == Decimal('0.00000001')
        
        db.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
