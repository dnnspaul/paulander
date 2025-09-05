from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from src.services.config_service import ConfigService
from src.services.display_service import DisplayService

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.config_service = ConfigService()
        self.display_service = DisplayService()
        self.running = False
    
    def start(self):
        """Start the scheduler"""
        if not self.running:
            self._setup_jobs()
            self.scheduler.start()
            self.running = True
            print("Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            print("Scheduler stopped")
    
    def _setup_jobs(self):
        """Set up scheduled jobs"""
        # Get configuration
        config = self.config_service.get_config()
        
        # Schedule B&W display refresh (every N minutes)
        refresh_interval = config.get('display_refresh_interval', 1800)  # Default 30 minutes
        self.scheduler.add_job(
            func=self._refresh_bw_display,
            trigger=IntervalTrigger(seconds=refresh_interval),
            id='bw_display_refresh',
            name='Refresh B&W Display',
            replace_existing=True
        )
        
        # Schedule color display refresh (daily at configured time)
        color_refresh_time = config.get('color_display_refresh_time', '06:00')
        try:
            hour, minute = map(int, color_refresh_time.split(':'))
            self.scheduler.add_job(
                func=self._refresh_color_display,
                trigger=CronTrigger(hour=hour, minute=minute),
                id='color_display_refresh',
                name='Refresh Color Display',
                replace_existing=True
            )
        except ValueError:
            print(f"Invalid color display refresh time: {color_refresh_time}")
        
        print("Scheduled jobs:")
        for job in self.scheduler.get_jobs():
            next_run = getattr(job, 'next_run_time', 'Unknown')
            print(f"  - {job.name}: {next_run}")
    
    def _refresh_bw_display(self):
        """Refresh B&W display"""
        try:
            print(f"[{datetime.now()}] Refreshing B&W display...")
            self.display_service.update_bw_display()
            print("B&W display refresh completed")
        except Exception as e:
            print(f"B&W display refresh failed: {e}")
    
    def _refresh_color_display(self):
        """Refresh color display"""
        try:
            print(f"[{datetime.now()}] Refreshing color display...")
            self.display_service.update_color_display()
            print("Color display refresh completed")
        except Exception as e:
            print(f"Color display refresh failed: {e}")
    
    def update_schedule(self):
        """Update scheduler with new configuration"""
        if self.running:
            self._setup_jobs()
            print("Scheduler updated with new configuration")
    
    def get_job_status(self):
        """Get status of scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            next_run_time = getattr(job, 'next_run_time', None)
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': next_run_time.isoformat() if next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return {
            'running': self.running,
            'jobs': jobs
        }