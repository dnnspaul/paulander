"""
German translations for OpenWeatherMap weather conditions
Optimized for small e-ink display - short and concise
"""

# Compact mapping of OpenWeatherMap weather descriptions to German
WEATHER_TRANSLATIONS = {
    # Thunderstorm group (2xx) - All variations -> "Gewitter"
    "thunderstorm with light rain": "Gewitter",
    "thunderstorm with rain": "Gewitter",
    "thunderstorm with heavy rain": "Gewitter", 
    "light thunderstorm": "Gewitter",
    "thunderstorm": "Gewitter",
    "heavy thunderstorm": "Gewitter",
    "ragged thunderstorm": "Gewitter",
    "thunderstorm with light drizzle": "Gewitter",
    "thunderstorm with drizzle": "Gewitter",
    "thunderstorm with heavy drizzle": "Gewitter",
    
    # Drizzle group (3xx) - All variations -> "Nieselregen"
    "light intensity drizzle": "Nieselregen",
    "drizzle": "Nieselregen",
    "heavy intensity drizzle": "Nieselregen",
    "light intensity drizzle rain": "Nieselregen",
    "drizzle rain": "Nieselregen",
    "heavy intensity drizzle rain": "Nieselregen",
    "shower rain and drizzle": "Nieselregen",
    "heavy shower rain and drizzle": "Nieselregen",
    "shower drizzle": "Nieselregen",
    
    # Rain group (5xx) - Light/moderate -> "Regen", heavy -> "Starkregen"
    "light rain": "Regen",
    "moderate rain": "Regen",
    "heavy intensity rain": "Starkregen",
    "very heavy rain": "Starkregen",
    "extreme rain": "Starkregen",
    "freezing rain": "Eisregen",
    "light intensity shower rain": "Schauer",
    "shower rain": "Schauer", 
    "heavy intensity shower rain": "Starke Schauer",
    "ragged shower rain": "Schauer",
    
    # Snow group (6xx) - Most variations -> "Schnee"
    "light snow": "Schnee",
    "snow": "Schnee",
    "heavy snow": "Starker Schnee",
    "sleet": "Schneematsch",
    "light shower sleet": "Schneematsch",
    "shower sleet": "Schneematsch",
    "light rain and snow": "Schneematsch",
    "rain and snow": "Schneematsch",
    "light shower snow": "Schneeschauer",
    "shower snow": "Schneeschauer",
    "heavy shower snow": "Schneeschauer",
    
    # Atmosphere group (7xx) - Simple terms
    "mist": "Dunst",
    "smoke": "Rauch",
    "haze": "Dunst",
    "sand/dust whirls": "Staub",
    "fog": "Nebel",
    "sand": "Sand", 
    "dust": "Staub",
    "volcanic ash": "Asche",
    "squalls": "Böen",
    "tornado": "Tornado",
    
    # Clear group (800) - Short and clear
    "clear sky": "Klar",
    "clear": "Klar",
    
    # Clouds group (80x) - Simplified cloud descriptions
    "few clouds": "Leicht bewölkt",
    "scattered clouds": "Bewölkt",
    "broken clouds": "Stark bewölkt", 
    "overcast clouds": "Bedeckt",
    "overcast": "Bedeckt",
    "clouds": "Bewölkt",
    "partly cloudy": "Teilweise bewölkt",
    "mostly cloudy": "Bewölkt",
    
    # Common variations and additional translations
    "sunny": "Sonnig",
    "hot": "Heiß",
    "cold": "Kalt",
    "windy": "Windig",
    "humid": "Schwül",
    "dry": "Trocken",
    "wet": "Nass",
    "stormy": "Stürmisch",
    
    # Error states - Short versions
    "weather data unavailable": "Keine Daten",
    "data unavailable": "Keine Daten",
    "no forecast available": "Keine Vorhersage",
    "weather unavailable": "Kein Wetter",
    "n/a": "k.A.",
    "unknown": "Unbekannt",
    "no forecast": "Keine Vorhersage",
}

# General translations for UI elements - also short
UI_TRANSLATIONS = {
    # General terms - optimized for display
    "today": "Heute",
    "tomorrow": "Morgen",
    "current": "Jetzt",
    "forecast": "Vorhersage",
    "temperature": "Temp",
    "humidity": "Feucht",
    "wind": "Wind",
    "pressure": "Druck",
    "visibility": "Sicht",
    "location": "Ort",
    "events": "Termine",
    "no events": "Keine Termine",
    "upcoming events": "Termine",
    "weather": "Wetter",
    "no events today": "Keine Termine heute",
    "updated": "Aktualisiert",
}

def translate_weather_description(description: str) -> str:
    """
    Translate an English weather description to German.
    Returns the German translation if found, otherwise returns the original.
    Case-insensitive matching.
    """
    if not description:
        return description
    
    # Convert to lowercase for matching
    desc_lower = description.lower().strip()
    
    # Check direct match first
    if desc_lower in WEATHER_TRANSLATIONS:
        return WEATHER_TRANSLATIONS[desc_lower]
    
    # Check if it's a title-cased version
    for key, value in WEATHER_TRANSLATIONS.items():
        if key.lower() == desc_lower:
            return value
    
    # Return original if no translation found
    return description

def translate_ui_text(text: str) -> str:
    """
    Translate common UI text to German.
    Returns the German translation if found, otherwise returns the original.
    Case-insensitive matching.
    """
    if not text:
        return text
    
    # Convert to lowercase for matching
    text_lower = text.lower().strip()
    
    # Check direct match first
    if text_lower in UI_TRANSLATIONS:
        return UI_TRANSLATIONS[text_lower]
    
    # Return original if no translation found
    return text