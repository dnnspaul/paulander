import caldav
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any
from src.services.config_service import ConfigService

class CalendarService:
    def __init__(self):
        self.config_service = ConfigService()
        self.client = None
        self.calendar = None
    
    def _get_client(self, apple_id: str = None, app_password: str = None):
        """Get CalDAV client with authentication"""
        if not apple_id:
            apple_id = self.config_service.get('apple_id')
        if not app_password:
            app_password = self.config_service.get('app_password')
            
        if not apple_id or not app_password:
            raise ValueError("Apple ID and App Password are required")
        
        # iCloud CalDAV URL
        url = f"https://caldav.icloud.com/"
        
        try:
            client = caldav.DAVClient(
                url=url,
                username=apple_id,
                password=app_password
            )
            return client
        except Exception as e:
            raise Exception(f"Failed to connect to iCloud calendar: {str(e)}")
    
    def test_connection(self, apple_id: str, app_password: str) -> Dict[str, Any]:
        """Test calendar connection"""
        try:
            client = self._get_client(apple_id, app_password)
            principal = client.principal()
            calendars = principal.calendars()
            
            if calendars:
                return {
                    'success': True,
                    'message': f'Successfully connected! Found {len(calendars)} calendar(s).'
                }
            else:
                return {
                    'success': False,
                    'message': 'Connected but no calendars found.'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }
    
    def _get_calendar(self):
        """Get the primary calendar"""
        if not self.client:
            self.client = self._get_client()
        
        if not self.calendar:
            principal = self.client.principal()
            calendars = principal.calendars()
            
            if not calendars:
                raise Exception("No calendars found")
            
            # Use the first calendar or find the primary one
            self.calendar = calendars[0]
            
        return self.calendar
    
    def get_upcoming_events(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming events for the next N days"""
        try:
            calendar = self._get_calendar()
            
            # Define time range
            now = datetime.now(pytz.UTC)
            end_date = now + timedelta(days=days_ahead)
            
            # Search for events
            events = calendar.search(
                start=now,
                end=end_date,
                event=True,
                expand=True
            )
            
            event_list = []
            
            for event in events:
                try:
                    # Parse the event
                    vevent = event.vobject_instance.vevent
                    
                    # Extract basic information
                    event_data = {
                        'id': str(event.id),
                        'title': str(vevent.summary.value) if hasattr(vevent, 'summary') else 'No Title',
                        'start': self._parse_datetime(vevent.dtstart.value) if hasattr(vevent, 'dtstart') else None,
                        'end': self._parse_datetime(vevent.dtend.value) if hasattr(vevent, 'dtend') else None,
                        'location': str(vevent.location.value) if hasattr(vevent, 'location') else None,
                        'description': str(vevent.description.value) if hasattr(vevent, 'description') else None,
                        'all_day': self._is_all_day_event(vevent)
                    }
                    
                    # Only add events that have a start time and are in the future
                    if event_data['start'] and event_data['start'] > now:
                        event_list.append(event_data)
                        
                except Exception as e:
                    print(f"Error parsing event: {e}")
                    continue
            
            # Sort by start time
            event_list.sort(key=lambda x: x['start'])
            
            return event_list
            
        except Exception as e:
            print(f"Error fetching calendar events: {e}")
            return []
    
    def _parse_datetime(self, dt):
        """Parse datetime from various formats"""
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                # Assume local timezone
                dt = pytz.UTC.localize(dt)
            return dt
        elif isinstance(dt, str):
            # Try to parse string datetime
            try:
                parsed = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    parsed = pytz.UTC.localize(parsed)
                return parsed
            except:
                pass
        
        return None
    
    def _is_all_day_event(self, vevent):
        """Check if event is all-day"""
        if hasattr(vevent, 'dtstart') and hasattr(vevent.dtstart, 'value'):
            return not isinstance(vevent.dtstart.value, datetime)
        return False
    
    def get_today_events(self) -> List[Dict[str, Any]]:
        """Get today's events for AI image generation prompt"""
        try:
            calendar = self._get_calendar()
            
            # Get today's events
            now = datetime.now(pytz.UTC)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            events = calendar.search(
                start=start_of_day,
                end=end_of_day,
                event=True,
                expand=True
            )
            
            event_list = []
            
            for event in events:
                try:
                    vevent = event.vobject_instance.vevent
                    event_data = {
                        'title': str(vevent.summary.value) if hasattr(vevent, 'summary') else 'No Title',
                        'start': self._parse_datetime(vevent.dtstart.value) if hasattr(vevent, 'dtstart') else None,
                        'location': str(vevent.location.value) if hasattr(vevent, 'location') else None,
                        'all_day': self._is_all_day_event(vevent)
                    }
                    
                    event_list.append(event_data)
                    
                except Exception as e:
                    continue
            
            # Sort by start time
            event_list.sort(key=lambda x: x['start'] if x['start'] else datetime.min.replace(tzinfo=pytz.UTC))
            
            return event_list
            
        except Exception as e:
            print(f"Error fetching today's events: {e}")
            return []