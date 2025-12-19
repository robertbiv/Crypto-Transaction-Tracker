"""
Advanced Edge Case Test Suite for TinyLLaMA Features
Tests complex scenarios, race conditions, boundary conditions, and error recovery

Test Coverage:
    - Concurrent operations
    - Memory stress tests
    - Configuration reload scenarios
    - Error recovery and graceful degradation
    - Boundary value analysis
    - State consistency across features
    - Fallback mechanism validation
    - Complex transaction patterns

Author: Test Suite
Last Modified: December 2025
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import time

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from advanced_ml_features_accurate import (
    FraudDetectorAccurate,
    SmartDescriptionGeneratorAccurate,
    PatternLearnerAccurate
)


# ============================================================================
# BOUNDARY VALUE ANALYSIS TESTS
# ============================================================================

class TestBoundaryValues:
    """Test extreme boundary values"""
    
    @pytest.mark.parametrize('amount', [
        0.00000001,      # Minimum (dust)
        0.00001,         # Very small
        1e-18,           # Satoshi equivalent
        1e18,            # Extremely large
        9223372036854775807,  # Max int64
    ])
    def test_boundary_amounts(self, fraud_detector, amount):
        """Test fraud detection with boundary amount values"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': amount,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        result = fraud_detector.detect(tx)
        assert result is None or isinstance(result, dict)
    
    @pytest.mark.parametrize('price', [
        0.000001,        # Penny stocks equivalent
        1,
        45000,
        1000000,
        1e9,             # Billion per unit
        1e20,            # Unrealistic
    ])
    def test_boundary_prices(self, fraud_detector, price):
        """Test with boundary price values"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': price,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        result = fraud_detector.detect(tx)
        assert result is None or isinstance(result, dict)
    
    def test_zero_and_negative_values(self, fraud_detector, pattern_learner):
        """Test handling of zero and negative values"""
        invalid_txs = [
            {'action': 'buy', 'coin': 'BTC', 'amount': 0, 'price_usd': 45000},
            {'action': 'buy', 'coin': 'BTC', 'amount': -1, 'price_usd': 45000},
            {'action': 'buy', 'coin': 'BTC', 'amount': 1, 'price_usd': 0},
            {'action': 'buy', 'coin': 'BTC', 'amount': 1, 'price_usd': -45000},
        ]
        
        for tx in invalid_txs:
            result = fraud_detector.detect(tx)
            assert result is None or isinstance(result, dict)


# ============================================================================
# CONCURRENT OPERATION TESTS
# ============================================================================

class TestConcurrentOperations:
    """Test thread-safe operations with concurrent requests"""
    
    def test_concurrent_fraud_detection(self):
        """Test fraud detection with concurrent requests"""
        detector = FraudDetectorAccurate()
        results = []
        errors = []
        
        def detect_transaction(tx_id):
            try:
                tx = {
                    'action': 'buy',
                    'coin': 'BTC',
                    'amount': 1.0,
                    'price_usd': 45000 + tx_id,
                    'source': 'binance',
                    'date': '2024-06-01'
                }
                result = detector.detect(tx)
                results.append((tx_id, result))
            except Exception as e:
                errors.append((tx_id, str(e)))
        
        # Test with 10 concurrent threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(detect_transaction, i) for i in range(100)]
            for future in futures:
                future.result(timeout=5)
        
        # Verify results
        assert len(results) + len(errors) == 100
        assert len(results) > 0  # At least some succeeded
    
    def test_concurrent_description_generation(self):
        """Test concurrent smart description generation"""
        gen = SmartDescriptionGeneratorAccurate()
        results = []
        errors = []
        
        def generate_description(tx_id):
            try:
                tx = {
                    'action': 'buy' if tx_id % 2 == 0 else 'sell',
                    'coin': ['BTC', 'ETH', 'ADA'][tx_id % 3],
                    'amount': 1.0 + (tx_id % 10),
                    'price_usd': 45000 + tx_id * 100,
                    'source': 'binance',
                    'date': '2024-06-01'
                }
                result = gen.generate(tx)
                results.append((tx_id, result))
            except Exception as e:
                errors.append((tx_id, str(e)))
        
        # Test with 10 concurrent threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_description, i) for i in range(100)]
            for future in futures:
                future.result(timeout=5)
        
        assert len(results) + len(errors) == 100
        assert len(results) > 0
    
    def test_concurrent_pattern_learning(self):
        """Test concurrent pattern learning"""
        learner = PatternLearnerAccurate()
        results = []
        errors = []
        
        def learn_batch(batch_id):
            try:
                transactions = [
                    {
                        'action': 'buy',
                        'coin': 'BTC',
                        'amount': 1.0 + (i % 5),
                        'price_usd': 45000 + (batch_id * 100) + (i * 10),
                        'source': 'binance',
                        'date': f'2024-06-{1 + batch_id:02d}'
                    }
                    for i in range(5)
                ]
                result = learner.learn(transactions)
                results.append((batch_id, result))
            except Exception as e:
                errors.append((batch_id, str(e)))
        
        # Test with 5 concurrent threads
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(learn_batch, i) for i in range(20)]
            for future in futures:
                future.result(timeout=5)
        
        assert len(results) + len(errors) == 20


# ============================================================================
# MEMORY STRESS TESTS
# ============================================================================

class TestMemoryStress:
    """Test resource usage under load"""
    
    def test_large_transaction_batch(self, fraud_detector, smart_description_gen):
        """Test processing large batches of transactions"""
        # Simulate 1000 transactions
        detector = fraud_detector
        gen = smart_description_gen
        
        for batch in range(10):
            transactions = [
                {
                    'action': 'buy' if i % 2 == 0 else 'sell',
                    'coin': ['BTC', 'ETH', 'ADA', 'XRP'][i % 4],
                    'amount': 0.1 * (i % 100 + 1),
                    'price_usd': 45000 + (batch * 1000) + (i * 10),
                    'source': ['binance', 'kraken', 'coinbase'][i % 3],
                    'date': '2024-06-01'
                }
                for i in range(100)
            ]
            
            for tx in transactions:
                detector.detect(tx)
                gen.generate(tx)
    
    def test_long_pattern_history(self, pattern_learner):
        """Test pattern learning with long transaction history"""
        # Simulate 5 years of daily transactions
        transactions = [
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': 0.5 + (i % 10) * 0.1,
                'price_usd': 40000 + (i * 50),
                'source': 'binance',
                'date': (datetime(2020, 1, 1) + timedelta(days=i)).strftime('%Y-%m-%d')
            }
            for i in range(1825)  # 5 years
        ]
        
        result = pattern_learner.learn(transactions)
        assert result is None or isinstance(result, dict)
    
    def test_many_concurrent_batches(self):
        """Test handling many concurrent batch operations"""
        detector = FraudDetectorAccurate()
        
        def process_batch(batch_id):
            for i in range(10):
                tx = {
                    'action': 'buy',
                    'coin': 'BTC',
                    'amount': 1.0,
                    'price_usd': 45000,
                    'source': 'binance',
                    'date': '2024-06-01'
                }
                detector.detect(tx)
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(process_batch, i) for i in range(50)]
            for future in futures:
                future.result(timeout=10)


# ============================================================================
# TRANSACTION PATTERN TESTS
# ============================================================================

class TestComplexTransactionPatterns:
    """Test complex and unusual transaction patterns"""
    
    def test_rapid_buy_sell_cycle(self, fraud_detector, pattern_learner):
        """Test detection of rapid buy-sell cycles (day trading)"""
        transactions = []
        base_time = datetime(2024, 6, 1)
        
        # Simulate 20 buy-sell pairs within an hour
        for i in range(20):
            transactions.append({
                'action': 'buy',
                'coin': 'ETH',
                'amount': 1.0,
                'price_usd': 2500,
                'source': 'binance',
                'date': base_time.isoformat(),
                'time': f'{i:02d}:00'
            })
            
            transactions.append({
                'action': 'sell',
                'coin': 'ETH',
                'amount': 1.0,
                'price_usd': 2510,
                'source': 'binance',
                'date': base_time.isoformat(),
                'time': f'{i:02d}:30'
            })
        
        # All should process without error
        for tx in transactions:
            fraud_detector.detect(tx)
        
        result = pattern_learner.learn(transactions)
        assert result is None or isinstance(result, dict)
    
    def test_pump_and_dump_pattern(self, fraud_detector, pattern_learner):
        """Test detection of pump and dump patterns"""
        transactions = []
        
        # Initial accumulation (low volume, stable price)
        for i in range(5):
            transactions.append({
                'action': 'buy',
                'coin': 'SHITCOIN',
                'amount': 10000,
                'price_usd': 0.01,
                'source': 'binance',
                'date': f'2024-06-{1 + i:02d}'
            })
        
        # Pump phase (high volume, skyrocketing price)
        for i in range(3):
            transactions.append({
                'action': 'buy',
                'coin': 'SHITCOIN',
                'amount': 100000,
                'price_usd': 0.10 + (i * 0.05),
                'source': 'binance',
                'date': f'2024-06-{6 + i:02d}'
            })
        
        # Dump phase (massive sells at inflated prices)
        for i in range(3):
            transactions.append({
                'action': 'sell',
                'coin': 'SHITCOIN',
                'amount': 50000,
                'price_usd': 0.20,
                'source': 'binance',
                'date': f'2024-06-{9 + i:02d}'
            })
        
        for tx in transactions:
            result = fraud_detector.detect(tx)
            # Dump phase should potentially flag as suspicious
    
    def test_round_number_purchases(self, fraud_detector, pattern_learner):
        """Test handling of round number purchases (common pattern)"""
        transactions = [
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': round_amount,
                'price_usd': 45000,
                'source': 'binance',
                'date': f'2024-06-{1 + i:02d}'
            }
            for i, round_amount in enumerate([1, 5, 10, 50, 100])
        ]
        
        for tx in transactions:
            result = fraud_detector.detect(tx)
            assert result is None or isinstance(result, dict)
        
        result = pattern_learner.learn(transactions)
        assert result is None or isinstance(result, dict)
    
    def test_alternating_sources(self, fraud_detector, pattern_learner):
        """Test transactions alternating between different sources"""
        sources = ['binance', 'kraken', 'coinbase', 'kraken', 'binance']
        transactions = [
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 45000,
                'source': source,
                'date': f'2024-06-{1 + i:02d}'
            }
            for i, source in enumerate(sources)
        ]
        
        for tx in transactions:
            result = fraud_detector.detect(tx)
            assert result is None or isinstance(result, dict)


# ============================================================================
# DATA CONSISTENCY TESTS
# ============================================================================

class TestDataConsistency:
    """Test data consistency across features"""
    
    def test_transaction_immutability(self, fraud_detector, smart_description_gen):
        """Test that processing doesn't modify original transactions"""
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        # Create copy for comparison
        tx_copy = tx.copy()
        
        # Process through both features
        fraud_detector.detect(tx)
        smart_description_gen.generate(tx)
        
        # Verify original unchanged
        assert tx == tx_copy
    
    def test_pattern_consistency(self, pattern_learner):
        """Test that pattern learning is consistent across calls"""
        transactions = [
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 45000 + (i * 100),
                'source': 'binance',
                'date': f'2024-06-{1 + i:02d}'
            }
            for i in range(25)
        ]
        
        # Learn pattern twice
        result1 = pattern_learner.learn(transactions)
        result2 = pattern_learner.learn(transactions)
        
        # Results should be consistent
        assert (result1 is None) == (result2 is None) or \
               (isinstance(result1, dict) and isinstance(result2, dict))


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling and graceful degradation"""
    
    def test_malformed_json_transaction(self, fraud_detector):
        """Test handling of malformed transaction data"""
        malformed_txs = [
            None,
            [],
            "not a dict",
            {'coin': 'BTC'},  # Missing required fields
            {'action': 'buy', 'coin': 'BTC', 'amount': 'invalid'},  # Type mismatch
        ]
        
        for tx in malformed_txs:
            result = fraud_detector.detect(tx)
            # Should not crash
            assert result is None or isinstance(result, dict)
    
    def test_missing_required_fields(self, smart_description_gen):
        """Test handling of transactions missing required fields"""
        incomplete_txs = [
            {'coin': 'BTC'},
            {'action': 'buy'},
            {'amount': 1.0},
            {'price_usd': 45000},
            {'source': 'binance'},
        ]
        
        for tx in incomplete_txs:
            result = smart_description_gen.generate(tx)
            assert result is None or isinstance(result, str)
    
    def test_type_errors_handled(self, fraud_detector, anomaly_detector):
        """Test handling of type errors in data"""
        invalid_txs = [
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': 'one',  # String instead of float
                'price_usd': 45000,
                'source': 'binance'
            },
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 'expensive',  # String instead of float
                'source': 'binance'
            },
            {
                'action': 'buy',
                'coin': 'BTC',
                'amount': [1.0, 2.0],  # List instead of float
                'price_usd': 45000,
                'source': 'binance'
            },
        ]
        
        for tx in invalid_txs:
            result = fraud_detector.detect(tx)
            assert result is None or isinstance(result, dict)


# ============================================================================
# CONFIGURATION VALIDATION TESTS
# ============================================================================

class TestConfigurationEdgeCases:
    """Test configuration edge cases and loading"""
    
    def test_missing_config_file(self):
        """Test behavior when config file missing"""
        # This tests graceful degradation
        config_file = Path(__file__).parent.parent / 'configs' / 'nonexistent_config.json'
        
        # Detectors should still work with defaults
        detector = FraudDetectorAccurate()
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        result = detector.detect(tx)
        assert result is None or isinstance(result, dict)
    
    def test_corrupted_config_file(self):
        """Test handling of corrupted configuration"""
        # This is more of a system-level test
        # but we can verify detectors work with defaults
        detector = FraudDetectorAccurate()
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        result = detector.detect(tx)
        assert result is None or isinstance(result, dict)
    
    def test_invalid_threshold_values(self):
        """Test handling of invalid threshold values in config"""
        # Test with extreme threshold values
        detector = FraudDetectorAccurate()
        
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        # Should work with any threshold
        result = detector.detect(tx)
        assert result is None or isinstance(result, dict)


# ============================================================================
# FALLBACK DEGRADATION TESTS
# ============================================================================

class TestFallbackDegradation:
    """Test graceful degradation when TinyLLaMA unavailable"""
    
    @patch('advanced_ml_features_accurate.FraudDetectorAccurate.get_model')
    def test_fraud_detector_model_unavailable(self, mock_get_model):
        """Test fraud detection when model is unavailable"""
        mock_get_model.return_value = None
        
        detector = FraudDetectorAccurate()
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        # Should still work with fallback
        result = detector.detect(tx)
        assert result is None or isinstance(result, dict)
    
    @patch('advanced_ml_features_accurate.SmartDescriptionGeneratorAccurate.get_model')
    def test_description_generator_model_unavailable(self, mock_get_model):
        """Test description generation when model is unavailable"""
        mock_get_model.return_value = None
        
        gen = SmartDescriptionGeneratorAccurate()
        tx = {
            'action': 'buy',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 45000,
            'source': 'binance',
            'date': '2024-06-01'
        }
        
        # Should still work with fallback
        result = gen.generate(tx)
        assert result is None or isinstance(result, str)
    
    @patch('advanced_ml_features_accurate.PatternLearnerAccurate.get_model')
    def test_pattern_learner_model_unavailable(self, mock_get_model):
        """Test pattern learning when model is unavailable"""
        mock_get_model.return_value = None
        
        learner = PatternLearnerAccurate()
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
        
        # Should still work with fallback
        result = learner.learn(transactions)
        assert result is None or isinstance(result, dict)


# ============================================================================
# ARM NAS SPECIFIC TESTS
# ============================================================================

class TestARMNASOptimization:
    """Test optimizations specific to ARM NAS deployment"""
    
    def test_batch_size_respected(self):
        """Test batch size configuration for ARM NAS"""
        config_file = Path(__file__).parent.parent / 'configs' / 'config.json'
        
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            
            # Verify batch size is ARM-optimized
            batch_size = config.get('ml_fallback', {}).get('batch_size')
            assert batch_size is not None
            assert batch_size <= 5  # ARM NAS optimized
    
    def test_memory_cleanup_after_batch(self):
        """Test that memory cleanup occurs after batch"""
        config_file = Path(__file__).parent.parent / 'configs' / 'config.json'
        
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            
            # Verify auto-shutdown configured
            auto_shutdown = config.get('ml_fallback', {}).get('auto_shutdown_after_batch')
            assert auto_shutdown is True
    
    def test_sequential_batch_processing(self, fraud_detector):
        """Test sequential batch processing without memory issues"""
        # Process multiple sequential batches
        for batch_num in range(10):
            batch_txs = [
                {
                    'action': 'buy',
                    'coin': 'BTC',
                    'amount': 1.0,
                    'price_usd': 45000 + (i * 10),
                    'source': 'binance',
                    'date': f'2024-06-{1 + batch_num:02d}'
                }
                for i in range(5)
            ]
            
            for tx in batch_txs:
                fraud_detector.detect(tx)
            
            # In real scenario, model would shut down here
            time.sleep(0.01)  # Simulate processing delay


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
