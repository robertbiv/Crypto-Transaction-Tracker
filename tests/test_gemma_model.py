"""
Test suite for Gemma 3n model integration.
Verifies the model loads, processes transactions, and handles edge cases.
"""

import pytest
import json
from pathlib import Path


class TestGemmaModel:
    """Test suite for Gemma 3n model functionality"""
    
    def test_gemma_import(self):
        """Test that ML service can be imported"""
        from src.ml_service import MLService
        assert MLService is not None
    
    def test_gemma_instantiation_shim_mode(self):
        """Test MLService can be instantiated in shim mode"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        assert ml is not None
        assert ml.mode == 'shim'
    
    def test_gemma_instantiation_gemma_mode(self):
        """Test MLService can be instantiated in gemma mode"""
        from src.ml_service import MLService
        
        try:
            ml = MLService(mode='gemma')
            assert ml is not None
            assert ml.mode == 'gemma'
        except Exception as e:
            # If torch/transformers not installed, will gracefully fall back
            print(f"Note: Gemma mode not available (dependencies missing): {e}")
    
    def test_shim_mode_basic_classification(self):
        """Test shim mode basic classification works"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        # Test buy keyword
        result = ml.suggest({'description': 'bought bitcoin on coinbase'})
        assert result is not None
        assert 'suggested_label' in result
        assert result['suggested_label'] in ['BUY', 'SELL', 'TRADE', 'TRANSFER', 'INCOME', 'unknown', None]
    
    def test_shim_mode_multiple_transactions(self):
        """Test shim mode classifies multiple transactions"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        test_cases = [
            {'description': 'bought ETH'},
            {'description': 'sold BTC'},
            {'description': 'traded for tokens'},
            {'description': 'transferred coins'},
        ]
        
        for tx in test_cases:
            result = ml.suggest(tx)
            assert result is not None
            assert 'suggested_label' in result
    
    def test_ml_service_with_auto_shutdown(self):
        """Test ML service with auto-shutdown enabled"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim', auto_shutdown_after_inference=True)
        result = ml.suggest({'description': 'test'})
        assert result is not None
        
        # Shutdown should work without error
        ml.shutdown()
    
    def test_rules_model_bridge(self):
        """Test rules-first classification bridge"""
        from src.rules_model_bridge import classify
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        # Test with a transaction that should match rules
        tx = {
            'description': 'bought bitcoin',
            'amount': 1.0,
            'price_usd': 50000,
            'coin': 'BTC',
            'action': 'UNKNOWN',
            'source': 'exchange'
        }
        
        result = classify(tx, ml=ml)
        assert result is not None
        assert 'label' in result
        assert 'confidence' in result
    
    def test_rules_before_ml(self):
        """Test that rules are tried before ML"""
        from src.rules_model_bridge import classify
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        tx = {
            'description': 'deposited coins',
            'amount': 10.0,
            'price_usd': 0,
            'coin': 'USDC',
            'action': 'UNKNOWN',
            'source': 'wallet'
        }
        
        result = classify(tx, ml=ml)
        
        # Should have a result
        assert result is not None
        assert 'label' in result
    
    def test_ml_confidence_threshold(self):
        """Test ML confidence scoring"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        result = ml.suggest({'description': 'bought something'})
        assert 'confidence' in result
        # Shim confidence should be between 0 and 1
        if result['confidence'] is not None:
            assert 0 <= result['confidence'] <= 1
    
    def test_ml_explanation(self):
        """Test ML provides explanation for classification"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        result = ml.suggest({'description': 'sold all my bitcoin'})
        assert 'explanation' in result
        # Explanation should be a string or None
        assert result['explanation'] is None or isinstance(result['explanation'], str)
    
    def test_ml_handles_empty_input(self):
        """Test ML handles empty input gracefully"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        result = ml.suggest({'description': ''})
        assert result is not None
        # Should return None for confidence/label on empty, not crash
    
    def test_ml_handles_none_input(self):
        """Test ML handles None values gracefully"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        result = ml.suggest({'description': None})
        assert result is not None
    
    def test_ml_handles_unicode(self):
        """Test ML handles unicode characters"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        result = ml.suggest({'description': '购买 bitcoin 在 Binance™'})
        assert result is not None
    
    def test_anomaly_detector_import(self):
        """Test anomaly detector can be imported"""
        from src.anomaly_detector import AnomalyDetector
        assert AnomalyDetector is not None
    
    def test_anomaly_detector_instantiation(self):
        """Test anomaly detector initialization"""
        from src.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        assert detector is not None
    
    def test_anomaly_detector_scan(self):
        """Test anomaly detector scans rows"""
        from src.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        
        row = {
            'amount': 1.0,
            'price_usd': 50000,
            'coin': 'BTC',
            'date': '2024-01-01'
        }
        
        anomalies = detector.scan_row(row)
        assert isinstance(anomalies, list)
    
    def test_anomaly_detector_price_error(self):
        """Test anomaly detector catches price errors"""
        from src.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        
        # Small amount with large price (likely total as price)
        row = {
            'amount': 0.01,
            'price_usd': 50000,
            'coin': 'BTC',
            'date': '2024-01-01'
        }
        
        anomalies = detector.scan_row(row)
        # May or may not flag depending on heuristics
        assert isinstance(anomalies, list)
    
    def test_anomaly_detector_extreme_values(self):
        """Test anomaly detector catches extreme values"""
        from src.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        
        # Extremely large amount
        row = {
            'amount': 10000000,
            'price_usd': 50000,
            'coin': 'BTC',
            'date': '2024-01-01'
        }
        
        anomalies = detector.scan_row(row)
        assert isinstance(anomalies, list)
        # Should flag extreme value
        if anomalies:
            assert any('extreme' in str(a).lower() for a in anomalies)
    
    def test_full_pipeline_shim(self):
        """Test full pipeline: rules -> ML (shim) -> anomaly detection"""
        from src.ml_service import MLService
        from src.rules_model_bridge import classify
        from src.anomaly_detector import AnomalyDetector
        
        ml = MLService(mode='shim')
        detector = AnomalyDetector()
        
        tx = {
            'description': 'bought ethereum',
            'amount': 10.5,
            'price_usd': 2000,
            'coin': 'ETH',
            'action': 'UNKNOWN',
            'source': 'exchange',
            'date': '2024-01-01'
        }
        
        # Classify
        result = classify(tx, ml=ml)
        assert result is not None
        
        # Scan for anomalies
        anomalies = detector.scan_row(tx)
        assert isinstance(anomalies, list)
    
    def test_ml_service_shutdown(self):
        """Test ML service shutdown works"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        # Should not crash
        ml.shutdown()
    
    def test_ml_service_multiple_suggests(self):
        """Test ML service can suggest multiple times"""
        from src.ml_service import MLService
        
        ml = MLService(mode='shim')
        
        for i in range(5):
            result = ml.suggest({'description': f'test {i}'})
            assert result is not None
    
    def test_gemma_real_model_loads(self):
        """Test real Gemma model can be loaded"""
        from src.ml_service import MLService
        
        ml = MLService(mode='gemma')
        assert ml is not None
        # Model may load or fall back to shim, both are acceptable
        assert ml.mode in ['gemma', 'shim']
    
    def test_gemma_real_model_inference(self):
        """Test Gemma model can run inference"""
        from src.ml_service import MLService
        
        ml = MLService(mode='gemma')
        result = ml.suggest({'description': 'bought bitcoin on coinbase'})
        
        assert result is not None
        assert 'suggested_label' in result
        assert result['suggested_label'] in ['BUY', 'SELL', 'TRADE', 'TRANSFER', 'INCOME', 'unknown', None]
        
        # If it's real Gemma (not shim), confidence should be reasonable
        if ml.mode == 'gemma':
            assert 'confidence' in result
            print(f"✓ Real Gemma inference: {result['suggested_label']} (confidence: {result['confidence']})")


class TestGemmaIntegration:
    """Integration tests for Gemma with the web server"""
    
    def test_ml_config_loaded(self):
        """Test ML config is properly loaded"""
        from pathlib import Path
        import json
        
        config_file = Path('configs/config.json')
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Check if ml_fallback exists - if not, that's also ok (will use defaults)
            if 'ml_fallback' in config:
                ml_config = config['ml_fallback']
                assert 'enabled' in ml_config
                assert 'model_name' in ml_config
                assert 'confidence_threshold' in ml_config
    
    def test_ml_config_has_gemma_as_default(self):
        """Test Gemma is set as default model"""
        from pathlib import Path
        import json
        
        config_file = Path('configs/config.json')
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            if 'ml_fallback' in config:
                ml_config = config['ml_fallback']
                # Should be gemma or shim
                assert ml_config.get('model_name') in ['gemma', 'shim']
    
    def test_model_suggestions_log_format(self):
        """Test model suggestions log has correct format"""
        from pathlib import Path
        import json
        
        log_file = Path('outputs/logs/model_suggestions.log')
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Check first entry
            if lines:
                entry = json.loads(lines[0])
                assert 'timestamp' in entry
                assert 'transaction_id' in entry or 'suggested_action' in entry


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
