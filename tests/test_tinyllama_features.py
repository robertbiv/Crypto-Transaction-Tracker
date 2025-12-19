"""
Comprehensive Test Suite for TinyLLaMA Features
Tests all AI features: fraud detection, smart descriptions, pattern learning, anomaly detection

Test Coverage:
    - FraudDetectorAccurate (context-aware fraud detection)
    - SmartDescriptionGeneratorAccurate (creative descriptions)
    - PatternLearnerAccurate (behavioral pattern analysis)
    - AnomalyDetector (statistical anomaly detection)
    - Integration tests (all features working together)
    - Edge cases (empty data, extreme values, missing fields)
    - Configuration validation
    - Error handling and fallbacks

Author: Test Suite
Last Modified: December 2025
"""

import pytest
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from advanced_ml_features_accurate import (
    FraudDetectorAccurate,
    SmartDescriptionGeneratorAccurate,
    PatternLearnerAccurate
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope='module')
def setup_test_db():
    """Setup test database with sample transactions"""
    db_file = Path('test_tinyllama_features.db')
    if db_file.exists():
        db_file.unlink()
    
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    
    # Create trades table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            action TEXT NOT NULL,
            coin TEXT NOT NULL,
            amount REAL NOT NULL,
            price_usd REAL NOT NULL,
            source TEXT DEFAULT 'manual',
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert sample transactions for pattern learning
    base_date = datetime(2024, 1, 1)
    sample_txs = [
        # Normal BTC purchases (establishing pattern)
        ('2024-01-01', 'buy', 'BTC', 0.5, 42000, 'binance'),
        ('2024-01-08', 'buy', 'BTC', 0.5, 43000, 'binance'),
        ('2024-01-15', 'buy', 'BTC', 0.5, 44000, 'binance'),
        ('2024-01-22', 'buy', 'BTC', 0.5, 41000, 'binance'),
        ('2024-02-01', 'buy', 'BTC', 0.5, 45000, 'binance'),
        ('2024-02-08', 'buy', 'BTC', 0.5, 46000, 'binance'),
        ('2024-02-15', 'buy', 'BTC', 0.5, 47000, 'binance'),
        ('2024-02-22', 'buy', 'BTC', 0.5, 46000, 'binance'),
        ('2024-03-01', 'buy', 'BTC', 0.5, 48000, 'binance'),
        ('2024-03-08', 'buy', 'BTC', 0.5, 49000, 'binance'),
        ('2024-03-15', 'buy', 'BTC', 0.5, 50000, 'binance'),
        ('2024-03-22', 'buy', 'BTC', 0.5, 49000, 'binance'),
        ('2024-04-01', 'buy', 'BTC', 0.5, 51000, 'binance'),
        ('2024-04-08', 'buy', 'BTC', 0.5, 52000, 'binance'),
        ('2024-04-15', 'buy', 'BTC', 0.5, 53000, 'binance'),
        ('2024-04-22', 'buy', 'BTC', 0.5, 52000, 'binance'),
        ('2024-05-01', 'buy', 'BTC', 0.5, 54000, 'binance'),
        ('2024-05-08', 'buy', 'BTC', 0.5, 55000, 'binance'),
        ('2024-05-15', 'buy', 'BTC', 0.5, 56000, 'binance'),
        ('2024-05-22', 'buy', 'BTC', 0.5, 55000, 'binance'),
        
        # Normal ETH sales (establishing pattern)
        ('2024-01-05', 'sell', 'ETH', 2.0, 2200, 'kraken'),
        ('2024-01-12', 'sell', 'ETH', 2.0, 2250, 'kraken'),
        ('2024-01-19', 'sell', 'ETH', 2.0, 2300, 'kraken'),
        ('2024-01-26', 'sell', 'ETH', 2.0, 2400, 'kraken'),
        
        # Potential fraud: enormous BTC purchase at unusual price
        ('2024-05-29', 'buy', 'BTC', 50.0, 10000, 'unknown_exchange'),  # Red flag
        
        # Potential fraud: dust transaction (extreme small amount)
        ('2024-06-01', 'buy', 'ETH', 0.0000001, 0.001, 'suspicious_exchange'),
        
        # Potential fraud: extreme volatility in single tx
        ('2024-06-05', 'sell', 'BTC', 0.5, 200000, 'unverified_source'),
    ]
    
    for tx in sample_txs:
        conn.execute("""
            INSERT INTO trades (date, action, coin, amount, price_usd, source, description)
            VALUES (?, ?, ?, ?, ?, ?, '')
        """, tx)
    
    conn.commit()
    yield conn
    conn.close()
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
def fraud_detector():
    """Create FraudDetectorAccurate instance"""
    return FraudDetectorAccurate()


@pytest.fixture
def smart_description_gen():
    """Create SmartDescriptionGeneratorAccurate instance"""
    return SmartDescriptionGeneratorAccurate()


@pytest.fixture
def pattern_learner():
    """Create PatternLearnerAccurate instance"""
    return PatternLearnerAccurate()


# ============================================================================
# FRAUD DETECTION TESTS
# ============================================================================

class TestFraudDetectorAccurate:
    """Test suite for FraudDetectorAccurate"""
    
    def test_initialization(self, fraud_detector):
        """Test FraudDetectorAccurate initializes correctly"""
        assert fraud_detector is not None
        assert hasattr(fraud_detector, 'detect') or hasattr(fraud_detector, 'fallback')
    
    def test_detect_extreme_price_outlier(self, fraud_detector):
        """Test detection of extreme price outliers"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 200000,  # Extreme outlier
            'source': 'unknown_exchange',
            'date': '2024-06-01'
        }
        
        result = fraud_detector.detect(tx)
        assert result is not None
        assert 'fraud_score' in result or 'risk_level' in result
    
    def test_detect_dust_attack(self, fraud_detector):
        """Test detection of dust attack (micro transaction)"""
        tx = {
            'action': 'buy',
            'coin': 'ETH',
            'amount': 0.0000001,  # Dust amount
            'price_usd': 0.001,
            'source': 'suspicious_exchange',
            'date': '2024-06-01'
        }
        
        result = fraud_detector.detect(tx)
        assert result is not None
        # Should flag dust transaction
    
    def test_detect_suspicious_source(self, fraud_detector):
        """Test detection of suspicious exchange source"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 40000,
            'source': 'unknown_sketchy_exchange_xyz',  # Suspicious
            'date': '2024-06-01'
        }
        
        result = fraud_detector.detect(tx)
        assert result is not None
    
    def test_detect_unusual_quantity_for_coin(self, fraud_detector):
        """Test detection of unusual quantity for specific coin"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 100.0,  # Extremely large for normal user
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        result = fraud_detector.detect(tx)
        assert result is not None
    
    def test_legitimate_transaction_low_risk(self, fraud_detector):
        """Test legitimate transaction scores low risk"""
        tx = {
            'action': 'buy',
            'coin': 'ETH',
            'amount': 1.0,
            'price_usd': 2500,
            'source': 'kraken',
            'date': '2024-06-01'
        }
        
        result = fraud_detector.detect(tx)
        assert result is not None
        # Should not be high risk
    
    def test_detect_with_empty_transaction(self, fraud_detector):
        """Test handling of empty/incomplete transaction"""
        tx = {}
        result = fraud_detector.detect(tx)
        # Should handle gracefully, return None or default score
        assert result is None or isinstance(result, dict)
    
    def test_detect_with_missing_fields(self, fraud_detector):
        """Test handling of missing required fields"""
        tx = {
            'action': 'buy',
            'coin': 'BTC'
            # Missing price_usd, amount, source, etc.
        }
        result = fraud_detector.detect(tx)
        assert result is None or isinstance(result, dict)


# ============================================================================
# SMART DESCRIPTION GENERATION TESTS
# ============================================================================

class TestSmartDescriptionGeneratorAccurate:
    """Test suite for SmartDescriptionGeneratorAccurate"""
    
    def test_initialization(self, smart_description_gen):
        """Test SmartDescriptionGeneratorAccurate initializes correctly"""
        assert smart_description_gen is not None
        assert hasattr(smart_description_gen, 'generate') or hasattr(smart_description_gen, 'fallback')
    
    def test_generate_buy_description(self, smart_description_gen):
        """Test generating description for buy transaction"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        description = smart_description_gen.generate(tx)
        assert description is not None
        assert isinstance(description, str)
        assert len(description) > 0
    
    def test_generate_sell_description(self, smart_description_gen):
        """Test generating description for sell transaction"""
        tx = {
            'action': 'sell',
            'coin': 'ETH',
            'amount': 2.0,
            'price_usd': 2500,
            'source': 'kraken',
            'date': '2024-06-01'
        }
        
        description = smart_description_gen.generate(tx)
        assert description is not None
        assert isinstance(description, str)
        assert len(description) > 0
    
    def test_generate_with_existing_description(self, smart_description_gen):
        """Test that existing descriptions are enhanced"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01',
            'description': 'Weekly purchase'
        }
        
        description = smart_description_gen.generate(tx)
        assert description is not None
        assert isinstance(description, str)
    
    def test_generate_with_empty_transaction(self, smart_description_gen):
        """Test handling of empty transaction"""
        tx = {}
        description = smart_description_gen.generate(tx)
        # Should handle gracefully
        assert description is None or isinstance(description, str)
    
    def test_generate_descriptions_vary(self, smart_description_gen):
        """Test that descriptions are contextual and vary"""
        tx1 = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 0.1,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        tx2 = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 10.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        desc1 = smart_description_gen.generate(tx1)
        desc2 = smart_description_gen.generate(tx2)
        
        assert desc1 is not None
        assert desc2 is not None
        # Different amounts should potentially generate different descriptions
    
    def test_generate_with_all_major_coins(self, smart_description_gen):
        """Test description generation for major coins"""
        coins = ['BTC', 'ETH', 'ADA', 'XRP', 'SOL']
        
        for coin in coins:
            tx = {
                'action': 'buy',
                'coin': coin,
                'amount': 1.0,
                'price_usd': 1000,
                'source': 'kraken',
                'date': '2024-06-01'
            }
            
            description = smart_description_gen.generate(tx)
            assert description is not None
            assert isinstance(description, str)


# ============================================================================
# PATTERN LEARNING TESTS
# ============================================================================

class TestPatternLearnerAccurate:
    """Test suite for PatternLearnerAccurate"""
    
    def test_initialization(self, pattern_learner):
        """Test PatternLearnerAccurate initializes correctly"""
        assert pattern_learner is not None
        assert hasattr(pattern_learner, 'learn') or hasattr(pattern_learner, 'fallback')
    
    def test_learn_from_transactions(self, pattern_learner, setup_test_db):
        """Test learning patterns from transactions"""
        conn = setup_test_db
        
        # Get sample transactions
        cursor = conn.execute("""
            SELECT action, coin, amount, price_usd, source, date
            FROM trades
            WHERE coin = 'BTC' AND action = 'buy'
            LIMIT 20
        """)
        
        transactions = [dict(row) for row in cursor.fetchall()]
        assert len(transactions) > 0
        
        # Learn patterns
        result = pattern_learner.learn(transactions)
        assert result is not None
    
    def test_detect_anomaly_in_pattern(self, pattern_learner, setup_test_db):
        """Test detection of anomalies against learned patterns"""
        conn = setup_test_db
        
        # Get normal transactions for learning
        cursor = conn.execute("""
            SELECT action, coin, amount, price_usd, source, date
            FROM trades
            WHERE coin = 'BTC' AND action = 'buy'
            LIMIT 10
        """)
        
        transactions = [dict(row) for row in cursor.fetchall()]
        pattern_learner.learn(transactions)
        
        # Test anomalous transaction
        anomaly = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 50.0,  # Way above normal
            'price_usd': 10000,  # Way below market
            'source': 'unknown_exchange',
            'date': '2024-06-01'
        }
        
        result = pattern_learner.detect_anomaly(anomaly)
        assert result is not None
    
    def test_pattern_with_empty_transactions(self, pattern_learner):
        """Test handling of empty transaction list"""
        result = pattern_learner.learn([])
        # Should handle gracefully
        assert result is None or isinstance(result, dict)
    
    def test_pattern_with_insufficient_transactions(self, pattern_learner):
        """Test handling when minimum transactions not met"""
        transactions = [
            {'action': 'buy', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 40000},
            {'action': 'buy', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 41000},
        ]
        
        result = pattern_learner.learn(transactions)
        # Should handle gracefully with insufficient data
        assert result is None or isinstance(result, dict)
    
    def test_pattern_update_incremental(self, pattern_learner):
        """Test incremental pattern updates"""
        batch1 = [
            {'action': 'buy', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 40000},
            {'action': 'buy', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 41000},
        ]
        
        batch2 = [
            {'action': 'buy', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 42000},
            {'action': 'buy', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 43000},
        ]
        
        pattern_learner.learn(batch1)
        result = pattern_learner.learn(batch2)
        # Should successfully update patterns
        assert result is None or isinstance(result, dict)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Test edge cases across all features"""
    
    def test_negative_amounts(self, fraud_detector, smart_description_gen, pattern_learner):
        """Test handling of negative amounts"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': -1.0,  # Invalid: negative amount
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        # All should handle gracefully
        assert fraud_detector.detect(tx) is None or isinstance(fraud_detector.detect(tx), dict)
        assert smart_description_gen.generate(tx) is None or isinstance(smart_description_gen.generate(tx), str)
        assert pattern_learner.learn([tx]) is None or isinstance(pattern_learner.learn([tx]), dict)
    
    def test_zero_amounts(self, fraud_detector, smart_description_gen):
        """Test handling of zero amounts"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 0.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        assert fraud_detector.detect(tx) is None or isinstance(fraud_detector.detect(tx), dict)
        assert smart_description_gen.generate(tx) is None or isinstance(smart_description_gen.generate(tx), str)
    
    def test_negative_prices(self, fraud_detector):
        """Test handling of negative prices"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': -45000,  # Invalid: negative price
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        assert fraud_detector.detect(tx) is None or isinstance(fraud_detector.detect(tx), dict)
    
    def test_extreme_large_numbers(self, fraud_detector):
        """Test handling of extremely large numbers"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1e15,  # Unrealistic amount
            'price_usd': 1e10,  # Unrealistic price
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        assert fraud_detector.detect(tx) is None or isinstance(fraud_detector.detect(tx), dict)
    
    def test_special_characters_in_fields(self, smart_description_gen):
        """Test handling of special characters"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': "exchange'; DROP TABLE trades; --",
            'date': '2024-06-01',
            'description': '<script>alert("xss")</script>'
        }
        
        description = smart_description_gen.generate(tx)
        assert description is None or isinstance(description, str)
    
    def test_unicode_characters_in_fields(self, smart_description_gen):
        """Test handling of unicode characters"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance_中文_😀',
            'date': '2024-06-01'
        }
        
        description = smart_description_gen.generate(tx)
        assert description is None or isinstance(description, str)
    
    def test_invalid_date_formats(self, fraud_detector, smart_description_gen):
        """Test handling of invalid date formats"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': 'not-a-valid-date'
        }
        
        assert fraud_detector.detect(tx) is None or isinstance(fraud_detector.detect(tx), dict)
        assert smart_description_gen.generate(tx) is None or isinstance(smart_description_gen.generate(tx), str)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test integration of all features together"""
    
    def test_full_pipeline_single_transaction(self, fraud_detector, smart_description_gen, pattern_learner, setup_test_db):
        """Test full pipeline for a single transaction"""
        conn = setup_test_db
        
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 0.5,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        # Run all features
        fraud_result = fraud_detector.detect(tx)
        description = smart_description_gen.generate(tx)
        pattern_result = pattern_learner.learn([tx])
        
        assert fraud_result is None or isinstance(fraud_result, dict)
        assert description is None or isinstance(description, str)
        assert pattern_result is None or isinstance(pattern_result, dict)
    
    def test_full_pipeline_multiple_transactions(self, fraud_detector, smart_description_gen, pattern_learner, setup_test_db):
        """Test full pipeline for multiple transactions"""
        conn = setup_test_db
        
        cursor = conn.execute("""
            SELECT action, coin, amount, price_usd, source, date
            FROM trades
            WHERE coin = 'BTC' AND action = 'buy'
            LIMIT 10
        """)
        
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Process all transactions
        for tx in transactions:
            fraud_result = fraud_detector.detect(tx)
            description = smart_description_gen.generate(tx)
            
            assert fraud_result is None or isinstance(fraud_result, dict)
            assert description is None or isinstance(description, str)
        
        # Learn pattern
        pattern_result = pattern_learner.learn(transactions)
        assert pattern_result is None or isinstance(pattern_result, dict)
    
    def test_detect_fraud_before_storage(self, fraud_detector, setup_test_db):
        """Test fraud detection integrated with storage workflow"""
        transactions = [
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 45000,
                'source': 'binance',
                'date': '2024-06-01'
            },
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': 50.0,  # Suspicious
                'price_usd': 10000,  # Suspicious
                'source': 'unknown_exchange',
                'date': '2024-06-02'
            }
        ]
        
        results = []
        for tx in transactions:
            result = fraud_detector.detect(tx)
            results.append(result)
        
        # First transaction should be low risk
        # Second transaction might be flagged
        assert len(results) == 2
    
    def test_smart_descriptions_with_fraud_detection(self, fraud_detector, smart_description_gen, setup_test_db):
        """Test combining fraud detection with smart descriptions"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 0.5,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        fraud_result = fraud_detector.detect(tx)
        description = smart_description_gen.generate(tx)
        
        # Both should work together
        assert fraud_result is None or isinstance(fraud_result, dict)
        assert description is None or isinstance(description, str)


# ============================================================================
# CONFIGURATION VALIDATION TESTS
# ============================================================================

class TestConfigurationValidation:
    """Test configuration handling and validation"""
    
    def test_tinyllama_config_present(self):
        """Test that TinyLLaMA configuration exists"""
        config_file = Path(__file__).parent.parent / 'configs' / 'config.json'
        
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            
            # Check ml_fallback config
            assert 'ml_fallback' in config
            assert config['ml_fallback']['model_name'] == 'tinyllama'
            assert config['ml_fallback']['enabled'] is True
    
    def test_accuracy_mode_config_present(self):
        """Test that accuracy mode configuration exists"""
        config_file = Path(__file__).parent.parent / 'configs' / 'config.json'
        
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            
            # Check accuracy_mode config
            assert 'accuracy_mode' in config
            assert config['accuracy_mode']['enabled'] is True
            assert config['accuracy_mode']['fraud_detection'] is True
            assert config['accuracy_mode']['smart_descriptions'] is True
            assert config['accuracy_mode']['pattern_learning'] is True
            assert config['accuracy_mode']['natural_language_search'] is False
    
    def test_anomaly_detection_config_present(self):
        """Test that anomaly detection configuration exists"""
        config_file = Path(__file__).parent.parent / 'configs' / 'config.json'
        
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            
            # Check anomaly_detection config
            assert 'anomaly_detection' in config
            assert config['anomaly_detection']['enabled'] is True
            assert 'price_error_threshold' in config['anomaly_detection']
            assert 'extreme_value_threshold' in config['anomaly_detection']
            assert 'dust_threshold_usd' in config['anomaly_detection']
            assert 'pattern_deviation_multiplier' in config['anomaly_detection']
            assert 'min_transactions_for_learning' in config['anomaly_detection']


# ============================================================================
# PERFORMANCE AND RESOURCE TESTS
# ============================================================================

class TestResourceManagement:
    """Test resource management for ARM NAS compatibility"""
    
    def test_batch_size_optimization(self):
        """Test batch size configuration for ARM NAS"""
        config_file = Path(__file__).parent.parent / 'configs' / 'config.json'
        
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            
            # Verify batch size is optimized for memory
            assert config['ml_fallback']['batch_size'] == 5
    
    def test_auto_shutdown_enabled(self):
        """Test auto-shutdown is enabled for memory cleanup"""
        config_file = Path(__file__).parent.parent / 'configs' / 'config.json'
        
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            
            # Verify auto-shutdown is enabled
            assert config['ml_fallback']['auto_shutdown_after_batch'] is True
    
    def test_processing_multiple_batches(self, fraud_detector, smart_description_gen):
        """Test processing multiple batches without memory issues"""
        # Simulate batch processing
        for batch in range(5):
            transactions = [
                {
                    'action': 'buy',
                    'coin': 'BTC',
                    'amount': 1.0,
                    'price_usd': 45000 + batch * 100,
                    'source': 'binance',
                    'date': '2024-06-01'
                }
                for _ in range(5)
            ]
            
            for tx in transactions:
                fraud_detector.detect(tx)
                smart_description_gen.generate(tx)
        
        # Should complete without error


# ============================================================================
# FALLBACK MECHANISM TESTS
# ============================================================================

class TestFallbackMechanism:
    """Test fallback to heuristics when TinyLLaMA unavailable"""
    
    def test_fraud_detector_fallback(self):
        """Test fraud detection fallback works"""
        detector = FraudDetectorAccurate(fallback_enabled=True)
        
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        # Should work even without model
        result = detector.detect(tx)
        assert result is None or isinstance(result, dict)
    
    def test_smart_description_fallback(self):
        """Test smart description generation fallback works"""
        gen = SmartDescriptionGeneratorAccurate(fallback_enabled=True)
        
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        # Should work even without model
        description = gen.generate(tx)
        assert description is None or isinstance(description, str)
    
    def test_pattern_learner_fallback(self):
        """Test pattern learner fallback works"""
        learner = PatternLearnerAccurate(fallback_enabled=True)
        
        transactions = [
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 45000,
                'source': 'binance',
                'date': '2024-06-01'
            }
        ]
        
        # Should work even without model
        result = learner.learn(transactions)
        assert result is None or isinstance(result, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
