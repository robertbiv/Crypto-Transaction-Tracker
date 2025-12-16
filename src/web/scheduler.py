"""
Scheduling Manager - Handles automated tax calculation scheduling
"""
import json
from pathlib import Path
from datetime import datetime, time
from typing import Dict, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import subprocess
import sys
import logging

logger = logging.getLogger("scheduler")

class ScheduleManager:
    """Manages automated scheduling of tax calculations"""
    
    def __init__(self, base_dir: Path, auto_runner_path: Path):
        self.base_dir = base_dir
        self.auto_runner_path = auto_runner_path
        self.config_file = base_dir / 'configs' / 'schedule_config.json'
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Scheduler initialized")
        
    def load_schedule_config(self) -> Dict:
        """Load schedule configuration from file"""
        if not self.config_file.exists():
            return {
                'enabled': False,
                'schedules': []
            }
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load schedule config: {e}")
            return {'enabled': False, 'schedules': []}
    
    def save_schedule_config(self, config: Dict):
        """Save schedule configuration to file"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            logger.info("Schedule configuration saved")
        except Exception as e:
            logger.error(f"Failed to save schedule config: {e}")
            raise
    
    def run_tax_calculation(self, cascade: bool = False):
        """Execute tax calculation (called by scheduler)"""
        try:
            logger.info(f"Running scheduled tax calculation (cascade={cascade})")
            cmd = [sys.executable, str(self.auto_runner_path)]
            if cascade:
                cmd.append('--cascade')
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Scheduled tax calculation completed successfully")
            else:
                logger.error(f"Scheduled tax calculation failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error running scheduled tax calculation: {e}")
    
    def add_schedule(self, schedule_id: str, frequency: str, time_str: str = None, 
                    day_of_week: str = None, cascade: bool = False):
        """Add or update a schedule
        
        Args:
            schedule_id: Unique identifier for the schedule
            frequency: 'daily', 'weekly', 'monthly', or 'interval'
            time_str: Time in HH:MM format (for daily/weekly/monthly)
            day_of_week: Day name for weekly (mon, tue, wed, thu, fri, sat, sun)
            cascade: Whether to run in cascade mode
        """
        # Remove existing schedule if present
        try:
            self.scheduler.remove_job(schedule_id)
        except:
            pass
        
        # Parse time if provided
        hour, minute = 0, 0
        if time_str:
            try:
                time_obj = datetime.strptime(time_str, '%H:%M').time()
                hour, minute = time_obj.hour, time_obj.minute
            except:
                logger.error(f"Invalid time format: {time_str}")
                raise ValueError("Time must be in HH:MM format")
        
        # Create trigger based on frequency
        if frequency == 'daily':
            trigger = CronTrigger(hour=hour, minute=minute)
        elif frequency == 'weekly':
            if not day_of_week:
                raise ValueError("day_of_week required for weekly schedule")
            trigger = CronTrigger(day_of_week=day_of_week.lower(), hour=hour, minute=minute)
        elif frequency == 'monthly':
            trigger = CronTrigger(day=1, hour=hour, minute=minute)
        elif frequency == 'interval':
            # Run every N hours (default 24 if no time specified)
            hours = hour if hour > 0 else 24
            trigger = IntervalTrigger(hours=hours)
        else:
            raise ValueError(f"Invalid frequency: {frequency}")
        
        # Add job to scheduler
        self.scheduler.add_job(
            func=self.run_tax_calculation,
            trigger=trigger,
            id=schedule_id,
            kwargs={'cascade': cascade},
            replace_existing=True
        )
        
        logger.info(f"Schedule added: {schedule_id} ({frequency})")
    
    def remove_schedule(self, schedule_id: str):
        """Remove a schedule"""
        try:
            self.scheduler.remove_job(schedule_id)
            logger.info(f"Schedule removed: {schedule_id}")
        except Exception as e:
            logger.warning(f"Failed to remove schedule {schedule_id}: {e}")
    
    def get_active_schedules(self) -> List[Dict]:
        """Get list of active schedules"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs
    
    def reload_schedules(self):
        """Reload all schedules from config file"""
        config = self.load_schedule_config()
        
        # Clear existing schedules
        for job in self.scheduler.get_jobs():
            self.scheduler.remove_job(job.id)
        
        if not config.get('enabled', False):
            logger.info("Scheduling is disabled")
            return
        
        # Add all configured schedules
        for schedule in config.get('schedules', []):
            try:
                self.add_schedule(
                    schedule_id=schedule['id'],
                    frequency=schedule['frequency'],
                    time_str=schedule.get('time'),
                    day_of_week=schedule.get('day_of_week'),
                    cascade=schedule.get('cascade', False)
                )
            except Exception as e:
                logger.error(f"Failed to add schedule {schedule.get('id')}: {e}")
        
        logger.info(f"Loaded {len(config.get('schedules', []))} schedule(s)")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler shut down")
