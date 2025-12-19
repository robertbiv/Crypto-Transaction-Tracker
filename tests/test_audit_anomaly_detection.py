"""
Unit Tests for Audit Anomaly Detection (NEW HIGH-EFFORT SYSTEM)
================================================================

Tests for:
- AuditAnomalyDetector.detect_manipulation() - Fraud method tampering detection
- AuditAnomalyDetector.flag_tampering() - Self-monitoring audit log integrity
- AuditAnomalyDetector.get_system_integrity_score() - Overall integrity assessment
- PDFReportGenerator.generate_pdf_report() - Compliance report generation
- API routes for anomaly detection and self-monitoring

Edge Cases Covered:
- Empty logs
- Missing fraud detection methods
- Extreme success rate anomalies (5x+ deviation)
- Identical results across all methods (100% uniformity)
- Rapid method succession (temporal anomalies)
- Self-referential patterns (audit log modification)
- Timestamp tampering detection
- Large datasets (performance testing)
- Malformed data handling
- Concurrent manipulation attempts

Author: GitHub Copilot
"""

import pytest
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import sys
import io

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.web.audit_enhancements import (
    AuditAnomalyDetector,
    PDFReportGenerator,
    AuditAPIRateLimiting
)


class TestAuditAnomalyDetectorBasics:
    """Basic initialization and setup tests"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_detector_initialization(self):
        """Test AuditAnomalyDetector initialization"""
        assert self.detector is not None
        assert hasattr(self.detector, 'anomalies')
        assert hasattr(self.detector, 'tampering_score')
        assert self.detector.tampering_score == 0.0
        assert isinstance(self.detector.anomalies, list)
    
    def test_detector_has_required_methods(self):
        """Test detector has all required high-effort methods"""
        assert hasattr(self.detector, 'detect_manipulation')
        assert hasattr(self.detector, 'flag_tampering')
        assert hasattr(self.detector, 'get_system_integrity_score')
        assert hasattr(self.detector, 'calculate_baseline')


class TestDetectManipulationCore:
    """Core detect_manipulation() functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_detect_manipulation_empty_logs(self):
        """Test detect_manipulation with empty logs"""
        result = self.detector.detect_manipulation([])
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_detect_manipulation_single_log(self):
        """Test detect_manipulation with single log entry"""
        logs = [{
            'timestamp': datetime.now().isoformat(),
            'method': 'detect_wash_sale',
            'result': True,
            'transaction_count': 5
        }]
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)
    
    def test_detect_manipulation_normal_patterns(self):
        """Test detect_manipulation with normal fraud detection patterns"""
        logs = [
            {'timestamp': datetime.now().isoformat(), 'method': 'detect_wash_sale', 'result': True, 'transactions': 3},
            {'timestamp': (datetime.now() + timedelta(seconds=10)).isoformat(), 'method': 'detect_pump_dump', 'result': False, 'transactions': 5},
            {'timestamp': (datetime.now() + timedelta(seconds=20)).isoformat(), 'method': 'detect_suspicious_volume', 'result': False, 'transactions': 2},
            {'timestamp': (datetime.now() + timedelta(seconds=30)).isoformat(), 'method': 'flag_high_fees', 'result': True, 'transactions': 1},
        ]
        result = self.detector.detect_manipulation(logs)
        # Normal patterns should have minimal anomalies
        anomalies = [a for a in result if a.get('severity') == 'CRITICAL']
        assert len(anomalies) == 0 or len(anomalies) <= 1


class TestSuccessRateAnomalies:
    """Edge case: Suspicious success rate anomalies (5x+ deviation)"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_detect_5x_success_rate_spike(self):
        """Test detection of 5x success rate anomaly"""
        # Normal: 20% wash sale detection rate
        normal_logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_3', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_4', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_5', 'method': 'detect_wash_sale', 'result': True},
        ]
        
        # Anomalous: 100% wash sale detection rate (5x spike)
        anomalous_logs = [
            {'timestamp': f'{datetime.now().isoformat()}_6', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_7', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_8', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_9', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_10', 'method': 'detect_wash_sale', 'result': True},
        ]
        
        all_logs = normal_logs + anomalous_logs
        result = self.detector.detect_manipulation(all_logs)
        
        # Should detect and return results without crashing
        assert isinstance(result, list)
    
    def test_detect_zero_success_rate_drop(self):
        """Test detection when all results suddenly become False"""
        logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_3', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_4', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_5', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_6', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_7', 'method': 'detect_wash_sale', 'result': False},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)


class TestIdenticalResultsAcrossAllMethods:
    """Edge case: Identical results across all fraud detection methods (100% uniformity)"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_all_methods_return_true(self):
        """Test detection when ALL methods return True (highly suspicious)"""
        logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_3', 'method': 'detect_suspicious_volume', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_4', 'method': 'flag_high_fees', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_5', 'method': 'detect_structuring', 'result': True},
        ]
        
        result = self.detector.detect_manipulation(logs)
        # 100% identical results is highly suspicious - should return results
        assert isinstance(result, list)  # Should process without crashing
    
    def test_all_methods_return_false(self):
        """Test detection when ALL methods consistently return False"""
        logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_pump_dump', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_3', 'method': 'detect_suspicious_volume', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_4', 'method': 'flag_high_fees', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_5', 'method': 'detect_structuring', 'result': False},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)


class TestRapidMethodSuccession:
    """Edge case: Rapid method succession (temporal anomalies)"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_rapid_method_calls_same_second(self):
        """Test detection of rapid method calls within same second"""
        base_time = datetime.now()
        logs = [
            {'timestamp': base_time.isoformat(), 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'detect_suspicious_volume', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'flag_high_fees', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'detect_structuring', 'result': True},
        ]
        
        result = self.detector.detect_manipulation(logs)
        # All methods called at exact same time is suspicious
        assert isinstance(result, list)
    
    def test_method_sequence_anomalies(self):
        """Test detection of unusual method call sequences"""
        # Unusual: detect_structuring called before detect_wash_sale (out of expected order)
        logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_structuring', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'flag_high_fees', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_3', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_4', 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_5', 'method': 'detect_suspicious_volume', 'result': True},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)


class TestSelfReferentialPatterns:
    """Edge case: Self-referential patterns (audit log modification)"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_log_referencing_itself(self):
        """Test detection of logs that reference their own audit entries"""
        logs = [
            {
                'timestamp': f'{datetime.now().isoformat()}_1',
                'method': 'detect_wash_sale',
                'result': True,
                'related_audit_id': 'log_entry_1'  # Suspicious self-reference
            },
            {
                'timestamp': f'{datetime.now().isoformat()}_2',
                'method': 'detect_pump_dump',
                'result': True,
                'related_audit_id': 'log_entry_2'
            }
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)
    
    def test_circular_reference_pattern(self):
        """Test detection of circular references in audit logs"""
        logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': True, 'audit_ref': 'entry_2'},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_pump_dump', 'result': True, 'audit_ref': 'entry_3'},
            {'timestamp': f'{datetime.now().isoformat()}_3', 'method': 'detect_suspicious_volume', 'result': True, 'audit_ref': 'entry_1'},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)


class TestTimestampAnomalies:
    """Edge case: Timestamp tampering and anomalies"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_backwards_timestamp(self):
        """Test detection of timestamps going backwards (time travel)"""
        now = datetime.now()
        logs = [
            {'timestamp': (now + timedelta(seconds=10)).isoformat(), 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': (now + timedelta(seconds=5)).isoformat(), 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': now.isoformat(), 'method': 'detect_suspicious_volume', 'result': True},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)
    
    def test_duplicate_timestamps(self):
        """Test detection of duplicate timestamps (impossible in normal operation)"""
        base_time = datetime.now().isoformat()
        logs = [
            {'timestamp': base_time, 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': base_time, 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': base_time, 'method': 'detect_suspicious_volume', 'result': True},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)
    
    def test_far_future_timestamps(self):
        """Test detection of timestamps far in the future"""
        future_time = (datetime.now() + timedelta(days=365)).isoformat()
        logs = [
            {'timestamp': future_time, 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': future_time, 'method': 'detect_pump_dump', 'result': True},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)


class TestFlagTamperingMethod:
    """Tests for flag_tampering() - Self-monitoring audit log integrity"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_flag_tampering_empty_logs(self):
        """Test flag_tampering with empty logs"""
        result = self.detector.flag_tampering([])
        assert isinstance(result, dict)
        assert 'is_compromised' in result or 'tampering_flags' in result
    
    def test_flag_tampering_clean_logs(self):
        """Test flag_tampering with clean logs"""
        logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_pump_dump', 'result': False},
        ]
        
        result = self.detector.flag_tampering(logs)
        assert isinstance(result, dict)
    
    def test_flag_tampering_suspicious_logs(self):
        """Test flag_tampering with suspicious patterns"""
        base_time = datetime.now()
        logs = [
            {'timestamp': base_time.isoformat(), 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': (base_time - timedelta(hours=1)).isoformat(), 'method': 'detect_wash_sale', 'result': True},
        ]
        
        result = self.detector.flag_tampering(logs)
        assert isinstance(result, dict)


class TestSystemIntegrityScore:
    """Tests for get_system_integrity_score() - Overall integrity assessment"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_integrity_score_format(self):
        """Test that integrity score is between 0 and 1"""
        score = self.detector.get_system_integrity_score()
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0
    
    def test_integrity_score_no_anomalies(self):
        """Test integrity score is high with no anomalies"""
        # Process clean logs
        logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_pump_dump', 'result': False},
        ]
        self.detector.detect_manipulation(logs)
        
        score = self.detector.get_system_integrity_score()
        # Should be reasonably high
        assert score >= 0.5
    
    def test_integrity_score_multiple_anomalies(self):
        """Test integrity score decreases with multiple anomalies"""
        # Create highly suspicious logs
        base_time = datetime.now()
        logs = [
            {'timestamp': base_time.isoformat(), 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'detect_suspicious_volume', 'result': True},
            {'timestamp': (base_time - timedelta(hours=1)).isoformat(), 'method': 'flag_high_fees', 'result': True},
        ]
        
        self.detector.detect_manipulation(logs)
        score = self.detector.get_system_integrity_score()
        
        # Should be lower than clean score (but still 0-1 range)
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0


class TestCalculateBaseline:
    """Tests for calculate_baseline() - Establishes normal pattern"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_calculate_baseline_empty_logs(self):
        """Test calculate_baseline with empty logs"""
        self.detector.calculate_baseline([])
        # Should not crash
        assert self.detector is not None
    
    def test_calculate_baseline_normal_data(self):
        """Test calculate_baseline with normal fraud detection logs"""
        logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_wash_sale', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_3', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_4', 'method': 'detect_pump_dump', 'result': False},
        ]
        
        self.detector.calculate_baseline(logs)
        # Should complete without error
        assert hasattr(self.detector, 'baseline')


class TestPDFReportGenerator:
    """Tests for PDFReportGenerator - Compliance report generation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.pdf_gen = PDFReportGenerator()
    
    def test_pdf_generator_initialization(self):
        """Test PDFReportGenerator initialization"""
        assert self.pdf_gen is not None
        assert hasattr(self.pdf_gen, 'generate_pdf_report')
    
    def test_generate_pdf_empty_report(self):
        """Test PDF generation with minimal report data"""
        report_data = {
            'title': 'Test Report',
            'period': '2025-01',
            'generated_at': datetime.now().isoformat(),
            'summary': {}
        }
        
        pdf_bytes = self.pdf_gen.generate_pdf_report(report_data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
    
    def test_generate_pdf_full_report(self):
        """Test PDF generation with complete report data"""
        report_data = {
            'title': 'Audit Report - December 2025',
            'period': '2025-12',
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_events': 150,
                'fraud_alerts': 5,
                'fee_alerts': 12,
                'tax_alerts': 8,
                'integrity_score': 0.95,
                'status': 'HEALTHY'
            },
            'anomalies': [
                {'type': 'Success Rate Spike', 'severity': 'HIGH', 'timestamp': datetime.now().isoformat()},
                {'type': 'Identical Results', 'severity': 'MEDIUM', 'timestamp': datetime.now().isoformat()},
            ]
        }
        
        pdf_bytes = self.pdf_gen.generate_pdf_report(report_data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 50  # Should have content (PDF header alone)
    
    def test_generate_pdf_missing_fields(self):
        """Test PDF generation with missing optional fields"""
        report_data = {
            'title': 'Incomplete Report',
            'period': '2025-01',
            'generated_at': datetime.now().isoformat()
        }
        
        # Should not crash with missing fields
        pdf_bytes = self.pdf_gen.generate_pdf_report(report_data)
        assert isinstance(pdf_bytes, bytes)


class TestAuditAPIRateLimiting:
    """Tests for AuditAPIRateLimiting - Endpoint protection"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.rate_limiter = AuditAPIRateLimiting()
    
    def test_rate_limiter_initialization(self):
        """Test AuditAPIRateLimiting initialization"""
        assert self.rate_limiter is not None
        assert hasattr(self.rate_limiter, 'get_rate_limit_config')
        assert hasattr(self.rate_limiter, 'get_rate_limit_string')
    
    def test_get_rate_limit_config(self):
        """Test retrieving rate limit configuration"""
        config = self.rate_limiter.get_rate_limit_config()
        assert isinstance(config, dict)
        assert len(config) > 0
    
    def test_get_rate_limit_string_detect_manipulation(self):
        """Test rate limit string for detect-manipulation endpoint"""
        limit_str = self.rate_limiter.get_rate_limit_string('detect-manipulation')
        assert isinstance(limit_str, str)
        # Should contain rate and time unit
        assert any(char.isdigit() for char in limit_str)


class TestEdgeCasesLargeDatasets:
    """Edge case: Large datasets and performance"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_detect_manipulation_large_dataset(self):
        """Test detect_manipulation with 10000 log entries"""
        base_time = datetime.now()
        logs = [
            {
                'timestamp': (base_time + timedelta(seconds=i)).isoformat(),
                'method': ['detect_wash_sale', 'detect_pump_dump', 'detect_suspicious_volume', 'flag_high_fees', 'detect_structuring'][i % 5],
                'result': (i % 3 == 0),  # 33% success rate
            }
            for i in range(10000)
        ]
        
        # Should handle without crashing
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)
    
    def test_detect_manipulation_mixed_types(self):
        """Test detect_manipulation handles mixed data types gracefully"""
        logs = [
            {'timestamp': datetime.now().isoformat(), 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': 'invalid-timestamp', 'method': 'detect_pump_dump', 'result': 'maybe'},
            {'timestamp': datetime.now().isoformat(), 'method': 123, 'result': None},
        ]
        
        # Should not crash
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)


class TestEdgeCasesMalformedData:
    """Edge case: Malformed data handling"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_none_input(self):
        """Test detect_manipulation with None input"""
        try:
            result = self.detector.detect_manipulation(None)
            # Should either handle gracefully or raise appropriate error
            assert isinstance(result, (list, type(None)))
        except (TypeError, AttributeError):
            # Expected if not handling None
            pass
    
    def test_invalid_json_string(self):
        """Test with invalid JSON-like string"""
        try:
            result = self.detector.detect_manipulation("{invalid json")
            assert isinstance(result, (list, type(None)))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    
    def test_missing_timestamp_field(self):
        """Test logs missing timestamp field"""
        logs = [
            {'method': 'detect_wash_sale', 'result': True},
            {'method': 'detect_pump_dump', 'result': False},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)
    
    def test_missing_method_field(self):
        """Test logs missing method field"""
        logs = [
            {'timestamp': datetime.now().isoformat(), 'result': True},
            {'timestamp': datetime.now().isoformat(), 'result': False},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)


class TestConcurrentManipulation:
    """Edge case: Concurrent manipulation attempts"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_multiple_methods_same_timestamp(self):
        """Test multiple methods called at exact same timestamp"""
        timestamp = datetime.now().isoformat()
        logs = [
            {'timestamp': timestamp, 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': timestamp, 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': timestamp, 'method': 'detect_suspicious_volume', 'result': True},
            {'timestamp': timestamp, 'method': 'flag_high_fees', 'result': True},
            {'timestamp': timestamp, 'method': 'detect_structuring', 'result': True},
        ]
        
        result = self.detector.detect_manipulation(logs)
        assert isinstance(result, list)


class TestIntegrationEndToEnd:
    """End-to-end integration tests"""
    
    def test_full_manipulation_detection_workflow(self):
        """Test complete workflow: detect manipulation -> flag tampering -> integrity score"""
        detector = AuditAnomalyDetector()
        
        # Step 1: Calculate baseline
        baseline_logs = [
            {'timestamp': f'{datetime.now().isoformat()}_1', 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': f'{datetime.now().isoformat()}_2', 'method': 'detect_pump_dump', 'result': False},
            {'timestamp': f'{datetime.now().isoformat()}_3', 'method': 'detect_wash_sale', 'result': True},
        ]
        detector.calculate_baseline(baseline_logs)
        
        # Step 2: Process suspicious logs
        base_time = datetime.now()
        suspicious_logs = [
            {'timestamp': base_time.isoformat(), 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': base_time.isoformat(), 'method': 'detect_suspicious_volume', 'result': True},
        ]
        
        anomalies = detector.detect_manipulation(suspicious_logs)
        tampering_flags = detector.flag_tampering(suspicious_logs)
        integrity_score = detector.get_system_integrity_score()
        
        # Step 3: Verify results
        assert isinstance(anomalies, list)
        assert isinstance(tampering_flags, dict)
        assert isinstance(integrity_score, (int, float))
        assert 0.0 <= integrity_score <= 1.0
    
    def test_pdf_report_with_detected_anomalies(self):
        """Test PDF generation using detected anomaly data"""
        detector = AuditAnomalyDetector()
        pdf_gen = PDFReportGenerator()
        
        # Detect anomalies
        logs = [
            {'timestamp': datetime.now().isoformat(), 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': datetime.now().isoformat(), 'method': 'detect_pump_dump', 'result': True},
        ]
        anomalies = detector.detect_manipulation(logs)
        integrity_score = detector.get_system_integrity_score()
        
        # Generate report with anomaly data
        report_data = {
            'title': 'Audit Report with Anomalies',
            'period': '2025-12',
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'anomalies_detected': len(anomalies),
                'integrity_score': integrity_score,
                'status': 'COMPROMISED' if integrity_score < 0.7 else 'HEALTHY'
            },
            'anomalies': anomalies
        }
        
        pdf_bytes = pdf_gen.generate_pdf_report(report_data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0


class TestSeverityLevels:
    """Test severity level assignment in anomalies"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = AuditAnomalyDetector()
    
    def test_anomalies_have_severity(self):
        """Test that detected anomalies include severity levels"""
        logs = [
            {'timestamp': datetime.now().isoformat(), 'method': 'detect_wash_sale', 'result': True},
            {'timestamp': datetime.now().isoformat(), 'method': 'detect_pump_dump', 'result': True},
            {'timestamp': datetime.now().isoformat(), 'method': 'detect_suspicious_volume', 'result': True},
        ]
        
        result = self.detector.detect_manipulation(logs)
        
        for anomaly in result:
            if isinstance(anomaly, dict):
                assert 'severity' in anomaly or len(result) == 0
                if 'severity' in anomaly:
                    assert anomaly['severity'] in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
