#!/usr/bin/env python3
"""Test wrapped service endpoints"""
import requests
import json

BASE_URL = "http://127.0.0.1:5002"

def test_endpoint(name, url):
    """Test a single endpoint"""
    print(f"\nTesting {name}: {url}")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success - Response keys: {list(data.keys())}")
            return True
        else:
            print(f"✗ Failed - Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Test all visualization endpoints"""
    print("Testing Wrapped Service Endpoints")
    print("=" * 50)
    
    endpoints = [
        ("Analytics Data", f"{BASE_URL}/api/analytics/data/2025"),
        ("Calendar Visualization", f"{BASE_URL}/api/visualizations/calendar/2025"),
        ("Listening Clock", f"{BASE_URL}/api/visualizations/listening-clock"),
        ("Weekly Patterns", f"{BASE_URL}/api/visualizations/weekly-patterns"),
        ("Artist Trends", f"{BASE_URL}/api/visualizations/artist-trends"),
        ("Music Hierarchy", f"{BASE_URL}/api/visualizations/music-hierarchy"),
        ("Timeline", f"{BASE_URL}/api/visualizations/timeline"),
        ("Wrapped Data", f"{BASE_URL}/api/wrapped/2025"),
    ]
    
    success_count = 0
    for name, url in endpoints:
        if test_endpoint(name, url):
            success_count += 1
    
    print(f"\n\nSummary: {success_count}/{len(endpoints)} endpoints working")
    
    # Test the explore page
    print(f"\n\nExplore page available at: {BASE_URL}/explore")
    print(f"Wrapped page available at: {BASE_URL}/")

if __name__ == "__main__":
    main()