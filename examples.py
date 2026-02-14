#!/usr/bin/env python3
"""
Example script demonstrating how to use the SolarmanAPI client.

This script shows various usage patterns and best practices.
"""

import json
import logging
from solarman_api import SolarmanAPI, SolarmanAPIError

# Configure logging
logging.basicConfig(level=logging.INFO)

# Import configuration (in production, use environment variables or config file)
# For this example, we'll use hardcoded placeholders
APP_ID = "YOUR_APP_ID"
APP_SECRET = "YOUR_APP_SECRET"
EMAIL = "your.email@example.com"
PASSWORD = "your_password"


def example_basic_usage():
    """Example 1: Basic usage with manual session management."""
    print("\n" + "=" * 70)
    print("Example 1: Basic Usage")
    print("=" * 70)
    
    try:
        # Create API client
        api = SolarmanAPI(APP_ID, APP_SECRET, EMAIL, PASSWORD)
        
        # Login
        print("\n1. Logging in...")
        api.login()
        print("   ✓ Login successful")
        
        # Get stations
        print("\n2. Getting station list...")
        stations = api.get_station_list()
        print(f"   ✓ Found {len(stations)} station(s)")
        
        # Get real-time data for first station
        if stations:
            station_id = str(stations[0]['id'])
            print(f"\n3. Getting real-time data for station {station_id}...")
            data = api.get_realtime_data(station_id)
            print("   ✓ Data retrieved successfully")
            print(f"   Data keys: {list(data.keys())}")
        
        # Close session
        api.close()
        
    except SolarmanAPIError as e:
        print(f"❌ API Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_context_manager():
    """Example 2: Using context manager (recommended)."""
    print("\n" + "=" * 70)
    print("Example 2: Using Context Manager (Recommended)")
    print("=" * 70)
    
    try:
        with SolarmanAPI(APP_ID, APP_SECRET, EMAIL, PASSWORD) as api:
            # Login
            api.login()
            
            # Get all station data
            print("\nFetching data from all stations...")
            all_data = api.fetch_all_stations_data()
            
            print(f"✓ Retrieved data from {len(all_data)} station(s)")
            
            # Process the data
            for idx, station_data in enumerate(all_data, 1):
                station_info = station_data['station_info']
                print(f"\nStation {idx}:")
                print(f"  Name: {station_info.get('name')}")
                print(f"  ID: {station_info.get('id')}")
        
        # Session automatically closed
        
    except SolarmanAPIError as e:
        print(f"❌ API Error: {e}")


def example_error_handling():
    """Example 3: Demonstrating error handling."""
    print("\n" + "=" * 70)
    print("Example 3: Error Handling")
    print("=" * 70)
    
    try:
        # Attempt to create API with invalid credentials
        api = SolarmanAPI("invalid", "invalid", "test@test.com", "test")
        api.login()
        
    except SolarmanAPIError as e:
        print(f"✓ Caught expected error: {e}")
    except Exception as e:
        print(f"✓ Caught error: {e}")


def example_individual_station():
    """Example 4: Getting data for a specific station."""
    print("\n" + "=" * 70)
    print("Example 4: Specific Station Data")
    print("=" * 70)
    
    try:
        with SolarmanAPI(APP_ID, APP_SECRET, EMAIL, PASSWORD) as api:
            api.login()
            
            # Get stations
            stations = api.get_station_list()
            
            if not stations:
                print("No stations found")
                return
            
            # Select a specific station (first one in this example)
            target_station = stations[0]
            station_id = str(target_station['id'])
            
            print(f"\nTarget Station:")
            print(f"  ID: {station_id}")
            print(f"  Name: {target_station.get('name')}")
            print(f"  Location: {target_station.get('locationLat')}, {target_station.get('locationLng')}")
            
            # Get real-time data
            print(f"\nFetching real-time data...")
            realtime_data = api.get_realtime_data(station_id)
            
            # Pretty print the data
            print("\nReal-time Data:")
            print(json.dumps(realtime_data, indent=2))
        
    except SolarmanAPIError as e:
        print(f"❌ API Error: {e}")


def example_batch_processing():
    """Example 5: Batch processing multiple stations."""
    print("\n" + "=" * 70)
    print("Example 5: Batch Processing")
    print("=" * 70)
    
    try:
        with SolarmanAPI(APP_ID, APP_SECRET, EMAIL, PASSWORD) as api:
            api.login()
            
            # Get all stations
            stations = api.get_station_list()
            print(f"Found {len(stations)} station(s)")
            
            # Process each station
            results = []
            for station in stations:
                station_id = str(station['id'])
                station_name = station.get('name', 'Unknown')
                
                try:
                    print(f"\nProcessing: {station_name} (ID: {station_id})")
                    data = api.get_realtime_data(station_id)
                    
                    # Extract relevant metrics
                    result = {
                        'id': station_id,
                        'name': station_name,
                        'data': data,
                        'status': 'success'
                    }
                    results.append(result)
                    print(f"  ✓ Success")
                    
                except SolarmanAPIError as e:
                    print(f"  ❌ Failed: {e}")
                    results.append({
                        'id': station_id,
                        'name': station_name,
                        'error': str(e),
                        'status': 'failed'
                    })
            
            # Summary
            successful = sum(1 for r in results if r['status'] == 'success')
            print(f"\n{'=' * 70}")
            print(f"Batch Processing Complete:")
            print(f"  Total: {len(results)}")
            print(f"  Successful: {successful}")
            print(f"  Failed: {len(results) - successful}")
        
    except SolarmanAPIError as e:
        print(f"❌ API Error: {e}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("SOLARMAN API CLIENT - USAGE EXAMPLES")
    print("=" * 70)
    print("\nNote: Replace credentials in this file to run with real API")
    
    # Check if credentials are still placeholders
    if APP_ID == "YOUR_APP_ID":
        print("\n⚠️  WARNING: Using placeholder credentials")
        print("   Examples will not connect to real API")
        print("   Replace APP_ID, APP_SECRET, EMAIL, and PASSWORD with real values")
        
        # Demonstrate structure only
        print("\n" + "=" * 70)
        print("Code Structure Examples (No API Calls)")
        print("=" * 70)
        example_error_handling()
        return
    
    # Run all examples with real credentials
    example_basic_usage()
    example_context_manager()
    example_individual_station()
    example_batch_processing()


if __name__ == "__main__":
    main()
