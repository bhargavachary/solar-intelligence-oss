#!/usr/bin/env python3
"""Dump all available data from Waaree API"""

from waaree_api_client import WaareeAPIClient
import json
from datetime import datetime

client = WaareeAPIClient('bhargavachary', 'R@m131091', token_file='.waaree_token.json')
client.login()

print("=" * 80)
print("WAAREE SOLAR API - COMPLETE DATA DUMP")
print("=" * 80)
print()

# 1. User Info
print("1. USER INFORMATION")
print("-" * 80)
user_info = client.get_user_info()
print(json.dumps(user_info, indent=2))
print()

# 2. API Quota
print("2. API QUOTA & RATE LIMITS")
print("-" * 80)
quota = client.get_api_quota()
print(json.dumps(quota, indent=2))
print()

# 3. Plants
print("3. PLANTS (Solar Installation)")
print("-" * 80)
plants = client.get_plants()
print(json.dumps(plants, indent=2))
station_id = plants[0]['stationID'] if plants else None
print()

# 4. Devices
print("4. DEVICES (Inverters/Controllers)")
print("-" * 80)
devices = client.get_devices()
print(json.dumps(devices, indent=2))
print()

# 5. Modules
print("5. MODULES (Communication Modules)")
print("-" * 80)
modules = client.get_modules()
print(json.dumps(modules, indent=2))
print()

# 6. Plant Devices
if station_id:
    print("6. PLANT DEVICE LIST")
    print("-" * 80)
    plant_devices = client.get_plant_devices(station_id)
    print(json.dumps(plant_devices, indent=2))
    print()

# 7. Hourly Generation
if station_id:
    print("7. TODAY'S HOURLY GENERATION")
    print("-" * 80)
    hourly = client.get_hourly_generation(station_id)
    print(json.dumps(hourly, indent=2, default=str))
    print()

# 8. Daily Generation
if station_id:
    now = datetime.now()
    print(f"8. DAILY GENERATION - {now.strftime('%B %Y')}")
    print("-" * 80)
    daily = client.get_daily_generation(station_id, now.year, now.month)
    print(json.dumps(daily, indent=2))
    print()

# 9. Monthly Generation
if station_id:
    print(f"9. MONTHLY GENERATION - {now.year}")
    print("-" * 80)
    monthly = client.get_monthly_generation(station_id, now.year)
    print(json.dumps(monthly, indent=2))
    print()

# 10. Dashboard Summary
print("10. DASHBOARD DATA (COMBINED)")
print("-" * 80)
dashboard = client.get_dashboard_data()
print(json.dumps(dashboard, indent=2, default=str))
