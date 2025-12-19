"""
Audit Log Rotation and Compression Module
==========================================

Handles:
- Automatic rotation of audit logs when size threshold exceeded
- Compression of old audit logs to save storage
- Archive retention policies
- Log cleanup based on age

Author: GitHub Copilot
"""

import os
import gzip
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List


class AuditLogRotation:
    """Manage audit log rotation, compression, and archival"""
    
    def __init__(self, log_path: Path, config: Optional[Dict] = None):
        """
        Initialize log rotation manager
        
        Args:
            log_path: Path to audit log file
            config: Configuration dict with keys:
                - max_file_size_mb: Rotate when log exceeds this size (default: 10)
                - max_age_days: Archive logs older than this (default: 30)
                - retention_days: Keep archived logs for this duration (default: 365)
                - compress: Whether to gzip archived logs (default: True)
                - archive_dir: Directory to store archives (default: logs/archives)
        """
        self.log_path = Path(log_path)
        self.config = config or {}
        
        self.max_file_size_mb = self.config.get('max_file_size_mb', 10)
        self.max_age_days = self.config.get('max_age_days', 30)
        self.retention_days = self.config.get('retention_days', 365)
        self.compress = self.config.get('compress', True)
        
        # Setup archive directory
        self.archive_dir = Path(self.config.get('archive_dir', 
                               self.log_path.parent / 'archives'))
        self.archive_dir.mkdir(parents=True, exist_ok=True)
    
    def should_rotate(self) -> bool:
        """Check if log file should be rotated based on size"""
        if not self.log_path.exists():
            return False
        
        file_size_mb = self.log_path.stat().st_size / (1024 * 1024)
        return file_size_mb > self.max_file_size_mb
    
    def rotate_log(self) -> Dict:
        """
        Rotate current log file to archive
        
        Returns:
            Dict with rotation details {archived: bool, filename: str, size_mb: float}
        """
        if not self.log_path.exists():
            return {'archived': False, 'reason': 'Log file does not exist'}
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f'{self.log_path.stem}_{timestamp}'
            archive_path = self.archive_dir / archive_name
            
            # Copy current log to archive
            shutil.copy2(self.log_path, archive_path)
            
            # Compress if enabled
            if self.compress:
                compressed_path = archive_path.with_suffix('.gz')
                with open(archive_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove uncompressed archive
                archive_path.unlink()
                archive_path = compressed_path
            
            # Clear current log
            self.log_path.write_text('')
            
            file_size_mb = self.log_path.stat().st_size / (1024 * 1024)
            
            return {
                'archived': True,
                'filename': archive_path.name,
                'size_mb': file_size_mb,
                'compressed': self.compress,
                'timestamp': timestamp
            }
        except Exception as e:
            return {
                'archived': False,
                'error': str(e)
            }
    
    def cleanup_old_archives(self) -> Dict:
        """
        Remove archives older than retention period
        
        Returns:
            Dict with cleanup stats {deleted: int, freed_mb: float}
        """
        if not self.archive_dir.exists():
            return {'deleted': 0, 'freed_mb': 0.0}
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        freed_mb = 0.0
        
        try:
            for archive_file in self.archive_dir.glob('*'):
                # Check file modification time
                file_mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    freed_mb += archive_file.stat().st_size / (1024 * 1024)
                    archive_file.unlink()
                    deleted_count += 1
            
            return {
                'deleted': deleted_count,
                'freed_mb': round(freed_mb, 2)
            }
        except Exception as e:
            return {
                'error': str(e),
                'deleted': deleted_count,
                'freed_mb': round(freed_mb, 2)
            }
    
    def get_archive_stats(self) -> Dict:
        """Get statistics about archived logs"""
        if not self.archive_dir.exists():
            return {
                'total_archives': 0,
                'total_size_mb': 0.0,
                'archives': []
            }
        
        archives = []
        total_size = 0
        
        for archive_file in sorted(self.archive_dir.glob('*'), reverse=True):
            size_mb = archive_file.stat().st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
            total_size += size_mb
            
            archives.append({
                'filename': archive_file.name,
                'size_mb': round(size_mb, 2),
                'modified': mtime.isoformat(),
                'compressed': archive_file.suffix == '.gz'
            })
        
        return {
            'total_archives': len(archives),
            'total_size_mb': round(total_size, 2),
            'archives': archives
        }
    
    def perform_maintenance(self) -> Dict:
        """
        Perform full maintenance: check rotation, cleanup old archives
        
        Returns:
            Dict with all maintenance results
        """
        results = {
            'rotation': None,
            'cleanup': None,
            'stats': None
        }
        
        # Check if rotation needed
        if self.should_rotate():
            results['rotation'] = self.rotate_log()
        else:
            results['rotation'] = {'archived': False, 'reason': 'Size threshold not exceeded'}
        
        # Cleanup old archives
        results['cleanup'] = self.cleanup_old_archives()
        
        # Get current stats
        results['stats'] = self.get_archive_stats()
        
        return results


class AuditLogRotationScheduler:
    """Schedule and manage automatic audit log rotation"""
    
    def __init__(self, log_path: Path, config: Optional[Dict] = None):
        """Initialize rotation scheduler"""
        self.rotation = AuditLogRotation(log_path, config)
        self.last_maintenance = None
        self.maintenance_interval_hours = config.get('maintenance_interval_hours', 6) if config else 6
    
    def should_run_maintenance(self) -> bool:
        """Check if maintenance should run based on last run time"""
        if self.last_maintenance is None:
            return True
        
        time_since_last = datetime.now() - self.last_maintenance
        return time_since_last > timedelta(hours=self.maintenance_interval_hours)
    
    def run_maintenance_if_needed(self) -> Optional[Dict]:
        """Run maintenance only if interval has passed"""
        if self.should_run_maintenance():
            results = self.rotation.perform_maintenance()
            self.last_maintenance = datetime.now()
            return results
        return None
    
    def force_maintenance(self) -> Dict:
        """Force maintenance to run immediately"""
        results = self.rotation.perform_maintenance()
        self.last_maintenance = datetime.now()
        return results


if __name__ == '__main__':
    # Example usage
    log_file = Path('outputs/logs/audit.log')
    config = {
        'max_file_size_mb': 10,
        'max_age_days': 30,
        'retention_days': 365,
        'compress': True
    }
    
    rotation = AuditLogRotation(log_file, config)
    
    # Check if rotation needed
    if rotation.should_rotate():
        print("Rotating log...")
        result = rotation.rotate_log()
        print(f"Rotation result: {result}")
    
    # Cleanup old archives
    cleanup_result = rotation.cleanup_old_archives()
    print(f"Cleanup result: {cleanup_result}")
    
    # Get stats
    stats = rotation.get_archive_stats()
    print(f"Archive stats: {stats}")
