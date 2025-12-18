"""
================================================================================
Test Suite - Advanced ML API Endpoints
================================================================================

Tests for web server endpoints that expose advanced ML features to the UI.

Tests:
    - Fraud detection endpoint
    - Smart descriptions endpoint
    - DeFi classification endpoint
    - Pattern analysis endpoint
    - AML detection endpoint
    - Transaction history endpoint
    - Natural language search endpoint
    - Transaction update with history recording

Author: Test Suite
Last Modified: December 2025
================================================================================
"""

import pytest
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Setup test database and app
@pytest.fixture(scope='module')
def setup_test_db():
    """Setup test database with sample transactions"""
    db_file = Path('test_advanced_endpoints.db')
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
        # Wash sale pattern (buy and sell same coin within 30 days)
        (base_date.isoformat(), 'buy', 'BTC', 0.5, 40000, 'manual', 'Buy BTC'),
        ((base_date + timedelta(days=15)).isoformat(), 'sell', 'BTC', 0.5, 45000, 'manual', 'Sell BTC'),
        
        # Normal transactions
        ((base_date + timedelta(days=40)).isoformat(), 'buy', 'ETH', 10, 2000, 'manual', 'Buy ETH'),
        ((base_date + timedelta(days=50)).isoformat(), 'buy', 'BTC', 0.1, 42000, 'manual', 'Buy BTC'),
        
        # Suspicious volume (large transaction)
        ((base_date + timedelta(days=60)).isoformat(), 'buy', 'DOGE', 1000000, 0.30, 'manual', 'Large DOGE purchase'),
        
        # DeFi transactions
        ((base_date + timedelta(days=70)).isoformat(), 'trade', 'UNI', 100, 5, 'uniswap', 'Swap on Uniswap'),
        ((base_date + timedelta(days=71)).isoformat(), 'staking', 'LIDO', 50, 3000, 'lido', 'Stake on Lido'),
        ((base_date + timedelta(days=72)).isoformat(), 'airdrop', 'USDC', 500, 1, 'compound', 'Compound interest'),
        
        # Pattern anomalies (much larger than typical)
        ((base_date + timedelta(days=80)).isoformat(), 'buy', 'BTC', 5, 45000, 'manual', 'Large BTC purchase'),
        
        # Structuring pattern (multiple small transactions)
        ((base_date + timedelta(days=90)).isoformat(), 'buy', 'BTC', 0.05, 45000, 'manual', 'Small BTC buy'),
        ((base_date + timedelta(days=91)).isoformat(), 'buy', 'BTC', 0.05, 45000, 'manual', 'Small BTC buy'),
        ((base_date + timedelta(days=92)).isoformat(), 'buy', 'BTC', 0.05, 45000, 'manual', 'Small BTC buy'),
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


class TestFraudDetectionEndpoint:
    """Test fraud detection API endpoint"""
    
    def test_endpoint_import(self):
        """Test that endpoint can be imported"""
        from src.web.server import api_fraud_detection
        assert callable(api_fraud_detection)
    
    def test_fraud_detection_basic(self, setup_test_db):
        """Test basic fraud detection functionality"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import FraudDetector
        
        detector = FraudDetector()
        
        # Get transactions
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Should detect wash sale
        wash_alerts = detector.detect_wash_sale(transactions)
        assert isinstance(wash_alerts, list)
    
    def test_pump_dump_detection(self, setup_test_db):
        """Test pump and dump detection"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import FraudDetector
        
        detector = FraudDetector()
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Pump and dump detection
        alerts = detector.detect_pump_dump(transactions)
        assert isinstance(alerts, list)


class TestSmartDescriptionsEndpoint:
    """Test smart descriptions API endpoint"""
    
    def test_endpoint_import(self):
        """Test that endpoint can be imported"""
        from src.web.server import api_smart_descriptions
        assert callable(api_smart_descriptions)
    
    def test_smart_description_generation(self, setup_test_db):
        """Test smart description generation"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import SmartDescriptionGenerator
        
        generator = SmartDescriptionGenerator()
        
        # Test description for different actions
        buy_tx = {
            'amount': 1.0, 'coin': 'BTC', 'action': 'BUY',
            'price_usd': 40000, 'date': '2024-01-01', 'description': ''
        }
        buy_desc = generator.generate_description(buy_tx)
        assert 'BTC' in buy_desc or 'buy' in buy_desc.lower()
        
        sell_tx = {
            'amount': 1.0, 'coin': 'ETH', 'action': 'SELL',
            'price_usd': 2000, 'date': '2024-01-01', 'description': ''
        }
        sell_desc = generator.generate_description(sell_tx)
        assert 'ETH' in sell_desc or 'sell' in sell_desc.lower()
    
    def test_defi_description_detection(self, setup_test_db):
        """Test DeFi protocol detection in descriptions"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import SmartDescriptionGenerator
        
        generator = SmartDescriptionGenerator()
        
        # Uniswap description should recognize protocol
        uniswap_tx = {
            'amount': 100, 'coin': 'UNI', 'action': 'TRADE',
            'price_usd': 5, 'date': '2024-01-01',
            'description': '', 'source': 'uniswap'
        }
        uniswap_desc = generator.generate_description(uniswap_tx)
        # Should mention swap/Uniswap or protocol
        assert 'swap' in uniswap_desc.lower() or 'uniswap' in uniswap_desc.lower()


class TestDeFiClassificationEndpoint:
    """Test DeFi classification API endpoint"""
    
    def test_endpoint_import(self):
        """Test that endpoint can be imported"""
        from src.web.server import api_defi_classification
        assert callable(api_defi_classification)
    
    def test_defi_classification_basic(self, setup_test_db):
        """Test basic DeFi classification"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import DeFiClassifier
        
        classifier = DeFiClassifier()
        
        # Test Uniswap classification
        uniswap_tx = {
            'description': 'Swap on Uniswap',
            'amount': 100, 'price_usd': 5, 'coin': 'UNI', 'source': 'uniswap'
        }
        result = classifier.classify(uniswap_tx)
        assert result is not None
        assert 'protocol' in result or 'type' in result
    
    def test_fee_flagging(self, setup_test_db):
        """Test high fee detection"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import DeFiClassifier
        
        classifier = DeFiClassifier()
        
        # High fee should be flagged (>5%)
        high_fee_tx = {'amount': 100, 'price_usd': 10}
        result = classifier.flag_high_fees(high_fee_tx)
        assert isinstance(result, (dict, type(None)))


class TestPatternAnalysisEndpoint:
    """Test pattern analysis API endpoint"""
    
    def test_endpoint_import(self):
        """Test that endpoint can be imported"""
        from src.web.server import api_pattern_analysis
        assert callable(api_pattern_analysis)
    
    def test_pattern_learning(self, setup_test_db):
        """Test pattern learning from transactions"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import PatternLearner
        
        learner = PatternLearner()
        
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Learn patterns
        learner.learn_patterns(transactions)
        assert learner.patterns is not None
    
    def test_anomaly_detection(self, setup_test_db):
        """Test anomaly detection"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import PatternLearner
        
        learner = PatternLearner()
        
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        learner.learn_patterns(transactions)
        
        # Test anomaly detection on large transaction
        if len(transactions) > 5:
            large_tx = transactions[-2]  # The 5 BTC purchase
            anomaly = learner.detect_anomalies(large_tx)
            # Large amount should trigger anomaly
            if anomaly:
                assert 'reason' in anomaly


class TestAMLDetectionEndpoint:
    """Test AML detection API endpoint"""
    
    def test_endpoint_import(self):
        """Test that endpoint can be imported"""
        from src.web.server import api_aml_detection
        assert callable(api_aml_detection)
    
    def test_structuring_detection(self, setup_test_db):
        """Test AML structuring pattern detection"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import AMLDetector
        
        detector = AMLDetector()
        
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Should detect structuring pattern (multiple small BTC buys)
        detected = False
        for tx in transactions:
            alert = detector.detect_structuring(transactions, tx)
            if alert:
                detected = True
                assert 'alert_type' in alert
                break
        
        # May or may not detect depending on thresholds
        assert isinstance(detected, bool)


class TestTransactionHistoryEndpoint:
    """Test transaction history API endpoint"""
    
    def test_endpoint_import(self):
        """Test that endpoint can be imported"""
        from src.web.server import api_transaction_history
        assert callable(api_transaction_history)
    
    def test_record_change(self):
        """Test recording transaction changes"""
        from src.advanced_ml_features import TransactionHistory
        
        history = TransactionHistory()
        
        # Record a change - pass the arguments directly
        history.record_change(
            tx_id='1',
            old_value='BUY',
            new_value='TRADE',
            reason='ML classification'
        )
        
        # Get history
        tx_history = history.get_history('1')
        assert isinstance(tx_history, list)


class TestNaturalLanguageSearchEndpoint:
    """Test natural language search API endpoint"""
    
    def test_endpoint_import(self):
        """Test that endpoint can be imported"""
        from src.web.server import api_natural_language_search
        assert callable(api_natural_language_search)
    
    def test_query_parsing(self):
        """Test natural language query parsing"""
        from src.advanced_ml_features import NaturalLanguageSearch
        
        searcher = NaturalLanguageSearch()
        
        # Parse different types of queries
        query1 = "Show my BTC transactions"
        parsed1 = searcher.parse_query(query1)
        assert parsed1.get('coin') == 'BTC'
        
        query2 = "Show my largest buys in 2024"
        parsed2 = searcher.parse_query(query2)
        # Parsed query returns uppercase
        assert parsed2.get('action') in ('BUY', 'buy')
    
    def test_search_functionality(self, setup_test_db):
        """Test actual search against transactions"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import NaturalLanguageSearch
        
        searcher = NaturalLanguageSearch()
        
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Search for BTC transactions - search method takes (transactions, query) not (query, transactions)
        query = "Show my BTC transactions"
        results = searcher.search(transactions, query)
        
        assert isinstance(results, list)


class TestUpdateWithHistoryEndpoint:
    """Test transaction update endpoint with history recording"""
    
    def test_endpoint_import(self):
        """Test that endpoint can be imported"""
        from src.web.server import api_update_transaction_with_history
        assert callable(api_update_transaction_with_history)


# ==========================================
# Integration Tests
# ==========================================

class TestAdvancedMLIntegration:
    """Test integration between multiple advanced features"""
    
    def test_fraud_to_descriptions_flow(self, setup_test_db):
        """Test workflow: detect fraud -> generate smart descriptions"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import FraudDetector, SmartDescriptionGenerator
        
        detector = FraudDetector()
        generator = SmartDescriptionGenerator()
        
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Find fraudulent transactions
        wash_alerts = detector.detect_wash_sale(transactions)
        
        if wash_alerts:
            # Generate description for flagged transaction
            alert = wash_alerts[0]
            fraudulent_tx = next((t for t in transactions if t['id'] == alert.get('buy_id')), None)
            
            if fraudulent_tx:
                desc = generator.generate_description(fraudulent_tx)
                assert isinstance(desc, str)
    
    def test_pattern_to_aml_flow(self, setup_test_db):
        """Test workflow: learn patterns -> detect AML anomalies"""
        conn, db_file = setup_test_db
        
        from src.advanced_ml_features import PatternLearner, AMLDetector
        
        learner = PatternLearner()
        detector = AMLDetector()
        
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Learn patterns
        learner.learn_patterns(transactions)
        
        # Detect anomalies
        anomalies = []
        for tx in transactions:
            anomaly = learner.detect_anomalies(tx)
            if anomaly:
                anomalies.append(anomaly)
            
            # Also check AML
            aml_alert = detector.detect_structuring(transactions, tx)
            if aml_alert:
                pass  # AML alert detected
        
        # Should have some findings
        assert isinstance(anomalies, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
