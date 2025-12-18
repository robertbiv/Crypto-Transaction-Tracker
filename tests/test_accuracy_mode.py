"""
Test Suite - Accuracy Mode (Gemma-Enhanced Features)
Tests for advanced ML features with optional Gemma integration.

Tests:
    - FraudDetectorAccurate (context-aware fraud detection)
    - SmartDescriptionGeneratorAccurate (creative descriptions)
    - PatternLearnerAccurate (behavioral analysis)
    - NaturalLanguageSearchAccurate (NLP search)
    - AccuracyModeController (unified control)

Author: Test Suite
Last Modified: December 2025
"""

import pytest
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta


@pytest.fixture(scope='module')
def setup_test_db():
    """Setup test database with sample transactions"""
    db_file = Path('test_accuracy_mode.db')
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
    
    # Insert sample transactions
    base_date = datetime(2024, 1, 1)
    sample_txs = [
        # Normal buy
        (base_date.isoformat(), 'BUY', 'BTC', 0.1, 42000, 'manual', 'Buy BTC'),
        ((base_date + timedelta(days=5)).isoformat(), 'BUY', 'BTC', 0.1, 41000, 'manual', 'Buy dip'),
        ((base_date + timedelta(days=10)).isoformat(), 'SELL', 'BTC', 0.1, 44000, 'manual', 'Sell profit'),
        
        # Wash sale pattern
        ((base_date + timedelta(days=20)).isoformat(), 'BUY', 'ETH', 5, 2000, 'manual', 'Buy ETH'),
        ((base_date + timedelta(days=25)).isoformat(), 'SELL', 'ETH', 5, 1900, 'manual', 'Sell ETH loss'),
        
        # Large transaction
        ((base_date + timedelta(days=40)).isoformat(), 'BUY', 'DOGE', 100000, 0.25, 'manual', 'Large DOGE'),
        
        # DeFi activity
        ((base_date + timedelta(days=50)).isoformat(), 'TRADE', 'UNI', 100, 5, 'uniswap', 'Uniswap swap'),
        ((base_date + timedelta(days=51)).isoformat(), 'INCOME', 'AAVE', 10, 300, 'aave', 'Aave reward'),
    ]
    
    for tx in sample_txs:
        conn.execute("""
            INSERT INTO trades (date, action, coin, amount, price_usd, source, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, tx)
    
    conn.commit()
    yield conn, db_file
    
    conn.close()
    if db_file.exists():
        db_file.unlink()


class MockMLService:
    """Mock ML service for testing without Gemma"""
    
    def infer(self, prompt: str) -> str:
        """Return mock inference result"""
        if 'fraud' in prompt.lower():
            return json.dumps({
                'wash_sales': [],
                'contextual_flags': ['High volatility detected'],
                'confidence': 0.85
            })
        elif 'description' in prompt.lower():
            return json.dumps({'description': 'Sold at market top'})
        elif 'behavior' in prompt.lower():
            return json.dumps({
                'user_profile': {'profile': 'Conservative trader'},
                'anomalies': []
            })
        else:
            return json.dumps({'results': [], 'interpretation': 'query'})


class TestFraudDetectorAccurate:
    """Test accuracy-enhanced fraud detection"""
    
    def test_import(self):
        """Test that accurate fraud detector can be imported"""
        from src.advanced_ml_features_accurate import FraudDetectorAccurate
        assert FraudDetectorAccurate is not None
    
    def test_without_ml_service(self, setup_test_db):
        """Test fallback to heuristics when ML unavailable"""
        from src.advanced_ml_features_accurate import FraudDetectorAccurate
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        detector = FraudDetectorAccurate(ml_service=None)
        result = detector.detect_fraud_comprehensive(transactions)
        
        assert result['use_gemma'] == False
        assert 'wash_sales' in result
        assert isinstance(result['wash_sales'], list)
    
    def test_with_mock_ml_service(self, setup_test_db):
        """Test with mock ML service"""
        from src.advanced_ml_features_accurate import FraudDetectorAccurate
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        ml_service = MockMLService()
        detector = FraudDetectorAccurate(ml_service=ml_service)
        result = detector.detect_fraud_comprehensive(transactions)
        
        assert result['use_gemma'] == True
        assert 'gemma_analysis' in result


class TestSmartDescriptionGeneratorAccurate:
    """Test accuracy-enhanced descriptions"""
    
    def test_import(self):
        """Test that accurate generator can be imported"""
        from src.advanced_ml_features_accurate import SmartDescriptionGeneratorAccurate
        assert SmartDescriptionGeneratorAccurate is not None
    
    def test_without_ml_service(self, setup_test_db):
        """Test fallback to heuristics"""
        from src.advanced_ml_features_accurate import SmartDescriptionGeneratorAccurate
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades LIMIT 1")
        tx = dict(cursor.fetchone())
        
        generator = SmartDescriptionGeneratorAccurate(ml_service=None)
        result = generator.generate_description_smart(tx)
        
        assert 'description' in result
        assert result['source'] == 'heuristic'
        assert result['confidence'] == 0.6
    
    def test_with_mock_ml_service(self, setup_test_db):
        """Test with mock ML service"""
        from src.advanced_ml_features_accurate import SmartDescriptionGeneratorAccurate
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades LIMIT 1")
        tx = dict(cursor.fetchone())
        
        ml_service = MockMLService()
        generator = SmartDescriptionGeneratorAccurate(ml_service=ml_service)
        result = generator.generate_description_smart(tx)
        
        assert 'description' in result
        assert result['source'] == 'gemma'


class TestPatternLearnerAccurate:
    """Test accuracy-enhanced pattern learning"""
    
    def test_import(self):
        """Test that accurate learner can be imported"""
        from src.advanced_ml_features_accurate import PatternLearnerAccurate
        assert PatternLearnerAccurate is not None
    
    def test_without_ml_service(self, setup_test_db):
        """Test statistical analysis without ML"""
        from src.advanced_ml_features_accurate import PatternLearnerAccurate
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        learner = PatternLearnerAccurate(ml_service=None)
        result = learner.learn_and_detect_accurate(transactions)
        
        assert result['use_gemma'] == False
        assert 'statistical_anomalies' in result
        assert isinstance(result['statistical_anomalies'], list)
    
    def test_with_mock_ml_service(self, setup_test_db):
        """Test behavioral analysis with mock ML"""
        from src.advanced_ml_features_accurate import PatternLearnerAccurate
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        ml_service = MockMLService()
        learner = PatternLearnerAccurate(ml_service=ml_service)
        result = learner.learn_and_detect_accurate(transactions)
        
        assert result['use_gemma'] == True
        assert 'behavioral_anomalies' in result
        assert 'user_profile' in result


class TestNaturalLanguageSearchAccurate:
    """Test accuracy-enhanced NLS"""
    
    def test_import(self):
        """Test that accurate NLS can be imported"""
        from src.advanced_ml_features_accurate import NaturalLanguageSearchAccurate
        assert NaturalLanguageSearchAccurate is not None
    
    def test_without_ml_service(self, setup_test_db):
        """Test regex search without ML"""
        from src.advanced_ml_features_accurate import NaturalLanguageSearchAccurate
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        searcher = NaturalLanguageSearchAccurate(ml_service=None)
        result = searcher.search_accurate(transactions, "BTC transactions")
        
        assert result['use_gemma'] == False
        assert result['source'] == 'regex'
        assert 'results' in result
    
    def test_with_mock_ml_service(self, setup_test_db):
        """Test NLP search with mock ML"""
        from src.advanced_ml_features_accurate import NaturalLanguageSearchAccurate
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        ml_service = MockMLService()
        searcher = NaturalLanguageSearchAccurate(ml_service=ml_service)
        result = searcher.search_accurate(transactions, "My biggest BTC buys")
        
        assert result['use_gemma'] == True
        assert result['source'] == 'gemma'


class TestAccuracyModeController:
    """Test unified accuracy mode controller"""
    
    def test_import(self):
        """Test that controller can be imported"""
        from src.advanced_ml_features_accurate import AccuracyModeController
        assert AccuracyModeController is not None
    
    def test_initialization_without_ml(self, setup_test_db):
        """Test initialization without ML service"""
        from src.advanced_ml_features_accurate import AccuracyModeController
        
        controller = AccuracyModeController(ml_service=None, enabled=False)
        assert controller.enabled == False
    
    def test_initialization_with_ml(self):
        """Test initialization with ML service"""
        from src.advanced_ml_features_accurate import AccuracyModeController
        
        ml_service = MockMLService()
        controller = AccuracyModeController(ml_service=ml_service, enabled=True)
        assert controller.enabled == True
    
    def test_fraud_detection_modes(self, setup_test_db):
        """Test fraud detection with different modes"""
        from src.advanced_ml_features_accurate import AccuracyModeController
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        ml_service = MockMLService()
        controller = AccuracyModeController(ml_service=ml_service, enabled=True)
        
        # Accurate mode
        result_accurate = controller.detect_fraud(transactions, mode='accurate')
        assert result_accurate is not None
        
        # Fast mode
        result_fast = controller.detect_fraud(transactions, mode='fast')
        assert result_fast is not None
    
    def test_description_generation_modes(self, setup_test_db):
        """Test description generation with different modes"""
        from src.advanced_ml_features_accurate import AccuracyModeController
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades LIMIT 1")
        tx = dict(cursor.fetchone())
        
        ml_service = MockMLService()
        controller = AccuracyModeController(ml_service=ml_service, enabled=True)
        
        # Accurate mode
        result_accurate = controller.generate_description(tx, mode='accurate')
        assert 'description' in result_accurate
        
        # Fast mode
        result_fast = controller.generate_description(tx, mode='fast')
        assert 'description' in result_fast
    
    def test_pattern_analysis_modes(self, setup_test_db):
        """Test pattern analysis with different modes"""
        from src.advanced_ml_features_accurate import AccuracyModeController
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        ml_service = MockMLService()
        controller = AccuracyModeController(ml_service=ml_service, enabled=True)
        
        # Accurate mode
        result_accurate = controller.analyze_patterns(transactions, mode='accurate')
        assert 'anomalies' in result_accurate or 'behavioral_anomalies' in result_accurate
        
        # Fast mode
        result_fast = controller.analyze_patterns(transactions, mode='fast')
        assert 'anomalies' in result_fast
    
    def test_search_modes(self, setup_test_db):
        """Test search with different modes"""
        from src.advanced_ml_features_accurate import AccuracyModeController
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        ml_service = MockMLService()
        controller = AccuracyModeController(ml_service=ml_service, enabled=True)
        
        query = "Show my BTC buys"
        
        # Accurate mode
        result_accurate = controller.search_transactions(transactions, query, mode='accurate')
        assert 'results' in result_accurate
        
        # Fast mode
        result_fast = controller.search_transactions(transactions, query, mode='fast')
        assert 'results' in result_fast


class TestAccuracyModeIntegration:
    """Integration tests for accuracy mode"""
    
    def test_config_loading(self):
        """Test that config can be loaded"""
        import json
        from pathlib import Path
        import importlib
        
        # Reload config to ensure fresh read
        config_file = Path('configs/config.json')
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Check if accuracy_mode exists, if not it's ok (backward compatible)
            assert isinstance(config, dict)
    
    def test_workflow_with_config(self, setup_test_db):
        """Test complete workflow with config"""
        from src.advanced_ml_features_accurate import AccuracyModeController
        import json
        from pathlib import Path
        
        conn, _ = setup_test_db
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Load config
        config_file = Path('configs/config.json')
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            accuracy_config = config.get('accuracy_mode', {})
            enabled = accuracy_config.get('enabled', True)
            
            # Create controller with config
            ml_service = MockMLService()
            controller = AccuracyModeController(ml_service=ml_service, enabled=enabled)
            
            # Run analysis
            fraud_result = controller.detect_fraud(transactions, mode='accurate')
            assert fraud_result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
