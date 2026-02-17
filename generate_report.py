#!/usr/bin/env python3
"""
Solar Energy System Report Generator
Generates comprehensive report from API data and updates energy logs
"""

import json
import os
from datetime import datetime, timedelta
from waaree_api_client import WaareeAPIClient

def generate_report():
    """Generate comprehensive solar system report"""
    
    client = WaareeAPIClient('bhargavachary', 'R@m131091', token_file='.waaree_token.json')
    client.login()
    
    # Fetch all data
    user = client.get_user_info()
    quota = client.get_api_quota()
    plants = client.get_plants()
    devices = client.get_devices()
    modules = client.get_modules()
    
    plant = plants[0] if plants else {}
    device = devices[0] if devices else {}
    module = modules[0] if modules else {}
    station_id = plant.get('stationID', '')
    
    # Get historical data
    now = datetime.now()
    hourly = client.get_hourly_generation(station_id) if station_id else {}
    daily = client.get_daily_generation(station_id, now.year, now.month) if station_id else []
    monthly = client.get_monthly_generation(station_id, now.year) if station_id else []
    
    # Build report
    report = {
        "report_generated": now.isoformat(),
        "report_period": f"{now.strftime('%B %d, %Y')}",
        
        "system_overview": {
            "plant_name": plant.get('name', 'N/A').strip(),
            "location": f"{plant.get('city', 'N/A')}, {plant.get('address', 'N/A')}",
            "capacity_kw": plant.get('systemCapacity', 0),
            "installation_date": plant.get('createdDate', 'N/A'),
            "status": "Online" if device.get('status') == 1 else "Offline",
            "owner": f"{user.get('name', 'N/A')}",
            "owner_email": user.get('email', 'N/A'),
            "owner_phone": user.get('phone', 'N/A'),
        },
        
        "hardware_details": {
            "inverter_sn": device.get('deviceSN', 'N/A'),
            "inverter_id": device.get('deviceID', 'N/A'),
            "inverter_type": device.get('deviceType', 'N/A'),
            "inverter_model": device.get('productType', 'N/A'),
            "communication_module_sn": device.get('moduleSN', 'N/A'),
            "communication_module_type": module.get('moduleType', 'N/A'),
            "module_firmware": module.get('version', 'N/A'),
            "module_signal": f"{module.get('signal', 0)}/4 bars",
            "pv_string_count": plant.get('quantity', 1),
            "battery_enabled": device.get('hasBattery', False),
            "wifi_meter": device.get('hasWifiMeter', False),
        },
        
        "live_status": {
            "current_power_kw": round(device.get('power', 0), 3),
            "today_generation_kwh": round(device.get('generationToday', 0), 2),
            "total_generation_kwh": round(device.get('generationTotal', 0), 2),
            "last_data_update": device.get('dataLatestUploadDate', 'N/A'),
            "feed_in_date": device.get('feedinDate', 'N/A'),
        },
        
        "daily_performance": {
            "date": now.strftime('%Y-%m-%d'),
            "total_kwh": round(device.get('generationToday', 0), 2),
            "peak_power_kw": round(device.get('power', 0), 3),
            "hourly_breakdown": [
                {"hour": h, "kwh": round(v, 2)} 
                for h, v in hourly.get('generation', [])
            ],
            "hours_active": len(hourly.get('generation', [])),
        },
        
        "monthly_performance": {
            "year_month": now.strftime('%B %Y'),
            "total_kwh": round(sum(v for _, v in daily), 2),
            "days_active": len(daily),
            "daily_average_kwh": round(sum(v for _, v in daily) / max(len(daily), 1), 2),
            "best_day": max(daily, key=lambda x: x[1])[1] if daily else 0,
            "best_day_date": f"Feb {max(daily, key=lambda x: x[1])[0]}" if daily else "N/A",
            "daily_breakdown": [
                {"day": f"Feb {d}", "kwh": round(v, 2)}
                for d, v in daily
            ],
        },
        
        "yearly_performance": {
            "year": now.year,
            "total_kwh": round(sum(v for _, v in monthly), 2),
            "months_active": len(monthly),
            "monthly_breakdown": [
                {"month": ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m],
                 "kwh": round(v, 2)}
                for m, v in monthly
            ],
        },
        
        "efficiency_metrics": {
            "capacity_utilization": f"{round((device.get('power', 0) / plant.get('systemCapacity', 1)) * 100, 1)}%",
            "daily_performance_ratio": f"{round((device.get('generationToday', 0) / (plant.get('systemCapacity', 1) * 5)) * 100, 1)}%",
            "system_days_operating": (datetime.fromisoformat(plant.get('createdDate', now.isoformat()).split()[0]) - datetime.now()).days * -1,
        },
        
        "api_information": {
            "api_key_status": "Valid",
            "daily_quota": int(quota.get('total', 0)),
            "calls_remaining": int(quota.get('remaining', 0)),
            "usage_today": int(quota.get('total', 0)) - int(quota.get('remaining', 0)),
        },
    }
    
    return report, device, daily, hourly

def update_energy_logs(device, daily, hourly):
    """Update energy log files with latest data"""
    
    now = datetime.now()
    logs_dir = 'data/energy_logs'
    os.makedirs(logs_dir, exist_ok=True)
    
    # Update today's log
    today_file = os.path.join(logs_dir, f'solar_energy_{now.strftime("%Y-%m-%d")}.json')
    
    today_data = {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        "device_sn": device.get('deviceSN'),
        "plant_name": device.get('plantName').strip(),
        "current_power_kw": round(device.get('power', 0), 3),
        "daily_yield_kwh": round(device.get('generationToday', 0), 2),
        "total_yield_kwh": round(device.get('generationTotal', 0), 2),
        "status": "Online" if device.get('status') == 1 else "Offline",
        "last_update": device.get('dataLatestUploadDate'),
        "hourly_generation": {
            "hours": [h for h, _ in hourly.get('generation', [])],
            "values_kwh": [round(v, 2) for _, v in hourly.get('generation', [])],
        },
    }
    
    with open(today_file, 'w') as f:
        json.dump(today_data, f, indent=2)
    
    return today_file

def main():
    print("=" * 80)
    print("SOLAR ENERGY SYSTEM REPORT")
    print("=" * 80)
    print()
    
    # Generate report
    report, device, daily, hourly = generate_report()
    
    # Print report to console
    print(f"Report Generated: {report['report_generated']}")
    print(f"Period: {report['report_period']}")
    print()
    
    print("SYSTEM OVERVIEW")
    print("-" * 80)
    for key, value in report['system_overview'].items():
        print(f"  {key:25s} : {value}")
    print()
    
    print("HARDWARE DETAILS")
    print("-" * 80)
    for key, value in report['hardware_details'].items():
        print(f"  {key:25s} : {value}")
    print()
    
    print("LIVE STATUS")
    print("-" * 80)
    for key, value in report['live_status'].items():
        print(f"  {key:25s} : {value}")
    print()
    
    print("TODAY'S PERFORMANCE")
    print("-" * 80)
    perf = report['daily_performance']
    print(f"  Date                      : {perf['date']}")
    print(f"  Total Generation          : {perf['total_kwh']} kWh")
    print(f"  Peak Power                : {perf['peak_power_kw']} kW")
    print(f"  Hours Active              : {perf['hours_active']}")
    print()
    print("  Hourly Breakdown:")
    for hour_data in perf['hourly_breakdown']:
        bar = "█" * int(hour_data['kwh'] * 10)
        print(f"    {hour_data['hour']:2d}:00  {hour_data['kwh']:5.2f} kWh  {bar}")
    print()
    
    print("THIS MONTH'S PERFORMANCE")
    print("-" * 80)
    monthly = report['monthly_performance']
    print(f"  Period                    : {monthly['year_month']}")
    print(f"  Total Generation          : {monthly['total_kwh']} kWh")
    print(f"  Days Active               : {monthly['days_active']}")
    print(f"  Daily Average             : {monthly['daily_average_kwh']} kWh")
    print(f"  Best Day                  : {monthly['best_day']} kWh ({monthly['best_day_date']})")
    print()
    print("  Daily Breakdown:")
    for day_data in monthly['daily_breakdown']:
        bar = "█" * int(day_data['kwh'])
        print(f"    {day_data['day']:8s}  {day_data['kwh']:6.2f} kWh  {bar}")
    print()
    
    print("THIS YEAR'S PERFORMANCE")
    print("-" * 80)
    yearly = report['yearly_performance']
    print(f"  Year                      : {yearly['year']}")
    print(f"  Total Generation          : {yearly['total_kwh']} kWh")
    print(f"  Months Active             : {yearly['months_active']}")
    print()
    print("  Monthly Breakdown:")
    for month_data in yearly['monthly_breakdown']:
        bar = "█" * int(month_data['kwh'] / 5)
        print(f"    {month_data['month']:3s}  {month_data['kwh']:7.2f} kWh  {bar}")
    print()
    
    print("EFFICIENCY METRICS")
    print("-" * 80)
    for key, value in report['efficiency_metrics'].items():
        print(f"  {key:25s} : {value}")
    print()
    
    print("API INFORMATION")
    print("-" * 80)
    for key, value in report['api_information'].items():
        print(f"  {key:25s} : {value}")
    print()
    
    # Update logs
    today_file = update_energy_logs(device, daily, hourly)
    print("=" * 80)
    print(f"✓ Energy log updated: {today_file}")
    print("=" * 80)
    
    # Save report as JSON
    report_file = f'reports/solar_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    os.makedirs('reports', exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"✓ Report saved: {report_file}")
    print()

if __name__ == "__main__":
    main()
