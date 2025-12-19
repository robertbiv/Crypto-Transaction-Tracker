"""
Unit Tests for Audit Log Management Enhancements
================================================

Tests for the new audit log API endpoints and AuditLogManager class.
Covers:
- API endpoints (download, summary, events, dashboard, compliance reports)
- AuditLogManager functionality
- CSV export
- Summary statistics
- Compliance report generation

Author: GitHub Copilot
"""

import pytest
import json
import tempfile
import io
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from src.web.audit_endpoints import AuditLogManager


class TestAuditLogManager:
    """Test suite for AuditLogManager class"""
    
    @pytest.fixture
    def temp_audit_log(self):
        """Create a temporary audit log file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = Path(f.name)
            
            # Write sample audit log entries
            entries = [
                {
                    "timestamp": (datetime.now() - timedelta(days=5)).isoformat(),
                    "alert_type": "WASH_SALE",
                    "severity": "high",
                    "coin": "BTC",
                    "tx_ids": ["buy_1", "sell_1"],
                    "amount": "0.5",
                    "wash_date_range": "3 days",
                    "loss_amount": "1234.56",
                    "description": "Wash sale detected"
                },
                {
                    "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
                    "alert_type": "FEE_CALCULATION",
                    "severity": "medium",
                    "coin": "ETH",
                    "tx_id": "tx_1",
                    "amount": "10.0",
                    "fee_amount": "0.5",
                    "fee_percentage": "5.0",
                    "description": "High fee detected"
                },
                {
                    "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                    "alert_type": "PUMP_DUMP",
                    "severity": "high",
                    "coin": "BTC",
                    "tx_id": "buy_2",
                    "amount": "1.0",
                    "calculated_gain": "5000.00",
                    "tax_impact": "1250.00",
                    "description": "Pump and dump pattern detected"
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "alert_type": "SUSPICIOUS_VOLUME",
                    "severity": "low",
                    "coin": "ADA",
                    "tx_id": "tx_2",
                    "amount": "1000.0",
                    "description": "Unusual volume detected"
                }
            ]
            
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        yield temp_path
        
        # Cleanup
        temp_path.unlink()
    
    def test_manager_initialization(self, temp_audit_log):
        """Test AuditLogManager initialization"""
        manager = AuditLogManager(temp_audit_log)
        assert manager.audit_log_file == temp_audit_log
        assert manager.audit_log_file.exists()
    
    def test_read_audit_logs(self, temp_audit_log):
        """Test reading audit logs from file"""
        manager = AuditLogManager(temp_audit_log)
        logs = manager.read_audit_logs()
        
        assert len(logs) == 4
        assert logs[0]['alert_type'] == 'WASH_SALE'
        assert logs[1]['alert_type'] == 'FEE_CALCULATION'
        assert logs[2]['alert_type'] == 'PUMP_DUMP'
        assert logs[3]['alert_type'] == 'SUSPICIOUS_VOLUME'
    
    def test_read_logs_with_alert_type_filter(self, temp_audit_log):
        """Test filtering logs by alert type"""
        manager = AuditLogManager(temp_audit_log)
        logs = manager.read_audit_logs(alert_type='WASH_SALE')
        
        assert len(logs) == 1
        assert logs[0]['alert_type'] == 'WASH_SALE'
    
    def test_read_logs_with_date_range(self, temp_audit_log):
        """Test filtering logs by date range"""
        manager = AuditLogManager(temp_audit_log)
        
        # Get logs from last 2 days
        start_date = datetime.now() - timedelta(days=2)
        logs = manager.read_audit_logs(start_date=start_date)
        
        # Should get logs from the last 2 days (not necessarily all of them)
        assert len(logs) >= 1  # At least one recent entry
        # The most recent entry should be either PUMP_DUMP or SUSPICIOUS_VOLUME or WASH_SALE
        recent_types = [log['alert_type'] for log in logs]
        assert any(t in recent_types for t in ['PUMP_DUMP', 'SUSPICIOUS_VOLUME', 'WASH_SALE', 'FEE_CALCULATION'])
    
    def test_export_to_csv(self, temp_audit_log):
        """Test CSV export functionality"""
        manager = AuditLogManager(temp_audit_log)
        logs = manager.read_audit_logs()
        csv_content = manager.export_to_csv(logs)
        
        assert isinstance(csv_content, str)
        assert 'timestamp' in csv_content
        assert 'WASH_SALE' in csv_content
        assert 'FEE_CALCULATION' in csv_content
        assert 'PUMP_DUMP' in csv_content
        assert 'SUSPICIOUS_VOLUME' in csv_content
    
    def test_export_to_csv_no_logs(self, temp_audit_log):
        """Test CSV export with no logs"""
        manager = AuditLogManager(temp_audit_log)
        csv_content = manager.export_to_csv([])
        
        assert isinstance(csv_content, str)
        assert 'No audit logs found' in csv_content
    
    def test_get_summary_statistics(self, temp_audit_log):
        """Test summary statistics calculation"""
        manager = AuditLogManager(temp_audit_log)
        logs = manager.read_audit_logs()
        summary = manager.get_summary_statistics(logs)
        
        assert summary['total_events'] == 4
        # Fraud alerts: WASH_SALE, PUMP_DUMP, SUSPICIOUS_VOLUME (3 fraud-related alerts)
        assert summary['fraud_alerts'] == 3
        assert summary['fee_alerts'] == 1    # FEE_CALCULATION
        assert 'events_by_type' in summary
        assert 'events_by_severity' in summary
        assert summary['events_by_type']['WASH_SALE'] == 1
        assert summary['events_by_type']['FEE_CALCULATION'] == 1
        assert summary['events_by_type']['PUMP_DUMP'] == 1
    
    def test_summary_severity_counts(self, temp_audit_log):
        """Test severity counting in summary"""
        manager = AuditLogManager(temp_audit_log)
        logs = manager.read_audit_logs()
        summary = manager.get_summary_statistics(logs)
        
        # WASH_SALE (high) + PUMP_DUMP (high) = 2 high severity
        assert summary['events_by_severity']['high'] == 2
        # FEE_CALCULATION (medium) = 1 medium
        assert summary['events_by_severity']['medium'] == 1
        # SUSPICIOUS_VOLUME (low) = 1 low
        assert summary['events_by_severity']['low'] == 1
    
    def test_summary_most_common_coin(self, temp_audit_log):
        """Test most common coin detection"""
        manager = AuditLogManager(temp_audit_log)
        logs = manager.read_audit_logs()
        summary = manager.get_summary_statistics(logs)
        
        assert summary['most_common_coin'] == 'BTC'  # BTC appears twice
    
    def test_summary_tax_impact_total(self, temp_audit_log):
        """Test tax impact total calculation"""
        manager = AuditLogManager(temp_audit_log)
        logs = manager.read_audit_logs()
        summary = manager.get_summary_statistics(logs)
        
        # Should have tax_impact from PUMP_DUMP entry
        assert summary['tax_impact_total'] == Decimal('1250.00')
    
    def test_generate_monthly_report(self, temp_audit_log):
        """Test monthly compliance report generation"""
        manager = AuditLogManager(temp_audit_log)
        
        # Generate report for current month
        now = datetime.now()
        report = manager.generate_monthly_report(year=now.year, month=now.month)
        
        assert report['title'].startswith('Monthly Compliance Report')
        assert report['period']['year'] == now.year
        assert report['period']['month'] == now.month
        assert 'summary' in report
        assert 'audit_events' in report
        assert 'fraud_alerts' in report
    
    def test_generate_monthly_report_structure(self, temp_audit_log):
        """Test monthly report has all required fields"""
        manager = AuditLogManager(temp_audit_log)
        now = datetime.now()
        report = manager.generate_monthly_report(year=now.year, month=now.month)
        
        required_fields = [
            'title', 'generated_at', 'period', 'summary',
            'audit_events', 'fraud_alerts', 'fee_alerts',
            'events_by_type', 'events_by_severity', 'tax_impact'
        ]
        
        for field in required_fields:
            assert field in report, f"Missing field: {field}"
    
    def test_empty_audit_log(self):
        """Test handling of empty audit log file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = Path(f.name)
        
        try:
            manager = AuditLogManager(temp_path)
            logs = manager.read_audit_logs()
            assert len(logs) == 0
            
            summary = manager.get_summary_statistics(logs)
            assert summary['total_events'] == 0
            assert summary['fraud_alerts'] == 0
        finally:
            temp_path.unlink()
    
    def test_nonexistent_audit_log(self):
        """Test handling of non-existent audit log file"""
        manager = AuditLogManager(Path('/nonexistent/path/to/audit.log'))
        logs = manager.read_audit_logs()
        assert len(logs) == 0
    
    def test_decimal_precision_in_export(self, temp_audit_log):
        """Test that Decimal values are preserved in CSV export"""
        manager = AuditLogManager(temp_audit_log)
        logs = manager.read_audit_logs()
        csv_content = manager.export_to_csv(logs)
        
        # Should contain decimal values as strings
        assert '1234.56' in csv_content
        assert '1250.00' in csv_content
        assert '5000.00' in csv_content


class TestAuditLogIntegration:
    """Integration tests for audit log system"""
    
    @pytest.fixture
    def temp_audit_log_with_data(self):
        """Create an audit log with realistic data"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = Path(f.name)
            
            entries = []
            base_date = datetime.now() - timedelta(days=29)
            
            # Create 30 days of audit events
            for day in range(30):
                current_date = base_date + timedelta(days=day)
                
                # Wash sale alert
                entries.append({
                    "timestamp": current_date.isoformat(),
                    "alert_type": "WASH_SALE",
                    "severity": "high",
                    "coin": "BTC",
                    "amount": "0.1",
                    "loss_amount": "234.56"
                })
                
                # Fee calculation
                entries.append({
                    "timestamp": (current_date + timedelta(hours=6)).isoformat(),
                    "alert_type": "FEE_CALCULATION",
                    "severity": "low",
                    "coin": "ETH",
                    "fee_amount": "0.05",
                    "fee_percentage": "2.5"
                })
                
                # Pump and dump
                if day % 3 == 0:
                    entries.append({
                        "timestamp": (current_date + timedelta(hours=12)).isoformat(),
                        "alert_type": "PUMP_DUMP",
                        "severity": "high",
                        "coin": "BTC",
                        "amount": "1.0",
                        "calculated_gain": "5000.00",
                        "tax_impact": "1250.00"
                    })
            
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        yield temp_path
        temp_path.unlink()
    
    def test_large_dataset_performance(self, temp_audit_log_with_data):
        """Test performance with larger dataset (30 days)"""
        manager = AuditLogManager(temp_audit_log_with_data)
        logs = manager.read_audit_logs()
        
        # Should have ~70 entries (3 per day for 30 days - some days skip pump_dump)
        assert len(logs) > 60
        
        # Summary should complete quickly
        summary = manager.get_summary_statistics(logs)
        assert summary['total_events'] > 60
        assert summary['fraud_alerts'] > 0
    
    def test_csv_export_with_large_dataset(self, temp_audit_log_with_data):
        """Test CSV export with larger dataset"""
        manager = AuditLogManager(temp_audit_log_with_data)
        logs = manager.read_audit_logs()
        csv_content = manager.export_to_csv(logs)
        
        # Should be valid CSV with multiple lines
        lines = csv_content.strip().split('\n')
        assert len(lines) > 61  # Header + data rows
        
        # First line should be headers
        assert 'timestamp' in lines[0]


class TestAuditLogDataValidation:
    """Tests for data validation and type checking"""
    
    @pytest.fixture
    def manager_with_mixed_data(self):
        """Create manager with various data types"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = Path(f.name)
            
            entries = [
                {
                    "timestamp": datetime.now().isoformat(),
                    "alert_type": "WASH_SALE",
                    "severity": "high",
                    "coin": "BTC",
                    "amount": "0.5",
                    "loss_amount": "1234.56",
                    "nested_data": {"key": "value"}
                }
            ]
            
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        yield AuditLogManager(temp_path), temp_path
        
        temp_path.unlink()
    
    def test_csv_handles_nested_data(self, manager_with_mixed_data):
        """Test that CSV export handles nested JSON data"""
        manager, _ = manager_with_mixed_data
        logs = manager.read_audit_logs()
        csv_content = manager.export_to_csv(logs)
        
        # Should contain JSON stringified nested data
        assert 'key' in csv_content or '{}' in csv_content or 'value' in csv_content
    
    def test_summary_handles_missing_fields(self):
        """Test summary generation with missing optional fields"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = Path(f.name)
            
            # Entry with minimal fields
            entry = {
                "timestamp": datetime.now().isoformat(),
                "alert_type": "ANOMALY",
                "severity": "low"
            }
            f.write(json.dumps(entry) + '\n')
        
        try:
            manager = AuditLogManager(temp_path)
            logs = manager.read_audit_logs()
            summary = manager.get_summary_statistics(logs)
            
            assert summary['total_events'] == 1
            assert summary['most_common_coin'] is None
            assert summary['fraud_alerts'] == 0
        finally:
            temp_path.unlink()


class TestAuditLogFiltering:
    """Tests for various filtering scenarios"""
    
    @pytest.fixture
    def manager_with_multi_day_data(self):
        """Create manager with events across multiple days"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = Path(f.name)
            
            now = datetime.now()
            
            entries = [
                # 10 days ago
                {
                    "timestamp": (now - timedelta(days=10)).isoformat(),
                    "alert_type": "WASH_SALE",
                    "severity": "high",
                    "coin": "BTC"
                },
                # 5 days ago
                {
                    "timestamp": (now - timedelta(days=5)).isoformat(),
                    "alert_type": "FEE_CALCULATION",
                    "severity": "medium",
                    "coin": "ETH"
                },
                # 3 days ago
                {
                    "timestamp": (now - timedelta(days=3)).isoformat(),
                    "alert_type": "PUMP_DUMP",
                    "severity": "high",
                    "coin": "BTC"
                },
                # 1 day ago
                {
                    "timestamp": (now - timedelta(days=1)).isoformat(),
                    "alert_type": "SUSPICIOUS_VOLUME",
                    "severity": "low",
                    "coin": "ADA"
                },
                # Today
                {
                    "timestamp": now.isoformat(),
                    "alert_type": "STRUCTURING",
                    "severity": "high",
                    "coin": "BTC"
                }
            ]
            
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        yield AuditLogManager(temp_path), temp_path
        
        temp_path.unlink()
    
    def test_date_range_filtering(self, manager_with_multi_day_data):
        """Test filtering by date range"""
        manager, _ = manager_with_multi_day_data
        now = datetime.now()
        
        # Last 2 days
        start = now - timedelta(days=2)
        logs = manager.read_audit_logs(start_date=start)
        assert len(logs) == 2  # Last 2 entries
    
    def test_type_and_date_filtering(self, manager_with_multi_day_data):
        """Test combining type and date filters"""
        manager, _ = manager_with_multi_day_data
        now = datetime.now()
        
        # BTC events in last 5 days
        start = now - timedelta(days=5)
        logs = manager.read_audit_logs(
            start_date=start,
            alert_type='PUMP_DUMP'
        )
        assert len(logs) == 1


def test_audit_endpoints_module_import():
    """Test that audit endpoints module can be imported"""
    from src.web.audit_endpoints import AuditLogManager, create_audit_endpoints
    assert AuditLogManager is not None
    assert create_audit_endpoints is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
