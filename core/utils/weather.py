import os
import requests
from django.conf import settings

API_KEY = getattr(settings, 'WEATHER_API_KEY', 'd76f6b52979d4579b5543501260204')

def get_weather(city):
    """
    Fetches current forecast from WeatherAPI.com and formats it to match
    what the frontend expects for the legacy forecast panel:
    {
        "time": str,
        "temp": float,
        "weather": str,
        "rain": float
    }
    """
    url = f"https://api.weatherapi.com/v1/forecast.json?key={API_KEY}&q={city}&days=1&aqi=no&alerts=no"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
        
        forecastday = data.get("forecast", {}).get("forecastday", [])
        if not forecastday:
            return []
            
        hours = forecastday[0].get("hour", [])
        forecasts = []
        
        # Take the first 5 hourly forecast slots
        for h in hours[:5]:
            forecasts.append({
                "time": h.get("time"),
                "temp": h.get("temp_c"),
                "weather": h.get("condition", {}).get("text"),
                "rain": h.get("precip_mm", 0.0)
            })
        return forecasts
    except Exception as e:
        print(f"Error fetching weather from WeatherAPI.com: {e}")
        return []