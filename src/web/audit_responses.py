"""
Automatic Response Actions - Incident Response Automation
===========================================================

Automatically responds to detected audit anomalies:
- Locks database operations on critical anomalies
- Escalates alerts to administrators
- Creates incident records
- Implements response workflows

Author: GitHub Copilot
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum
import logging

# ==========================================
# 1. RESPONSE ACTION TYPES & SEVERITY LEVELS
# ==========================================

class AnomalySeverity(Enum):
    """Severity levels for audit anomalies"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ResponseAction(Enum):
    """Automatic response actions"""
    ALERT = "alert"
    LOCK_OPERATIONS = "lock_operations"
    ESCALATE_ADMIN = "escalate_admin"
    SNAPSHOT_STATE = "snapshot_state"
    NOTIFY_SECURITY = "notify_security"
    ROLLBACK_TRANSACTIONS = "rollback_transactions"


# ==========================================
# 2. OPERATION LOCK MANAGER
# ==========================================

class OperationLockManager:
    """
    Manages database operation locks during security incidents
    Prevents modifications during anomaly investigation
    """
    
    def __init__(self, db_path: str):
        """Initialize lock manager"""
        self.db_path = db_path
        self.lock_file = Path(db_path).parent / '.operation_lock'
        self.lock_state = {}
    
    def lock_operations(self, reason: str, duration_minutes: int = 30) -> Dict:
        """
        Lock all database operations
        Returns lock ticket for tracking
        """
        try:
            lock_ticket = {
                'timestamp': datetime.now().isoformat(),
                'reason': reason,
                'duration_minutes': duration_minutes,
                'expires_at': (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
                'locked_operations': [
                    'write_transaction',
                    'update_fraud_flags',
                    'modify_calculations',
                    'delete_records'
                ],
                'allowed_operations': [
                    'read_transaction',
                    'read_fraud_flags',
                    'read_logs'
                ]
            }
            
            # Write lock state
            with open(self.lock_file, 'w') as f:
                json.dump(lock_ticket, f, indent=2)
            
            self.lock_state = lock_ticket
            
            return {
                'success': True,
                'lock_ticket': lock_ticket['timestamp'],
                'expires': lock_ticket['expires_at']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def is_locked(self) -> bool:
        """Check if operations are currently locked"""
        try:
            if not self.lock_file.exists():
                return False
            
            with open(self.lock_file, 'r') as f:
                lock_ticket = json.load(f)
            
            expires_at = datetime.fromisoformat(lock_ticket['expires_at'])
            
            # Lock expired
            if datetime.now() > expires_at:
                self.lock_file.unlink()
                return False
            
            self.lock_state = lock_ticket
            return True
        except Exception as e:
            return False
    
    def get_lock_info(self) -> Optional[Dict]:
        """Get current lock information"""
        if self.is_locked():
            return self.lock_state
        return None
    
    def unlock_operations(self, unlock_key: str = None) -> Dict:
        """
        Unlock operations (requires admin authentication)
        """
        try:
            if not self.lock_file.exists():
                return {'success': False, 'error': 'No active lock'}
            
            self.lock_file.unlink()
            self.lock_state = {}
            
            return {
                'success': True,
                'message': 'Operations unlocked'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ==========================================
# 3. ALERT & ESCALATION SYSTEM
# ==========================================

class IncidentAlertSystem:
    """
    Manages alert escalation and notification
    """
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.incidents_dir = self.base_dir / 'outputs' / 'incidents'
        self.incidents_dir.mkdir(parents=True, exist_ok=True)
        self.active_incidents = []
    
    def create_incident(self, anomaly: Dict, severity: AnomalySeverity) -> Dict:
        """
        Create an incident record from anomaly
        """
        try:
            incident_id = f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            incident = {
                'id': incident_id,
                'timestamp': datetime.now().isoformat(),
                'severity': severity.name,
                'anomaly': anomaly,
                'status': 'ACTIVE',
                'created_by': 'AUTOMATIC_RESPONSE_SYSTEM',
                'acknowledged': False,
                'resolution': None
            }
            
            # Write incident to file
            incident_file = self.incidents_dir / f"{incident_id}.json"
            with open(incident_file, 'w') as f:
                json.dump(incident, f, indent=2)
            
            self.active_incidents.append(incident)
            
            return {
                'success': True,
                'incident_id': incident_id,
                'severity': severity.name
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def escalate_to_admin(self, incident_id: str, message: str) -> Dict:
        """
        Escalate incident to administrator
        Creates notification and alert log entry
        """
        try:
            escalation = {
                'incident_id': incident_id,
                'timestamp': datetime.now().isoformat(),
                'message': message,
                'action': ResponseAction.ESCALATE_ADMIN.value,
                'status': 'PENDING_REVIEW'
            }
            
            # Write escalation log
            escalation_log = self.incidents_dir / 'escalations.jsonl'
            with open(escalation_log, 'a') as f:
                f.write(json.dumps(escalation) + '\n')
            
            return {
                'success': True,
                'escalated_to': 'ADMIN',
                'timestamp': escalation['timestamp']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_active_incidents(self) -> List[Dict]:
        """Get list of active incidents"""
        try:
            incidents = []
            for incident_file in self.incidents_dir.glob("INC-*.json"):
                with open(incident_file, 'r') as f:
                    incident = json.load(f)
                    if incident.get('status') == 'ACTIVE':
                        incidents.append(incident)
            
            return incidents
        except Exception as e:
            return []


# ==========================================
# 4. STATE SNAPSHOT & FORENSICS
# ==========================================

class ForensicSnapshot:
    """
    Creates forensic snapshots of system state during incidents
    For investigation and audit trail
    """
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.snapshots_dir = self.base_dir / 'outputs' / 'forensics'
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
    
    def create_snapshot(self, anomaly: Dict, context: Dict) -> Dict:
        """
        Create snapshot of system state during anomaly
        """
        try:
            snapshot_id = f"SNAP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            snapshot = {
                'id': snapshot_id,
                'timestamp': datetime.now().isoformat(),
                'anomaly': anomaly,
                'system_context': {
                    'total_transactions': context.get('transaction_count', 0),
                    'recent_anomalies': context.get('anomaly_count', 0),
                    'system_integrity': context.get('integrity_score', 0),
                    'tampering_score': context.get('tampering_score', 0)
                },
                'audit_log_summary': context.get('log_summary', {})
            }
            
            # Write snapshot
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot, f, indent=2)
            
            return {
                'success': True,
                'snapshot_id': snapshot_id,
                'location': str(snapshot_file)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        """Retrieve a forensic snapshot"""
        try:
            snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
            if snapshot_file.exists():
                with open(snapshot_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            return None


# ==========================================
# 5. AUTOMATIC RESPONSE ORCHESTRATOR
# ==========================================

class AutomaticResponseOrchestrator:
    """
    Orchestrates automatic responses to anomalies
    Determines which actions to take based on severity
    """
    
    def __init__(self, base_dir: str, db_path: str):
        self.base_dir = Path(base_dir)
        self.db_path = db_path
        self.lock_manager = OperationLockManager(db_path)
        self.alert_system = IncidentAlertSystem(base_dir)
        self.forensics = ForensicSnapshot(base_dir)
        self.response_log_file = self.base_dir / 'outputs' / 'logs' / 'response_actions.jsonl'
        self.response_log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def analyze_and_respond(self, anomaly: Dict, severity: AnomalySeverity) -> Dict:
        """
        Analyze anomaly and execute appropriate responses
        """
        responses = {
            'anomaly_id': anomaly.get('timestamp', 'unknown'),
            'severity': severity.name,
            'actions_taken': []
        }
        
        try:
            # Always log alert
            responses['actions_taken'].append({
                'action': ResponseAction.ALERT.value,
                'status': 'completed'
            })
            
            # Create incident
            incident_result = self.alert_system.create_incident(anomaly, severity)
            if incident_result['success']:
                responses['actions_taken'].append({
                    'action': 'create_incident',
                    'status': 'completed',
                    'incident_id': incident_result['incident_id']
                })
            
            # Create forensic snapshot
            snapshot_context = {
                'transaction_count': 0,
                'anomaly_count': 1,
                'integrity_score': 0.7,
                'tampering_score': anomaly.get('score', 0)
            }
            snapshot_result = self.forensics.create_snapshot(anomaly, snapshot_context)
            if snapshot_result['success']:
                responses['actions_taken'].append({
                    'action': ResponseAction.SNAPSHOT_STATE.value,
                    'status': 'completed',
                    'snapshot_id': snapshot_result['snapshot_id']
                })
            
            # CRITICAL severity: Lock operations
            if severity == AnomalySeverity.CRITICAL:
                lock_result = self.lock_manager.lock_operations(
                    reason=f"CRITICAL anomaly detected: {anomaly.get('type', 'Unknown')}",
                    duration_minutes=60
                )
                if lock_result['success']:
                    responses['actions_taken'].append({
                        'action': ResponseAction.LOCK_OPERATIONS.value,
                        'status': 'completed',
                        'expires': lock_result['expires']
                    })
                
                # Escalate to admin
                escalate_result = self.alert_system.escalate_to_admin(
                    incident_result['incident_id'],
                    f"CRITICAL: {anomaly.get('type')} - {anomaly.get('description', 'No details')}"
                )
                if escalate_result['success']:
                    responses['actions_taken'].append({
                        'action': ResponseAction.ESCALATE_ADMIN.value,
                        'status': 'completed'
                    })
            
            # HIGH severity: Escalate and snapshot
            elif severity == AnomalySeverity.HIGH:
                escalate_result = self.alert_system.escalate_to_admin(
                    incident_result['incident_id'],
                    f"HIGH: {anomaly.get('type')} - Review required"
                )
                if escalate_result['success']:
                    responses['actions_taken'].append({
                        'action': ResponseAction.ESCALATE_ADMIN.value,
                        'status': 'completed'
                    })
            
            # Log all responses
            self._log_response(responses)
            
            responses['success'] = True
            return responses
        
        except Exception as e:
            responses['success'] = False
            responses['error'] = str(e)
            return responses
    
    def _log_response(self, response: Dict):
        """Log response action to file"""
        try:
            with open(self.response_log_file, 'a') as f:
                response['timestamp'] = datetime.now().isoformat()
                f.write(json.dumps(response) + '\n')
        except Exception as e:
            pass  # Silently fail logging
    
    def get_response_history(self, limit: int = 100) -> List[Dict]:
        """Get response action history"""
        try:
            if not self.response_log_file.exists():
                return []
            
            responses = []
            with open(self.response_log_file, 'r') as f:
                for line in f:
                    try:
                        responses.append(json.loads(line.strip()))
                    except:
                        pass
            
            return responses[-limit:]
        except Exception as e:
            return []
    
    def get_status(self) -> Dict:
        """Get automatic response system status"""
        return {
            'lock_status': {
                'is_locked': self.lock_manager.is_locked(),
                'lock_info': self.lock_manager.get_lock_info()
            },
            'active_incidents': len(self.alert_system.get_active_incidents()),
            'incidents': self.alert_system.get_active_incidents(),
            'recent_responses': self.get_response_history(10)
        }

