"""
Audit Log Enhancement Modules - REFACTORED
===========================================

Focuses on:
- Anomaly detection for fraud detection method manipulation
- Self-monitoring of audit system integrity
- API rate limiting
- Database indexing

Author: GitHub Copilot
"""

import json
import sqlite3
import hmac
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import statistics

# ==========================================
# 1. AUDIT LOG ANOMALY DETECTION - FRAUD METHOD MANIPULATION DETECTION
# ==========================================

class AuditAnomalyDetector:
    """
    ENHANCED: Detect anomalies in audit logs, specifically:
    - Unusual patterns in fraud detection method calls
    - Detection if someone is manipulating fraud detection results
    - Self-monitoring for audit system integrity
    - Behavioral deviations that suggest tampering
    - ML-based pattern analysis with high-effort capability
    """
    
    def __init__(self):
        self.baseline = {}
        self.baseline_history = []  # Track baseline changes over time
        self.detection_methods = [
            'detect_wash_sale',
            'detect_pump_dump',
            'detect_suspicious_volume',
            'flag_high_fees',
            'detect_structuring'
        ]
        self.anomalies = []
        self.tampering_score = 0.0
        self.last_baseline_update = None
    
    def calculate_baseline(self, audit_logs: List[Dict]) -> Dict:
        """Calculate baseline patterns from audit logs for detection method calls"""
        baseline = {
            'method_call_frequency': defaultdict(int),
            'method_result_distribution': defaultdict(lambda: defaultdict(int)),
            'average_time_between_calls': {},
            'detection_success_rate': {},
            'time_patterns': defaultdict(list),
            'total_logs': len(audit_logs)
        }
        
        try:
            for log in audit_logs:
                method = log.get('method_name', 'unknown')
                result = log.get('result', 'unknown')
                
                # Track method calls
                baseline['method_call_frequency'][method] += 1
                baseline['method_result_distribution'][method][result] += 1
                
                # Track timestamp patterns
                if 'timestamp' in log:
                    try:
                        ts = datetime.fromisoformat(log['timestamp'])
                        baseline['time_patterns'][method].append(ts)
                    except:
                        pass
            
            # Calculate success rates for detection methods
            for method in self.detection_methods:
                results = baseline['method_result_distribution'].get(method, {})
                total = sum(results.values()) or 1
                success = results.get('fraud_detected', 0)
                baseline['detection_success_rate'][method] = success / total
                
                # Calculate time between calls
                times = baseline['time_patterns'].get(method, [])
                if len(times) > 1:
                    times.sort()
                    diffs = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
                    if diffs:
                        baseline['average_time_between_calls'][method] = statistics.mean(diffs)
            
            self.baseline = baseline
            self.last_baseline_update = datetime.now()
            
            # Store in history for drift detection
            self.baseline_history.append({
                'timestamp': self.last_baseline_update.isoformat(),
                'baseline': dict(baseline)
            })
            
            return baseline
        except Exception as e:
            print(f"Error calculating baseline: {e}")
            return baseline
    
    def auto_learn_baseline_from_history(self, days_back: int = 30, 
                                        min_logs: int = 100) -> Dict:
        """
        AUTO-LEARN: Learn baseline from historical successful patterns
        
        Analyzes past N days of audit logs and creates adaptive baseline
        
        Args:
            days_back: Number of days of history to analyze (default: 30)
            min_logs: Minimum logs required to learn baseline (default: 100)
        
        Returns:
            Dict with learning results and new baseline
        """
        try:
            # Simulate reading historical logs from audit.log
            # In production, this would read from database or file
            historical_logs = self._get_historical_logs(days_back)
            
            if len(historical_logs) < min_logs:
                return {
                    'success': False,
                    'reason': f'Insufficient logs ({len(historical_logs)} < {min_logs})',
                    'logs_found': len(historical_logs)
                }
            
            # Calculate baseline from historical data
            new_baseline = self.calculate_baseline(historical_logs)
            
            # Calculate drift from previous baseline
            drift = self._calculate_baseline_drift(new_baseline)
            
            return {
                'success': True,
                'logs_analyzed': len(historical_logs),
                'baseline_updated': True,
                'methods_monitored': len(self.detection_methods),
                'drift_score': drift,
                'update_timestamp': datetime.now().isoformat(),
                'baseline': {
                    'success_rates': new_baseline['detection_success_rate'],
                    'method_frequencies': dict(new_baseline['method_call_frequency']),
                    'avg_times_between_calls': dict(new_baseline['average_time_between_calls'])
                }
            }
        except Exception as e:
            print(f"Error in auto-learn baseline: {e}")
            return {
                'success': False,
                'error': str(e),
                'logs_analyzed': 0
            }
    
    def _get_historical_logs(self, days_back: int) -> List[Dict]:
        """Retrieve historical audit logs from past N days"""
        # In production, integrate with database query
        # For now, return empty list as placeholder
        # TODO: Integrate with actual audit log storage
        return []
    
    def _calculate_baseline_drift(self, new_baseline: Dict) -> float:
        """
        Calculate drift (change) between current and new baseline
        
        Returns: drift score 0-1 (0 = no change, 1 = complete change)
        """
        if not self.baseline or not self.baseline.get('detection_success_rate'):
            return 0.0
        
        try:
            old_rates = self.baseline.get('detection_success_rate', {})
            new_rates = new_baseline.get('detection_success_rate', {})
            
            if not old_rates:
                return 0.0
            
            # Calculate average difference in success rates
            diffs = []
            for method in self.detection_methods:
                old_rate = old_rates.get(method, 0.5)
                new_rate = new_rates.get(method, 0.5)
                diff = abs(old_rate - new_rate)
                diffs.append(diff)
            
            drift = statistics.mean(diffs) if diffs else 0.0
            return min(1.0, drift)
        except Exception as e:
            print(f"Error calculating drift: {e}")
            return 0.0
    
    def get_baseline_statistics(self) -> Dict:
        """Get current baseline statistics and health"""
        if not self.baseline:
            return {'has_baseline': False}
        
        return {
            'has_baseline': True,
            'last_updated': self.last_baseline_update.isoformat() if self.last_baseline_update else None,
            'total_logs_in_baseline': self.baseline.get('total_logs', 0),
            'methods_tracked': len(self.detection_methods),
            'success_rates': self.baseline.get('detection_success_rate', {}),
            'history_points': len(self.baseline_history),
            'history_span': f'{self.baseline_history[0]["timestamp"] if self.baseline_history else "N/A"} to {self.baseline_history[-1]["timestamp"] if self.baseline_history else "N/A"}'
        }
    
    def detect_manipulation(self, recent_logs: List[Dict]) -> List[Dict]:
        """
        HIGH-EFFORT ANALYSIS: Detect if fraud detection methods are being manipulated
        
        Checks for:
        1. Suspicious patterns in fraud detection results
        2. Methods being called in unusual sequences
        3. Success rate deviations (indicating false positives/negatives)
        4. Self-referential manipulation attempts
        5. Timestamp anomalies suggesting log tampering
        """
        anomalies = []
        
        if not self.baseline or not recent_logs:
            return anomalies
        
        try:
            # 1. Detect suspicious result distributions (manipulation indicator)
            recent_results = defaultdict(lambda: defaultdict(int))
            for log in recent_logs:
                method = log.get('method_name')
                result = log.get('result')
                recent_results[method][result] += 1
            
            for method in self.detection_methods:
                baseline_success = self.baseline['detection_success_rate'].get(method, 0)
                recent_distribution = recent_results.get(method, {})
                recent_total = sum(recent_distribution.values()) or 1
                recent_success = recent_distribution.get('fraud_detected', 0) / recent_total
                
                # Detect if success rate is suspiciously different
                if baseline_success > 0:
                    ratio = recent_success / baseline_success
                    if ratio > 5 or ratio < 0.1:  # 5x increase or 90% decrease
                        anomalies.append({
                            'type': 'fraud_detection_manipulation',
                            'method': method,
                            'severity': 'CRITICAL',
                            'description': f'{method} success rate anomaly: {recent_success*100:.1f}% vs {baseline_success*100:.1f}% baseline',
                            'baseline_rate': baseline_success,
                            'recent_rate': recent_success,
                            'score': 0.95
                        })
                        self.tampering_score = min(1.0, self.tampering_score + 0.3)
            
            # 2. Detect method call sequence manipulation
            methods_called = [log.get('method_name') for log in recent_logs if log.get('method_name')]
            
            # If all detection methods called with identical results, likely manipulation
            if len(set(methods_called)) == len(self.detection_methods):
                results = [log.get('result') for log in recent_logs if log.get('method_name') in self.detection_methods]
                if len(set(results)) == 1 and len(results) == len(self.detection_methods):
                    anomalies.append({
                        'type': 'all_methods_identical_result',
                        'severity': 'CRITICAL',
                        'description': f'All fraud detection methods returned SAME result - indicates manipulation',
                        'score': 0.90
                    })
                    self.tampering_score = min(1.0, self.tampering_score + 0.4)
            
            # 3. Detect rapid method succession (automated tampering attempt)
            for i in range(1, len(recent_logs)):
                try:
                    t1 = datetime.fromisoformat(recent_logs[i-1].get('timestamp', datetime.now().isoformat()))
                    t2 = datetime.fromisoformat(recent_logs[i].get('timestamp', datetime.now().isoformat()))
                    time_diff = (t2 - t1).total_seconds()
                    
                    method = recent_logs[i].get('method_name')
                    expected_time = self.baseline['average_time_between_calls'].get(method, 60)
                    
                    # If much faster than normal, potential automated attack
                    if time_diff < 1 and expected_time > 10:
                        anomalies.append({
                            'type': 'rapid_method_succession',
                            'method': method,
                            'severity': 'HIGH',
                            'description': f'Method called {expected_time/time_diff:.0f}x faster than normal - possible automated manipulation',
                            'time_diff': time_diff,
                            'expected': expected_time,
                            'score': 0.85
                        })
                        self.tampering_score = min(1.0, self.tampering_score + 0.25)
                except Exception as e:
                    pass
            
            # 4. Detect self-referential patterns (audit log modifying fraud detection results)
            for log in recent_logs:
                description = log.get('description', '').lower()
                if 'audit' in description and any(method in description for method in self.detection_methods):
                    anomalies.append({
                        'type': 'self_referential_anomaly',
                        'severity': 'CRITICAL',
                        'description': 'Audit log contains self-referential manipulation attempt',
                        'log_entry': log.get('description', ''),
                        'score': 0.92
                    })
                    self.tampering_score = min(1.0, self.tampering_score + 0.35)
            
            # Sort by score
            anomalies.sort(key=lambda x: x.get('score', 0), reverse=True)
            self.anomalies = anomalies
            
            return anomalies
        except Exception as e:
            print(f"Error detecting manipulation: {e}")
            return anomalies
    
    def get_system_integrity_score(self) -> float:
        """Get overall system integrity score (0=compromised, 1=perfect)"""
        return max(0.0, 1.0 - self.tampering_score)
    
    def flag_tampering(self, audit_logs: List[Dict]) -> Dict:
        """Self-monitoring: Check if audit logs themselves have been tampered with"""
        tampering_indicators = {
            'out_of_order_timestamps': 0,
            'duplicate_entries': 0,
            'missing_expected_fields': 0,
            'suspicious_result_patterns': 0,
            'integrity_score': 1.0,
            'is_compromised': False
        }
        
        try:
            prev_timestamp = None
            seen_hashes = set()
            
            for i, log in enumerate(audit_logs):
                # Check timestamps
                try:
                    curr_ts = datetime.fromisoformat(log.get('timestamp', ''))
                    if prev_timestamp and curr_ts < prev_timestamp:
                        tampering_indicators['out_of_order_timestamps'] += 1
                        tampering_indicators['integrity_score'] -= 0.15
                    prev_timestamp = curr_ts
                except:
                    pass
                
                # Check for duplicates
                log_hash = hashlib.sha256(json.dumps(log, sort_keys=True).encode()).hexdigest()
                if log_hash in seen_hashes:
                    tampering_indicators['duplicate_entries'] += 1
                    tampering_indicators['integrity_score'] -= 0.2
                seen_hashes.add(log_hash)
                
                # Check required fields
                required = ['timestamp', 'method_name', 'result']
                missing = [f for f in required if f not in log]
                if missing:
                    tampering_indicators['missing_expected_fields'] += 1
                    tampering_indicators['integrity_score'] -= 0.1
            
            tampering_indicators['integrity_score'] = max(0.0, tampering_indicators['integrity_score'])
            tampering_indicators['is_compromised'] = tampering_indicators['integrity_score'] < 0.7
            
            return tampering_indicators
        except Exception as e:
            print(f"Error checking integrity: {e}")
            return tampering_indicators


# ==========================================
# 2. PDF REPORT GENERATION
# ==========================================

class PDFReportGenerator:
    """Generate professional PDF compliance reports from audit logs"""
    
    @staticmethod
    def generate_pdf_report(report_data: Dict) -> bytes:
        """
        Generate PDF report from audit log data
        
        Args:
            report_data: Dict with keys: title, period, generated_at, summary
        
        Returns:
            PDF file as bytes
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            import io
            
            # Create in-memory PDF
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=30
            )
            story.append(Paragraph(report_data.get('title', 'Audit Report'), title_style))
            story.append(Paragraph(f"Generated: {report_data.get('generated_at', '')}", styles['Normal']))
            story.append(Spacer(1, 0.3 * inch))
            
            # Period and summary
            period = report_data.get('period', 'N/A')
            story.append(Paragraph(f"Period: {period}", styles['Heading2']))
            story.append(Spacer(1, 0.2 * inch))
            
            # Summary data table
            summary = report_data.get('summary', {})
            summary_data = [
                ['Metric', 'Value'],
                ['Total Events', str(summary.get('total_events', 0))],
                ['Fraud Alerts', str(summary.get('fraud_alerts', 0))],
                ['Fee Alerts', str(summary.get('fee_alerts', 0))],
                ['Transaction Alerts', str(summary.get('transaction_alerts', 0))],
            ]
            
            summary_table = Table(summary_data)
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(summary_table)
            
            # Build PDF
            doc.build(story)
            pdf_buffer.seek(0)
            return pdf_buffer.getvalue()
        
        except ImportError:
            # Return error message if reportlab not installed
            print("reportlab not installed. Install with: pip install reportlab")
            return b"PDF generation requires reportlab library"
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return b""


# ==========================================
# 2. DATABASE INDEXING FOR AUDIT LOGS
# ==========================================

class AuditLogIndexing:
    """Create and manage indexes for efficient audit log queries"""
    
    @staticmethod
    def create_indexes(db_file: Path) -> bool:
        """Create indexes on audit log table for performance"""
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            
            # Create indexes
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_logs(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_alert_type ON audit_logs(alert_type)",
                "CREATE INDEX IF NOT EXISTS idx_coin ON audit_logs(coin)",
                "CREATE INDEX IF NOT EXISTS idx_severity ON audit_logs(severity)",
                "CREATE INDEX IF NOT EXISTS idx_timestamp_type ON audit_logs(timestamp, alert_type)",
                "CREATE INDEX IF NOT EXISTS idx_coin_severity ON audit_logs(coin, severity)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error creating indexes: {e}")
            return False
    
    @staticmethod
    def analyze_indexes(db_file: Path) -> Dict:
        """Analyze index performance"""
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA index_list(audit_logs)")
            indexes = cursor.fetchall()
            
            cursor.execute("ANALYZE")
            
            conn.close()
            
            return {
                'total_indexes': len(indexes),
                'indexes': [idx[1] for idx in indexes],
                'analyzed': True
            }
        except Exception as e:
            print(f"Error analyzing indexes: {e}")
            return {'error': str(e)}


# ==========================================
# 3. CRYPTOGRAPHIC AUDIT LOG SIGNING
# ==========================================

class AuditLogSigner:
    """Sign and verify audit log entries for tamper-detection"""
    
    def __init__(self, signing_key: str):
        self.signing_key = signing_key.encode('utf-8') if isinstance(signing_key, str) else signing_key
    
    def sign_entry(self, entry: Dict) -> Dict:
        """Add HMAC signature to audit log entry"""
        try:
            # Create entry copy without signature
            entry_copy = {k: v for k, v in entry.items() if k != 'signature'}
            
            # Create deterministic JSON string
            entry_json = json.dumps(entry_copy, sort_keys=True, separators=(',', ':'))
            
            # Generate HMAC signature
            signature = hmac.new(
                self.signing_key,
                entry_json.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Add signature to entry
            entry_copy['signature'] = signature
            return entry_copy
        except Exception as e:
            print(f"Error signing entry: {e}")
            return entry
    
    def verify_entry(self, entry: Dict) -> bool:
        """Verify HMAC signature of audit log entry"""
        try:
            stored_signature = entry.pop('signature', None)
            if not stored_signature:
                return False
            
            # Recreate entry JSON
            entry_json = json.dumps(entry, sort_keys=True, separators=(',', ':'))
            
            # Compute expected signature
            expected_signature = hmac.new(
                self.signing_key,
                entry_json.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(stored_signature, expected_signature)
        except Exception as e:
            print(f"Error verifying entry: {e}")
            return False


# ==========================================
# 5. WEBSOCKET REAL-TIME UPDATES
# ==========================================

class RealtimeAuditUpdates:
    """WebSocket integration for real-time audit event streaming"""
    
    def __init__(self):
        self.connected_clients = []
        self.event_buffer = []
    
    def register_client(self, client_id: str):
        """Register a WebSocket client"""
        if client_id not in self.connected_clients:
            self.connected_clients.append(client_id)
    
    def unregister_client(self, client_id: str):
        """Unregister a WebSocket client"""
        if client_id in self.connected_clients:
            self.connected_clients.remove(client_id)
    
    def buffer_event(self, event: Dict):
        """Buffer new audit event for broadcasting"""
        self.event_buffer.append({
            'event': event,
            'timestamp': datetime.now().isoformat(),
            'clients_notified': 0
        })
    
    def get_pending_events(self) -> List[Dict]:
        """Get events pending broadcast"""
        return self.event_buffer.copy()
    
    def clear_events(self):
        """Clear event buffer after broadcast"""
        self.event_buffer.clear()
    
    def format_event_for_broadcast(self, event: Dict) -> Dict:
        """Format event for WebSocket broadcast"""
        return {
            'type': 'audit_event',
            'data': {
                'alert_type': event.get('alert_type'),
                'severity': event.get('severity'),
                'coin': event.get('coin'),
                'description': event.get('description'),
                'timestamp': event.get('timestamp')
            }
        }




# ==========================================
# 6. API RATE LIMITING CONFIGURATION
# ==========================================

class AuditAPIRateLimiting:
    """Rate limiting configuration for audit log API endpoints"""
    
    # Default rate limits (requests per hour)
    DEFAULT_LIMITS = {
        '/api/audit-logs/download': 60,
        '/api/audit-logs/summary': 300,
        '/api/audit-logs/events': 300,
        '/api/audit-logs/compliance-report': 100,
        '/api/audit-logs/compliance-report/download': 60,
        '/api/audit-logs/dashboard-data': 600
    }
    
    @staticmethod
    def get_rate_limit_config() -> Dict:
        """Get rate limiting configuration"""
        return {
            'enabled': True,
            'strategy': 'token_bucket',
            'storage': 'memory',
            'limits': AuditAPIRateLimiting.DEFAULT_LIMITS,
            'key_func': 'get_remote_address'
        }
    
    @staticmethod
    def get_rate_limit_string(endpoint: str) -> str:
        """Get Flask-Limiter format string for endpoint"""
        limit = AuditAPIRateLimiting.DEFAULT_LIMITS.get(
            endpoint, 100
        )
        return f"{limit} per hour"

# ==========================================
# 6. ML-BASED ANOMALY DETECTION
# ==========================================

class MLAnomalyDetector:
    """
    ML-based anomaly detection using Isolation Forest
    Detects subtle patterns that rule-based detection misses
    """
    
    def __init__(self, contamination: float = 0.05):
        """
        Initialize ML detector
        contamination: Expected proportion of anomalies (5% default)
        """
        try:
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler
            self.IsolationForest = IsolationForest
            self.StandardScaler = StandardScaler
            self.model = IsolationForest(contamination=contamination, random_state=42)
            self.scaler = StandardScaler()
            self.is_trained = False
            self.feature_names = []
            self.training_history = []
        except ImportError:
            print("WARNING: scikit-learn not installed. ML anomaly detection disabled.")
            self.is_trained = False
            self.model = None
    
    def extract_features(self, entry: Dict) -> List[float]:
        """
        Extract numerical features from audit log entry
        Returns normalized feature vector
        """
        try:
            timestamp = entry.get('timestamp', '')
            action = entry.get('action', '')
            user = entry.get('user', '')
            status = entry.get('status', '')
            
            features = []
            
            # Temporal features
            hour_of_day = datetime.fromisoformat(timestamp).hour if timestamp else 0
            features.append(float(hour_of_day))
            
            # Action frequency encoding
            action_code = hash(action) % 100 if action else 0
            features.append(float(action_code))
            
            # User encoding
            user_code = hash(user) % 100 if user else 0
            features.append(float(user_code))
            
            # Status encoding
            status_map = {'SUCCESS': 1.0, 'FAILURE': 2.0, 'WARNING': 3.0, 'ERROR': 4.0}
            features.append(float(status_map.get(status, 0.0)))
            
            # Additional numeric features
            details = entry.get('details', {})
            if isinstance(details, dict):
                features.append(float(len(details)))  # Details dict size
                features.append(float(details.get('transaction_count', 0)))
                features.append(float(details.get('anomaly_count', 0)))
            else:
                features.extend([0.0, 0.0, 0.0])
            
            return features
        except Exception as e:
            print(f"Error extracting features: {e}")
            return [0.0] * 7
    
    def train_model(self, log_entries: List[Dict]) -> Dict:
        """
        Train ML model on historical audit logs
        Returns training summary
        """
        if self.model is None:
            return {'success': False, 'message': 'ML model not available (scikit-learn not installed). Need at least 10 samples to train.'}
        
        try:
            # Extract features from all entries
            features_list = []
            for entry in log_entries:
                features = self.extract_features(entry)
                features_list.append(features)
            
            if len(features_list) < 10:
                return {
                    'success': False,
                    'message': f'Need at least 10 samples to train. Got {len(features_list)}'
                }
            
            # Convert to numpy array and normalize
            import numpy as np
            X = np.array(features_list)
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            self.model.fit(X_scaled)
            self.is_trained = True
            self.feature_names = ['hour', 'action', 'user', 'status', 'details_size', 'tx_count', 'anomaly_count']
            
            # Store training info
            self.training_history.append({
                'timestamp': datetime.now().isoformat(),
                'samples': len(features_list),
                'features': self.feature_names
            })
            
            return {
                'success': True,
                'samples_used': len(features_list),
                'features': self.feature_names,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'success': False, 'message': f'Training failed: {str(e)}'}
    
    def detect_anomalies(self, entries: List[Dict]) -> List[Dict]:
        """
        Detect anomalies in audit log entries using trained ML model
        Returns list of flagged anomalies with ML scores
        """
        if not self.is_trained or not self.model:
            return []
        
        try:
            import numpy as np
            
            anomalies = []
            features_list = []
            
            # Extract features from entries
            for entry in entries:
                features = self.extract_features(entry)
                features_list.append((features, entry))
            
            if not features_list:
                return []
            
            # Normalize and predict
            X = np.array([f[0] for f in features_list])
            X_scaled = self.scaler.transform(X)
            predictions = self.model.predict(X_scaled)
            scores = self.model.score_samples(X_scaled)
            
            # Collect anomalies (predictions == -1)
            for i, (features, entry) in enumerate(features_list):
                if predictions[i] == -1:  # Anomaly
                    anomalies.append({
                        'timestamp': entry.get('timestamp'),
                        'action': entry.get('action'),
                        'user': entry.get('user'),
                        'ml_score': float(scores[i]),  # Lower = more anomalous
                        'severity': 'HIGH' if scores[i] < -1.0 else 'MEDIUM',
                        'type': 'ML_DETECTED_ANOMALY'
                    })
            
            return anomalies
        except Exception as e:
            print(f"Error in ML detection: {e}")
            return []
    
    def get_model_info(self) -> Dict:
        """Get information about the trained model"""
        return {
            'is_trained': self.is_trained,
            'feature_names': self.feature_names,
            'training_samples': len(self.training_history),
            'last_trained': self.training_history[-1]['timestamp'] if self.training_history else None,
            'training_history': self.training_history[-5:]  # Last 5 trainings
        }