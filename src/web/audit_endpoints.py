"""
Audit Log API Endpoints - Optional Enhancements
================================================

This module provides three optional enhancements for audit trail management:
1. API Endpoint - Download precision audit logs (CSV format)
2. Dashboard Visualization - Real-time audit events with severity levels
3. Monthly Compliance Report - Generate compliance summary from audit logs

Author: GitHub Copilot
Last Modified: December 2025
"""

import json
import csv
import io
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
from flask import jsonify, send_file


class AuditLogManager:
    """Manager for precision audit logs"""
    
    def __init__(self, audit_log_file: Path):
        self.audit_log_file = audit_log_file
    
    def read_audit_logs(self, start_date=None, end_date=None, alert_type=None):
        """Read and filter audit logs"""
        logs = []
        
        if not self.audit_log_file.exists():
            return logs
        
        try:
            with open(self.audit_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        # Apply date filtering
                        if start_date or end_date:
                            entry_date = datetime.fromisoformat(entry.get('timestamp', ''))
                            if start_date and entry_date < start_date:
                                continue
                            if end_date and entry_date > end_date:
                                continue
                        
                        # Apply type filtering
                        if alert_type and entry.get('alert_type') != alert_type:
                            continue
                        
                        logs.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading audit logs: {e}")
        
        return logs
    
    def export_to_csv(self, logs=None):
        """Export audit logs to CSV format"""
        if logs is None:
            logs = self.read_audit_logs()
        
        csv_buffer = io.StringIO()
        
        if not logs:
            writer = csv.writer(csv_buffer)
            writer.writerow(['No audit logs found'])
            csv_buffer.seek(0)
            return csv_buffer.getvalue()
        
        # Get all unique keys from logs
        all_keys = set()
        for log in logs:
            all_keys.update(log.keys())
        
        fieldnames = sorted(list(all_keys))
        
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        
        for log in logs:
            # Convert Decimal to string for CSV compatibility
            row = {}
            for key, value in log.items():
                if isinstance(value, Decimal):
                    row[key] = str(value)
                elif isinstance(value, dict):
                    row[key] = json.dumps(value)
                else:
                    row[key] = value
            writer.writerow(row)
        
        csv_buffer.seek(0)
        return csv_buffer.getvalue()
    
    def get_summary_statistics(self, logs=None):
        """Generate summary statistics from audit logs"""
        if logs is None:
            logs = self.read_audit_logs()
        
        summary = {
            'total_events': len(logs),
            'events_by_type': defaultdict(int),
            'events_by_severity': defaultdict(int),
            'fraud_alerts': 0,
            'fee_alerts': 0,
            'tax_impact_total': Decimal('0'),
            'most_common_coin': None,
            'date_range': {}
        }
        
        coin_counts = defaultdict(int)
        
        for log in logs:
            # Count by type
            alert_type = log.get('alert_type', 'unknown')
            summary['events_by_type'][alert_type] += 1
            
            # Count by severity
            severity = log.get('severity', 'medium')
            summary['events_by_severity'][severity] += 1
            
            # Special counts
            if alert_type in ['PUMP_DUMP', 'SUSPICIOUS_VOLUME', 'WASH_SALE', 'STRUCTURING']:
                summary['fraud_alerts'] += 1
            
            if alert_type == 'FEE_CALCULATION':
                summary['fee_alerts'] += 1
            
            # Tax impact
            if 'tax_impact' in log:
                try:
                    impact = Decimal(str(log['tax_impact']))
                    summary['tax_impact_total'] += impact
                except:
                    pass
            
            # Track coins
            if 'coin' in log:
                coin_counts[log['coin']] += 1
        
        # Most common coin
        if coin_counts:
            summary['most_common_coin'] = max(coin_counts, key=coin_counts.get)
        
        # Date range
        if logs:
            dates = [datetime.fromisoformat(log.get('timestamp', '')) for log in logs if log.get('timestamp')]
            if dates:
                summary['date_range'] = {
                    'start': min(dates).isoformat(),
                    'end': max(dates).isoformat()
                }
        
        return summary
    
    def generate_monthly_report(self, year=None, month=None):
        """Generate monthly compliance report"""
        if year is None or month is None:
            now = datetime.now()
            year, month = now.year, now.month
        
        # Create date range for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get logs for this month
        logs = self.read_audit_logs(start_date=start_date, end_date=end_date)
        
        summary = self.get_summary_statistics(logs)
        
        report = {
            'title': f'Monthly Compliance Report - {year}-{month:02d}',
            'generated_at': datetime.now().isoformat(),
            'period': {
                'year': year,
                'month': month,
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': summary,
            'audit_events': len(logs),
            'fraud_alerts': summary['fraud_alerts'],
            'fee_alerts': summary['fee_alerts'],
            'events_by_type': dict(summary['events_by_type']),
            'events_by_severity': dict(summary['events_by_severity']),
            'tax_impact': str(summary['tax_impact_total']),
            'most_common_coin': summary['most_common_coin']
        }
        
        return report


def create_audit_endpoints(app, base_dir):
    """Create audit log API endpoints and register with Flask app"""
    
    PRECISION_AUDIT_LOG = base_dir / 'outputs' / 'logs' / 'precision_audit.log'
    audit_manager = AuditLogManager(PRECISION_AUDIT_LOG)
    
    @app.route('/api/audit-logs/download', methods=['GET'])
    def api_download_audit_logs():
        """Download precision audit logs as CSV"""
        try:
            from flask import session, request, redirect, url_for
            
            # Require authentication
            if 'username' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Get filter parameters
            alert_type = request.args.get('type')
            days = int(request.args.get('days', 30))
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get logs with filters
            logs = audit_manager.read_audit_logs(
                start_date=start_date,
                end_date=end_date,
                alert_type=alert_type
            )
            
            # Export to CSV
            csv_content = audit_manager.export_to_csv(logs)
            
            # Return as downloadable CSV
            csv_bytes = io.BytesIO(csv_content.encode('utf-8'))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            return send_file(
                csv_bytes,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'precision_audit_{timestamp}.csv'
            )
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audit-logs/summary', methods=['GET'])
    def api_audit_logs_summary():
        """Get audit logs summary statistics"""
        try:
            from flask import session, request
            
            # Require authentication
            if 'username' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Get filter parameters
            days = int(request.args.get('days', 30))
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get logs
            logs = audit_manager.read_audit_logs(start_date=start_date, end_date=end_date)
            
            # Generate summary
            summary = audit_manager.get_summary_statistics(logs)
            
            # Convert Decimal to string for JSON serialization
            summary['tax_impact_total'] = str(summary['tax_impact_total'])
            summary['events_by_type'] = dict(summary['events_by_type'])
            summary['events_by_severity'] = dict(summary['events_by_severity'])
            
            return jsonify({
                'success': True,
                'summary': summary,
                'period_days': days
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audit-logs/events', methods=['GET'])
    def api_audit_logs_events():
        """Get recent audit log events (paginated)"""
        try:
            from flask import session, request
            
            # Require authentication
            if 'username' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Get pagination parameters
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))
            days = int(request.args.get('days', 30))
            alert_type = request.args.get('type')
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get logs
            logs = audit_manager.read_audit_logs(
                start_date=start_date,
                end_date=end_date,
                alert_type=alert_type
            )
            
            # Sort by timestamp (newest first)
            logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Paginate
            total = len(logs)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_logs = logs[start_idx:end_idx]
            
            # Convert Decimal values to strings
            for log in paginated_logs:
                for key, value in log.items():
                    if isinstance(value, Decimal):
                        log[key] = str(value)
            
            return jsonify({
                'success': True,
                'events': paginated_logs,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audit-logs/compliance-report', methods=['GET'])
    def api_audit_logs_compliance_report():
        """Generate monthly compliance report"""
        try:
            from flask import session, request
            
            # Require authentication
            if 'username' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Get year and month parameters
            year = request.args.get('year')
            month = request.args.get('month')
            
            if year:
                year = int(year)
            if month:
                month = int(month)
            
            # Generate report
            report = audit_manager.generate_monthly_report(year=year, month=month)
            
            # Convert Decimal values to strings
            report['tax_impact'] = str(report['tax_impact'])
            
            return jsonify({
                'success': True,
                'report': report
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audit-logs/compliance-report/download', methods=['GET'])
    def api_download_compliance_report():
        """Download compliance report as JSON or CSV"""
        try:
            from flask import session, request
            
            # Require authentication
            if 'username' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Get parameters
            year = int(request.args.get('year', datetime.now().year))
            month = int(request.args.get('month', datetime.now().month))
            format_type = request.args.get('format', 'json').lower()
            
            # Generate report
            report = audit_manager.generate_monthly_report(year=year, month=month)
            
            if format_type == 'csv':
                # Convert to CSV format
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                
                # Write report summary
                writer.writerow(['Monthly Compliance Report'])
                writer.writerow([f"Period: {year}-{month:02d}"])
                writer.writerow([''])
                writer.writerow(['Summary Statistics'])
                writer.writerow(['Metric', 'Value'])
                
                writer.writerow(['Total Audit Events', report['audit_events']])
                writer.writerow(['Fraud Alerts', report['fraud_alerts']])
                writer.writerow(['Fee Alerts', report['fee_alerts']])
                writer.writerow(['Total Tax Impact', report['tax_impact']])
                writer.writerow(['Most Common Coin', report['most_common_coin'] or 'N/A'])
                
                writer.writerow([''])
                writer.writerow(['Events by Type'])
                writer.writerow(['Type', 'Count'])
                for event_type, count in report['events_by_type'].items():
                    writer.writerow([event_type, count])
                
                writer.writerow([''])
                writer.writerow(['Events by Severity'])
                writer.writerow(['Severity', 'Count'])
                for severity, count in report['events_by_severity'].items():
                    writer.writerow([severity, count])
                
                csv_buffer.seek(0)
                csv_bytes = io.BytesIO(csv_buffer.getvalue().encode('utf-8'))
                
                timestamp = f'{year}{month:02d}'
                return send_file(
                    csv_bytes,
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=f'compliance_report_{timestamp}.csv'
                )
            else:
                # Return as JSON
                json_data = json.dumps(report, default=str, indent=2)
                json_bytes = io.BytesIO(json_data.encode('utf-8'))
                
                timestamp = f'{year}{month:02d}'
                return send_file(
                    json_bytes,
                    mimetype='application/json',
                    as_attachment=True,
                    download_name=f'compliance_report_{timestamp}.json'
                )
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/audit-logs/dashboard-data', methods=['GET'])
    def api_audit_logs_dashboard_data():
        """Get real-time dashboard data for audit visualization"""
        try:
            from flask import session
            
            # Require authentication
            if 'username' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            # Get all recent logs
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            logs = audit_manager.read_audit_logs(start_date=start_date, end_date=end_date)
            
            # Organize by date for chart
            events_by_date = defaultdict(lambda: defaultdict(int))
            severity_timeline = defaultdict(lambda: defaultdict(int))
            
            for log in logs:
                try:
                    log_date = datetime.fromisoformat(log.get('timestamp', ''))
                    date_str = log_date.date().isoformat()
                    
                    alert_type = log.get('alert_type', 'unknown')
                    severity = log.get('severity', 'medium')
                    
                    events_by_date[date_str][alert_type] += 1
                    severity_timeline[date_str][severity] += 1
                except:
                    pass
            
            # Get summary
            summary = audit_manager.get_summary_statistics(logs)
            
            dashboard_data = {
                'summary': {
                    'total_events': summary['total_events'],
                    'fraud_alerts': summary['fraud_alerts'],
                    'fee_alerts': summary['fee_alerts'],
                    'tax_impact': str(summary['tax_impact_total']),
                    'most_common_coin': summary['most_common_coin']
                },
                'events_by_date': dict(events_by_date),
                'severity_timeline': dict(severity_timeline),
                'events_by_type': dict(summary['events_by_type']),
                'events_by_severity': dict(summary['events_by_severity']),
                'recent_events': []
            }
            
            # Add 10 most recent events
            sorted_logs = sorted(logs, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
            for log in sorted_logs:
                event = {
                    'timestamp': log.get('timestamp', ''),
                    'type': log.get('alert_type', 'unknown'),
                    'severity': log.get('severity', 'medium'),
                    'coin': log.get('coin', ''),
                    'message': log.get('description', '')
                }
                dashboard_data['recent_events'].append(event)
            
            return jsonify({
                'success': True,
                'dashboard': dashboard_data,
                'last_updated': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return audit_manager
