"""
Weather service integration for music-weather correlation
"""
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import requests
from collections import defaultdict
import numpy as np
from loguru import logger
import os
from functools import lru_cache


class WeatherService:
    """Fetches and manages weather data"""
    
    def __init__(self):
        # In production, use environment variable
        self.api_key = os.getenv('OPENWEATHER_API_KEY', 'demo_key')
        self.base_url = 'https://api.openweathermap.org/data/2.5'
        
        # Weather categories
        self.weather_categories = {
            'clear': ['Clear'],
            'cloudy': ['Clouds'],
            'rainy': ['Rain', 'Drizzle'],
            'stormy': ['Thunderstorm'],
            'snowy': ['Snow'],
            'misty': ['Mist', 'Fog', 'Haze']
        }
        
        # Cache for weather data
        self._weather_cache = {}
    
    @lru_cache(maxsize=100)
    def get_historical_weather(self, lat: float, lon: float, date: datetime) -> Optional[Dict[str, Any]]:
        """
        Get historical weather for a specific date and location
        Note: In demo mode, returns synthetic data
        """
        # Check cache
        cache_key = f"{lat},{lon},{date.date()}"
        if cache_key in self._weather_cache:
            return self._weather_cache[cache_key]
        
        # In demo mode, generate synthetic weather data
        if self.api_key == 'demo_key':
            weather_data = self._generate_synthetic_weather(date)
        else:
            # Real API call (requires paid OpenWeatherMap subscription for historical data)
            weather_data = self._fetch_real_weather(lat, lon, date)
        
        # Cache the result
        self._weather_cache[cache_key] = weather_data
        return weather_data
    
    def _generate_synthetic_weather(self, date: datetime) -> Dict[str, Any]:
        """
        Generate synthetic weather data for demo purposes
        Creates realistic patterns based on date
        """
        # Use date as seed for consistency
        np.random.seed(int(date.timestamp()) % 10000)
        
        # Seasonal patterns
        month = date.month
        if month in [12, 1, 2]:  # Winter
            temp_base = 5
            weather_options = ['Clear', 'Clouds', 'Snow', 'Mist']
            weights = [0.3, 0.3, 0.3, 0.1]
        elif month in [3, 4, 5]:  # Spring
            temp_base = 15
            weather_options = ['Clear', 'Clouds', 'Rain', 'Drizzle']
            weights = [0.4, 0.3, 0.2, 0.1]
        elif month in [6, 7, 8]:  # Summer
            temp_base = 25
            weather_options = ['Clear', 'Clouds', 'Thunderstorm']
            weights = [0.6, 0.3, 0.1]
        else:  # Fall
            temp_base = 12
            weather_options = ['Clear', 'Clouds', 'Rain', 'Mist']
            weights = [0.3, 0.4, 0.2, 0.1]
        
        # Add daily variation
        hour = date.hour
        if 6 <= hour <= 18:  # Daytime
            temp_variation = np.random.normal(5, 2)
        else:  # Nighttime
            temp_variation = np.random.normal(-5, 2)
        
        temperature = temp_base + temp_variation
        
        # Select weather condition
        weather_main = np.random.choice(weather_options, p=weights)
        
        return {
            'date': date.isoformat(),
            'weather': {
                'main': weather_main,
                'description': weather_main.lower(),
                'id': hash(weather_main) % 900 + 100
            },
            'temperature': {
                'current': round(temperature, 1),
                'feels_like': round(temperature + np.random.normal(0, 2), 1),
                'min': round(temperature - 3, 1),
                'max': round(temperature + 3, 1)
            },
            'humidity': int(np.random.normal(60, 20)),
            'pressure': int(np.random.normal(1013, 10)),
            'wind_speed': round(np.random.exponential(5), 1),
            'clouds': int(np.random.uniform(0, 100))
        }
    
    def _fetch_real_weather(self, lat: float, lon: float, date: datetime) -> Optional[Dict[str, Any]]:
        """
        Fetch real weather data from OpenWeatherMap API
        Note: Historical data requires paid subscription
        """
        try:
            # For current weather (free tier)
            if (datetime.now() - date).days <= 1:
                url = f"{self.base_url}/weather"
                params = {
                    'lat': lat,
                    'lon': lon,
                    'appid': self.api_key,
                    'units': 'metric'
                }
            else:
                # Historical data endpoint (requires subscription)
                timestamp = int(date.timestamp())
                url = f"{self.base_url}/onecall/timemachine"
                params = {
                    'lat': lat,
                    'lon': lon,
                    'dt': timestamp,
                    'appid': self.api_key,
                    'units': 'metric'
                }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self._format_weather_response(data, date)
            else:
                logger.warning(f"Weather API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching weather: {e}")
            return None
    
    def _format_weather_response(self, data: Dict[str, Any], date: datetime) -> Dict[str, Any]:
        """Format API response to consistent structure"""
        # Handle different response formats
        if 'weather' in data:
            # Current weather format
            weather = data['weather'][0]
            temp = data['main']
            
            return {
                'date': date.isoformat(),
                'weather': {
                    'main': weather['main'],
                    'description': weather['description'],
                    'id': weather['id']
                },
                'temperature': {
                    'current': temp['temp'],
                    'feels_like': temp['feels_like'],
                    'min': temp['temp_min'],
                    'max': temp['temp_max']
                },
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'],
                'clouds': data['clouds']['all']
            }
        else:
            # Historical format (onecall)
            current = data.get('current', data.get('hourly', [{}])[0])
            weather = current.get('weather', [{}])[0]
            
            return {
                'date': date.isoformat(),
                'weather': {
                    'main': weather.get('main', 'Unknown'),
                    'description': weather.get('description', 'unknown'),
                    'id': weather.get('id', 0)
                },
                'temperature': {
                    'current': current.get('temp', 20),
                    'feels_like': current.get('feels_like', 20),
                    'min': current.get('temp', 20) - 3,
                    'max': current.get('temp', 20) + 3
                },
                'humidity': current.get('humidity', 50),
                'pressure': current.get('pressure', 1013),
                'wind_speed': current.get('wind_speed', 0),
                'clouds': current.get('clouds', 0)
            }
    
    def categorize_weather(self, weather_data: Dict[str, Any]) -> str:
        """Categorize weather into simplified categories"""
        weather_main = weather_data['weather']['main']
        
        for category, conditions in self.weather_categories.items():
            if weather_main in conditions:
                return category
        
        return 'other'
    
    def get_weather_features(self, weather_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract normalized features for correlation analysis"""
        return {
            'temperature': weather_data['temperature']['current'] / 40,  # Normalize to 0-1
            'feels_like': weather_data['temperature']['feels_like'] / 40,
            'humidity': weather_data['humidity'] / 100,
            'pressure': (weather_data['pressure'] - 980) / 60,  # Normalize around typical range
            'wind_speed': min(weather_data['wind_speed'] / 20, 1),
            'cloudiness': weather_data['clouds'] / 100
        }
    
    def get_location_from_ip(self) -> Tuple[float, float]:
        """
        Get approximate location from IP address
        Returns (latitude, longitude)
        """
        try:
            # Use IP geolocation service
            response = requests.get('https://ipapi.co/json/', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('latitude', 40.7128), data.get('longitude', -74.0060)
            else:
                # Default to New York
                return 40.7128, -74.0060
        except:
            # Default to New York
            return 40.7128, -74.0060
    
    def get_bulk_weather(self, lat: float, lon: float, 
                        start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get weather data for a date range"""
        weather_data = []
        current_date = start_date
        
        while current_date <= end_date:
            weather = self.get_historical_weather(lat, lon, current_date)
            if weather:
                weather_data.append(weather)
            current_date += timedelta(days=1)
        
        return weather_data