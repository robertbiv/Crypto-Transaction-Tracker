"""
Comparative Analysis & Trend Reporting
=======================================

Generates historical analysis and trend reports:
- System integrity trends over time
- Anomaly frequency patterns
- Correlation with transaction activity
- Risk trend analysis

Author: GitHub Copilot
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from statistics import mean, stdev

# ==========================================
# 1. TREND DATA COLLECTOR
# ==========================================

class TrendDataCollector:
    """
    Collects and aggregates historical audit data for trend analysis
    """
    
    def __init__(self, audit_log_path: str):
        self.audit_log_path = Path(audit_log_path)
        self.data_cache = {}
    
    def collect_daily_statistics(self, days_back: int = 30) -> Dict:
        """
        Collect daily statistics from audit logs
        Returns daily aggregations
        """
        try:
            daily_stats = defaultdict(lambda: {
                'total_entries': 0,
                'anomalies': 0,
                'errors': 0,
                'warnings': 0,
                'integrity_score': 1.0,
                'tampering_incidents': 0,
                'transactions': 0,
                'timestamp': None
            })
            
            if not self.audit_log_path.exists():
                return daily_stats
            
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            with open(self.audit_log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        timestamp = entry.get('timestamp', '')
                        
                        if timestamp:
                            entry_date = datetime.fromisoformat(timestamp)
                            if entry_date < cutoff_date:
                                continue
                            
                            day_key = entry_date.date().isoformat()
                            day_data = daily_stats[day_key]
                            
                            # Aggregate counts
                            day_data['total_entries'] += 1
                            day_data['timestamp'] = timestamp
                            
                            # Count by status
                            status = entry.get('status', '').upper()
                            if status == 'ERROR':
                                day_data['errors'] += 1
                            elif status == 'WARNING':
                                day_data['warnings'] += 1
                            
                            # Count anomalies
                            if entry.get('is_anomaly'):
                                day_data['anomalies'] += 1
                            
                            # Count transaction activities
                            if 'transaction' in entry.get('action', '').lower():
                                day_data['transactions'] += 1
                    except:
                        pass
            
            return daily_stats
        except Exception as e:
            print(f"Error collecting daily stats: {e}")
            return defaultdict(dict)
    
    def collect_hourly_statistics(self, hours_back: int = 24) -> Dict:
        """Collect hourly statistics for near-real-time trends"""
        try:
            hourly_stats = defaultdict(lambda: {
                'entries': 0,
                'anomalies': 0,
                'errors': 0,
                'hour': None
            })
            
            if not self.audit_log_path.exists():
                return hourly_stats
            
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            with open(self.audit_log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        timestamp = entry.get('timestamp', '')
                        
                        if timestamp:
                            entry_time = datetime.fromisoformat(timestamp)
                            if entry_time < cutoff_time:
                                continue
                            
                            hour_key = entry_time.replace(minute=0, second=0, microsecond=0).isoformat()
                            hour_data = hourly_stats[hour_key]
                            
                            hour_data['entries'] += 1
                            hour_data['hour'] = hour_key
                            
                            if entry.get('is_anomaly'):
                                hour_data['anomalies'] += 1
                            
                            if entry.get('status') == 'ERROR':
                                hour_data['errors'] += 1
                    except:
                        pass
            
            return hourly_stats
        except Exception as e:
            return defaultdict(dict)


# ==========================================
# 2. TREND ANALYZER
# ==========================================

class TrendAnalyzer:
    """
    Analyzes trends and patterns in audit data
    """
    
    def __init__(self, collector: TrendDataCollector):
        self.collector = collector
    
    def calculate_integrity_trend(self, days_back: int = 30) -> Dict:
        """
        Calculate system integrity score trend over time
        """
        try:
            daily_stats = self.collector.collect_daily_statistics(days_back)
            
            trend = {
                'period_days': days_back,
                'daily_scores': [],
                'avg_score': 0.0,
                'min_score': 1.0,
                'max_score': 0.0,
                'trend_direction': 'stable',  # improving, degrading, stable
                'volatility': 0.0
            }
            
            scores = []
            for day in sorted(daily_stats.keys()):
                day_data = daily_stats[day]
                
                # Calculate integrity score for this day
                error_penalty = day_data.get('errors', 0) * 0.05
                anomaly_penalty = day_data.get('anomalies', 0) * 0.10
                score = max(0.0, 1.0 - error_penalty - anomaly_penalty)
                
                scores.append(score)
                trend['daily_scores'].append({
                    'date': day,
                    'score': round(score, 3),
                    'anomalies': day_data.get('anomalies', 0),
                    'errors': day_data.get('errors', 0)
                })
            
            if scores:
                trend['avg_score'] = round(mean(scores), 3)
                trend['min_score'] = round(min(scores), 3)
                trend['max_score'] = round(max(scores), 3)
                
                # Calculate volatility (standard deviation)
                if len(scores) > 1:
                    trend['volatility'] = round(stdev(scores), 3)
                
                # Determine trend direction
                if len(scores) >= 7:
                    first_week_avg = mean(scores[:7])
                    last_week_avg = mean(scores[-7:])
                    
                    if last_week_avg > first_week_avg + 0.05:
                        trend['trend_direction'] = 'improving'
                    elif last_week_avg < first_week_avg - 0.05:
                        trend['trend_direction'] = 'degrading'
            
            return trend
        except Exception as e:
            return {'error': str(e)}
    
    def calculate_anomaly_frequency(self, days_back: int = 30) -> Dict:
        """
        Analyze frequency and patterns of anomalies
        """
        try:
            daily_stats = self.collector.collect_daily_statistics(days_back)
            
            anomaly_data = {
                'period_days': days_back,
                'total_anomalies': 0,
                'anomaly_free_days': 0,
                'daily_distribution': [],
                'peak_anomaly_day': None,
                'avg_anomalies_per_day': 0.0,
                'anomaly_days': 0
            }
            
            anomaly_counts = []
            for day in sorted(daily_stats.keys()):
                day_data = daily_stats[day]
                anomalies = day_data.get('anomalies', 0)
                anomaly_counts.append(anomalies)
                anomaly_data['total_anomalies'] += anomalies
                
                if anomalies == 0:
                    anomaly_data['anomaly_free_days'] += 1
                else:
                    anomaly_data['anomaly_days'] += 1
                
                anomaly_data['daily_distribution'].append({
                    'date': day,
                    'anomalies': anomalies
                })
            
            if anomaly_counts:
                anomaly_data['avg_anomalies_per_day'] = round(
                    anomaly_data['total_anomalies'] / len(anomaly_counts), 2
                )
                
                # Find peak anomaly day
                max_anomalies = max(anomaly_counts)
                if max_anomalies > 0:
                    peak_index = anomaly_counts.index(max_anomalies)
                    peak_date = sorted(daily_stats.keys())[peak_index]
                    anomaly_data['peak_anomaly_day'] = {
                        'date': peak_date,
                        'anomalies': max_anomalies
                    }
            
            return anomaly_data
        except Exception as e:
            return {'error': str(e)}
    
    def calculate_activity_correlation(self, days_back: int = 30) -> Dict:
        """
        Correlate anomalies with transaction activity
        """
        try:
            daily_stats = self.collector.collect_daily_statistics(days_back)
            
            correlation = {
                'period_days': days_back,
                'correlation_coefficient': 0.0,
                'high_activity_days': 0,
                'high_activity_anomalies': 0,
                'low_activity_days': 0,
                'low_activity_anomalies': 0,
                'analysis': []
            }
            
            activity_anomaly_pairs = []
            for day in sorted(daily_stats.keys()):
                day_data = daily_stats[day]
                transactions = day_data.get('transactions', 0)
                anomalies = day_data.get('anomalies', 0)
                
                activity_anomaly_pairs.append({
                    'date': day,
                    'transactions': transactions,
                    'anomalies': anomalies
                })
                
                if transactions > 50:  # High activity threshold
                    correlation['high_activity_days'] += 1
                    correlation['high_activity_anomalies'] += anomalies
                else:
                    correlation['low_activity_days'] += 1
                    correlation['low_activity_anomalies'] += anomalies
            
            correlation['analysis'] = activity_anomaly_pairs[-7:]  # Last 7 days
            
            return correlation
        except Exception as e:
            return {'error': str(e)}
    
    def get_risk_score_trend(self, days_back: int = 30) -> Dict:
        """
        Calculate overall risk score trend
        """
        try:
            daily_stats = self.collector.collect_daily_statistics(days_back)
            
            risk_trend = {
                'period_days': days_back,
                'risk_scores': [],
                'current_risk': 'LOW',
                'risk_trajectory': 'stable'
            }
            
            scores = []
            for day in sorted(daily_stats.keys()):
                day_data = daily_stats[day]
                
                # Risk score calculation
                error_factor = min(day_data.get('errors', 0) / 10.0, 1.0) * 40
                anomaly_factor = min(day_data.get('anomalies', 0) / 5.0, 1.0) * 60
                risk_score = (error_factor + anomaly_factor) / 100.0
                
                scores.append(risk_score)
                risk_trend['risk_scores'].append({
                    'date': day,
                    'risk': round(risk_score, 3),
                    'level': 'CRITICAL' if risk_score > 0.7 else 'HIGH' if risk_score > 0.4 else 'MEDIUM' if risk_score > 0.2 else 'LOW'
                })
            
            if scores:
                # Current risk
                current_risk_score = scores[-1]
                risk_trend['current_risk'] = 'CRITICAL' if current_risk_score > 0.7 else 'HIGH' if current_risk_score > 0.4 else 'MEDIUM' if current_risk_score > 0.2 else 'LOW'
                
                # Trajectory
                if len(scores) >= 7:
                    recent_avg = mean(scores[-7:])
                    older_avg = mean(scores[:-7])
                    
                    if recent_avg > older_avg + 0.1:
                        risk_trend['risk_trajectory'] = 'increasing'
                    elif recent_avg < older_avg - 0.1:
                        risk_trend['risk_trajectory'] = 'decreasing'
            
            return risk_trend
        except Exception as e:
            return {'error': str(e)}


# ==========================================
# 3. REPORT GENERATOR
# ==========================================

class ComparativeAnalysisReport:
    """
    Generates comprehensive comparative analysis reports
    """
    
    def __init__(self, base_dir: str, audit_log_path: str):
        self.base_dir = Path(base_dir)
        self.reports_dir = self.base_dir / 'outputs' / 'reports' / 'comparative'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        self.collector = TrendDataCollector(audit_log_path)
        self.analyzer = TrendAnalyzer(self.collector)
    
    def generate_comprehensive_report(self, days_back: int = 30) -> Dict:
        """
        Generate comprehensive comparative analysis report
        """
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'analysis_period_days': days_back,
                'integrity_trend': self.analyzer.calculate_integrity_trend(days_back),
                'anomaly_frequency': self.analyzer.calculate_anomaly_frequency(days_back),
                'activity_correlation': self.analyzer.calculate_activity_correlation(days_back),
                'risk_score_trend': self.analyzer.get_risk_score_trend(days_back)
            }
            
            # Save report
            report_file = self.reports_dir / f"comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            return {
                'success': True,
                'report': report,
                'saved_to': str(report_file)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def generate_summary_report(self) -> Dict:
        """
        Generate quick summary report for dashboard
        """
        try:
            integrity = self.analyzer.calculate_integrity_trend(7)  # Last 7 days
            anomalies = self.analyzer.calculate_anomaly_frequency(7)
            risk = self.analyzer.get_risk_score_trend(7)
            
            summary = {
                'generated_at': datetime.now().isoformat(),
                'integrity_score': integrity.get('avg_score', 0.0),
                'integrity_trend': integrity.get('trend_direction', 'stable'),
                'anomaly_count_7d': anomalies.get('total_anomalies', 0),
                'anomaly_free_days': anomalies.get('anomaly_free_days', 0),
                'current_risk_level': risk.get('current_risk', 'UNKNOWN'),
                'risk_trajectory': risk.get('risk_trajectory', 'stable')
            }
            
            return {
                'success': True,
                'summary': summary
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_recent_reports(self, limit: int = 10) -> List[str]:
        """Get list of recent reports"""
        try:
            reports = sorted(self.reports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            return [r.name for r in reports[:limit]]
        except Exception as e:
            return []

