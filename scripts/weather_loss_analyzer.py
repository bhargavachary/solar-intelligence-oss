#!/usr/bin/env python3
"""
Weather & Loss Analysis for Solar Generation
Integrates actual weather data to explain performance and losses
"""

import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_weather_data(location: str = "Berhampur", date: str = None):
    """
    Get weather data for a location and date.
    Uses Open-Meteo API (free, no API key needed)
    """
    # Berhampur/Golanthara coordinates
    lat, lon = 19.3150, 84.7941
    
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        # Open-Meteo API for historical weather
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': 'temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m',
            'daily': 'temperature_2m_max,temperature_2m_min,sunshine_duration,precipitation_sum',
            'timezone': 'Asia/Kolkata',
            'start_date': date,
            'end_date': date
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract daily summary
        daily = data.get('daily', {})
        hourly = data.get('hourly', {})
        
        # Compute daylight hours average (6 AM to 6 PM)
        daylight_start = 6
        daylight_end = 18
        
        temps = hourly.get('temperature_2m', [])
        humidity = hourly.get('relative_humidity_2m', [])
        clouds = hourly.get('cloud_cover', [])
        wind = hourly.get('wind_speed_10m', [])
        
        daylight_temps = temps[daylight_start:daylight_end] if len(temps) >= daylight_end else temps
        daylight_humidity = humidity[daylight_start:daylight_end] if len(humidity) >= daylight_end else humidity
        daylight_clouds = clouds[daylight_start:daylight_end] if len(clouds) >= daylight_end else clouds
        daylight_wind = wind[daylight_start:daylight_end] if len(wind) >= daylight_end else wind
        
        return {
            'date': date,
            'location': 'Golanthara (Berhampur), Odisha',
            'temperature': {
                'max': daily.get('temperature_2m_max', [0])[0],
                'min': daily.get('temperature_2m_min', [0])[0],
                'avg_daylight': sum(daylight_temps) / len(daylight_temps) if daylight_temps else 0,
            },
            'humidity_avg': sum(daylight_humidity) / len(daylight_humidity) if daylight_humidity else 0,
            'cloud_cover_avg': sum(daylight_clouds) / len(daylight_clouds) if daylight_clouds else 0,
            'wind_speed_avg': sum(daylight_wind) / len(daylight_wind) if daylight_wind else 0,
            'sunshine_duration_hours': daily.get('sunshine_duration', [0])[0] / 3600,
            'precipitation_mm': daily.get('precipitation_sum', [0])[0],
        }
    except Exception as e:
        print(f"⚠️  Weather API unavailable: {e}")
        return {
            'date': date,
            'location': 'Golanthara (Berhampur), Odisha',
            'error': str(e),
            'fallback': True,
        }


def analyze_hourly_generation(energy_log):
    """
    Analyze hourly generation from 30-min data points
    Returns peak hourly average and hourly breakdown
    """
    records = energy_log.get('records', [])
    
    if not records:
        return {}
    
    # Group by hour
    hourly_data = {}
    
    for rec in records:
        ts = datetime.strptime(rec['timestamp'], '%Y-%m-%d %H:%M:%S')
        hour = ts.hour
        
        if hour not in hourly_data:
            hourly_data[hour] = []
        
        hourly_data[hour].append({
            'timestamp': rec['timestamp'],
            'power_kw': rec.get('current_power_kw', 0),
            'daily_yield': rec.get('daily_yield_kwh', 0),
        })
    
    # Compute hourly averages
    hourly_summary = []
    for hour in sorted(hourly_data.keys()):
        records_in_hour = hourly_data[hour]
        avg_power = sum(r['power_kw'] for r in records_in_hour) / len(records_in_hour)
        
        hourly_summary.append({
            'hour': hour,
            'avg_power_kw': round(avg_power, 3),
            'samples': len(records_in_hour),
            'energy_kwh': round(avg_power * 1.0, 3),  # kWh for 1 hour
        })
    
    peak_hour = max(hourly_summary, key=lambda x: x['avg_power_kw']) if hourly_summary else {}
    
    return {
        'hourly_breakdown': hourly_summary,
        'peak_hour': peak_hour,
        'total_hours': len(hourly_summary),
    }


def analyze_losses(daily_yield_kwh: float, capacity_kw: float, weather: dict):
    """
    Comprehensive loss analysis based on actual conditions
    """
    # Theoretical maximum (ideal conditions)
    # Peak sun hours for Berhampur in February: ~5.5 hours
    peak_sun_hours = 5.5
    theoretical_max = capacity_kw * peak_sun_hours
    
    # Actual vs theoretical
    efficiency_pct = (daily_yield_kwh / theoretical_max * 100) if theoretical_max > 0 else 0
    total_loss_pct = 100 - efficiency_pct
    
    # Break down losses
    losses = {
        'theoretical_max_kwh': round(theoretical_max, 2),
        'actual_kwh': daily_yield_kwh,
        'total_loss_pct': round(total_loss_pct, 1),
        'breakdown': {}
    }
    
    # Temperature losses
    temp_avg = weather.get('temperature', {}).get('avg_daylight', 25)
    if temp_avg > 25:
        # Panel efficiency drops ~0.4% per °C above 25°C
        temp_loss = (temp_avg - 25) * 0.4
        losses['breakdown']['temperature'] = {
            'loss_pct': round(temp_loss, 1),
            'reason': f'Panel heating at {temp_avg:.1f}°C (optimal: 25°C)',
        }
    
    # Cloud cover / irradiance losses
    cloud_cover = weather.get('cloud_cover_avg', 0)
    if cloud_cover > 10:
        irradiance_loss = cloud_cover * 0.7  # Approximate
        losses['breakdown']['cloud_cover'] = {
            'loss_pct': round(irradiance_loss, 1),
            'reason': f'{cloud_cover:.0f}% cloud cover reducing irradiance',
        }
    
    # Humidity losses (coastal haze)
    humidity = weather.get('humidity_avg', 0)
    if humidity > 60:
        humidity_loss = (humidity - 60) * 0.1
        losses['breakdown']['humidity'] = {
            'loss_pct': round(humidity_loss, 1),
            'reason': f'Coastal humidity {humidity:.0f}% causing atmospheric haze',
        }
    
    # Standard system losses (always present)
    losses['breakdown']['inverter_conversion'] = {
        'loss_pct': 3.0,
        'reason': 'DC to AC conversion efficiency (97% inverter efficiency)',
    }
    
    losses['breakdown']['wiring_resistance'] = {
        'loss_pct': 2.0,
        'reason': 'Cable resistance and connection losses',
    }
    
    losses['breakdown']['soiling'] = {
        'loss_pct': 2.5,
        'reason': 'Dust and soiling on panel surface',
    }
    
    losses['breakdown']['mismatch'] = {
        'loss_pct': 1.5,
        'reason': 'Panel mismatch and non-optimal angle',
    }
    
    # Compute justified losses
    total_explained = sum(v['loss_pct'] for v in losses['breakdown'].values())
    losses['total_explained_loss_pct'] = round(total_explained, 1)
    losses['unexplained_pct'] = round(total_loss_pct - total_explained, 1)
    
    # Performance rating
    if efficiency_pct >= 90:
        rating = 'Excellent'
    elif efficiency_pct >= 80:
        rating = 'Good'
    elif efficiency_pct >= 70:
        rating = 'Fair'
    else:
        rating = 'Needs Investigation'
    
    losses['performance_rating'] = rating
    losses['efficiency_pct'] = round(efficiency_pct, 1)
    
    return losses


if __name__ == '__main__':
    # Test with today's data
    energy_log = json.load(open(ROOT / 'data' / 'energy_logs' / 'solar_energy_2026-02-16.json'))
    
    print("=" * 60)
    print("☁️  WEATHER & LOSS ANALYSIS")
    print("=" * 60)
    
    weather = get_weather_data(date='2026-02-16')
    print(f"\n📍 Location: {weather['location']}")
    print(f"📅 Date: {weather['date']}")
    print(f"🌡️  Temperature: {weather['temperature']['min']:.1f}°C - {weather['temperature']['max']:.1f}°C (avg daylight: {weather['temperature']['avg_daylight']:.1f}°C)")
    print(f"💧 Humidity: {weather['humidity_avg']:.0f}%")
    print(f"☁️  Cloud Cover: {weather['cloud_cover_avg']:.0f}%")
    print(f"🌤️  Sunshine Duration: {weather['sunshine_duration_hours']:.1f} hours")
    
    hourly = analyze_hourly_generation(energy_log)
    print(f"\n⚡ HOURLY GENERATION ANALYSIS")
    print(f"Peak Hour: {hourly['peak_hour']['hour']}:00")
    print(f"Peak Hourly Avg: {hourly['peak_hour']['avg_power_kw']} kW")
    print(f"Peak Hour Energy: {hourly['peak_hour']['energy_kwh']} kWh")
    
    daily_yield = energy_log['daily_summary']['total_yield_kwh']
    losses = analyze_losses(daily_yield, 2.32, weather)
    
    print(f"\n📊 LOSS ANALYSIS")
    print(f"Theoretical Max: {losses['theoretical_max_kwh']} kWh")
    print(f"Actual Yield: {losses['actual_kwh']} kWh")
    print(f"System Efficiency: {losses['efficiency_pct']}%")
    print(f"Total Losses: {losses['total_loss_pct']}%")
    print(f"\nLoss Breakdown:")
    for component, details in losses['breakdown'].items():
        print(f"  • {component}: {details['loss_pct']}% - {details['reason']}")
    print(f"\nPerformance Rating: {losses['performance_rating']}")
