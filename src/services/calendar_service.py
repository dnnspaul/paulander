import caldav
from datetime import datetime, date, timedelta
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
    
    def _get_calendars(self) -> list:
        """Get all calendars"""
        if not self.client:
            self.client = self._get_client()
        
        principal = self.client.principal()
        calendars = principal.calendars()
        
        if not calendars:
            raise Exception("No calendars found")
        
        return calendars
    
    def get_upcoming_events(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming events for the next N days from all calendars"""
        try:
            calendars = self._get_calendars()
            
            # Define time range
            now = datetime.now(pytz.UTC)
            start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now + timedelta(days=days_ahead)
            
            event_list = []
            
            for calendar in calendars:
                try:
                    # Search for events
                    events = calendar.search(
                        start=start_of_today,
                        end=end_date,
                        event=True,
                        expand=True
                    )
                except Exception:
                    continue
                
                for event in events:
                    try:
                        event_data = self._parse_event_ical(event)
                        if event_data and event_data['start']:
                            event_list.append(event_data)
                    except Exception:
                        continue
            
            # Sort by start time
            event_list.sort(key=lambda x: x['start'])
            
            return event_list
            
        except Exception as e:
            print(f"Error fetching calendar events: {e}")
            return []
    
    def _parse_event_ical(self, event) -> Dict[str, Any] | None:
        """Parse a calendar event using the icalendar library (caldav 2.0+)"""
        ical = event.icalendar_instance
        if ical is None:
            return None
        
        for component in ical.walk():
            if component.name != "VEVENT":
                continue
            
            title = str(component.get("SUMMARY", "No Title"))
            
            # Handle start time
            dtstart_prop = component.get("DTSTART")
            start_time = self._parse_ical_dt(dtstart_prop) if dtstart_prop else None
            
            # Handle end time
            dtend_prop = component.get("DTEND")
            end_time = self._parse_ical_dt(dtend_prop) if dtend_prop else None
            
            # Handle location
            location = component.get("LOCATION")
            location = str(location) if location else None
            
            # Handle description
            description = component.get("DESCRIPTION")
            description = str(description) if description else None
            
            # All-day check
            all_day = isinstance(dtstart_prop.dt, date) and not isinstance(dtstart_prop.dt, datetime) if dtstart_prop else False
            
            event_id = str(component.get("UID", "unknown"))
            
            return {
                'id': event_id,
                'title': title,
                'start': start_time,
                'end': end_time,
                'location': location,
                'description': description,
                'all_day': all_day
            }
        
        return None
    
    def _parse_ical_dt(self, prop) -> datetime | None:
        """Parse a datetime/date from an icalendar property"""
        if prop is None:
            return None
        dt = prop.dt if hasattr(prop, 'dt') else prop
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            return dt
        elif isinstance(dt, date):
            # Convert date to datetime at midnight UTC
            return datetime(dt.year, dt.month, dt.day, tzinfo=pytz.UTC)
        return None
    
    def get_today_events(self) -> List[Dict[str, Any]]:
        """Get today's events for AI image generation prompt"""
        try:
            calendars = self._get_calendars()
            
            # Get today's events
            now = datetime.now(pytz.UTC)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            event_list = []
            
            for calendar in calendars:
                try:
                    events = calendar.search(
                        start=start_of_day,
                        end=end_of_day,
                        event=True,
                        expand=True
                    )
                except Exception:
                    continue
                
                for event in events:
                    try:
                        event_data = self._parse_event_ical(event)
                        if event_data:
                            event_list.append(event_data)
                    except Exception:
                        continue
            
            # Sort by start time
            event_list.sort(key=lambda x: x['start'] if x['start'] else datetime.min.replace(tzinfo=pytz.UTC))
            
            return event_list
            
        except Exception as e:
            print(f"Error fetching today's events: {e}")
            return []

