from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import threading
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
            try:
                self._setup_jobs()
                self.scheduler.start()
                self.running = True
                print("Scheduler started")
                
                # Schedule initial display refresh after a delay to allow web server to start first
                print("Scheduling initial display refresh (delayed to allow web server startup)...")
                self._schedule_initial_refresh()
            except Exception as e:
                if "already running" in str(e).lower():
                    print("Scheduler already running")
                    self.running = True
                else:
                    print(f"Failed to start scheduler: {e}")
                    raise
    
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
        
        # Schedule B&W display refresh (at :00 and :30 of every hour)
        self.scheduler.add_job(
            func=self._refresh_bw_display,
            trigger=CronTrigger(minute='0,30'),
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
            next_run_time = getattr(job, 'next_run_time', None)
            if next_run_time:
                next_run = next_run_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                next_run = 'Calculating...'
            print(f"  - {job.name}: {next_run}")
    
    def _schedule_initial_refresh(self):
        """Schedule initial display refresh with delay to allow web server to start"""
        # Schedule B&W display refresh after 5 seconds
        run_time = datetime.now() + timedelta(seconds=5)
        self.scheduler.add_job(
            func=self._initial_bw_refresh,
            trigger='date',
            run_date=run_time,
            id='initial_bw_refresh',
            name='Initial B&W Display Refresh',
            replace_existing=True
        )
        
        # Schedule color display refresh after 10 seconds (takes longer)
        run_time = datetime.now() + timedelta(seconds=10)
        self.scheduler.add_job(
            func=self._initial_color_refresh,
            trigger='date',
            run_date=run_time,
            id='initial_color_refresh',
            name='Initial Color Display Refresh',
            replace_existing=True
        )
        
        print("Initial display refreshes scheduled:")
        print("  - B&W display: in 5 seconds")
        print("  - Color display: in 10 seconds")
        print("Web server will be available immediately")
    
    def _initial_bw_refresh(self):
        """Initial B&W display refresh (one-time)"""
        try:
            print(f"[{datetime.now()}] Performing initial B&W display refresh...")
            self._refresh_bw_display()
        except Exception as e:
            print(f"Initial B&W display refresh failed: {e}")
    
    def _initial_color_refresh(self):
        """Initial color display refresh (one-time)"""
        try:
            print(f"[{datetime.now()}] Performing initial color display refresh...")
            self._refresh_color_display()
        except Exception as e:
            print(f"Initial color display refresh failed: {e}")
    
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