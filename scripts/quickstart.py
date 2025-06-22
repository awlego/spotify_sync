#!/usr/bin/env python3
"""
Quick start script to help set up Spotify Sync Automated
"""

import os
import sys
import shutil
from pathlib import Path


def main():
    print("🎵 Spotify Sync Automated - Quick Start Setup 🎵\n")
    
    # Check for .env file
    if not os.path.exists('.env'):
        print("Creating .env file from template...")
        shutil.copy('.env.example', '.env')
        print("✅ .env file created")
        print("\n⚠️  Please edit .env and add your API credentials:")
        print("   - Spotify API: https://developer.spotify.com/dashboard")
        print("   - Last.fm API: https://www.last.fm/api/account/create")
        print("\nPress Enter when you've updated .env...")
        input()
    else:
        print("✅ .env file found")
    
    # Create necessary directories
    dirs = ['logs', 'backups', 'static', 'templates']
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
    print("✅ Directories created")
    
    # Check for existing CSV files to migrate
    csv_files = list(Path('..').glob('*.csv'))
    if csv_files:
        print(f"\n📊 Found {len(csv_files)} CSV files in parent directory:")
        for i, csv in enumerate(csv_files):
            print(f"   {i+1}. {csv.name}")
        
        choice = input("\nWould you like to import any of these? (y/n): ")
        if choice.lower() == 'y':
            try:
                idx = int(input("Enter the number of the file to import: ")) - 1
                if 0 <= idx < len(csv_files):
                    print(f"\nTo import {csv_files[idx].name}, run:")
                    print(f"python migrate_csv.py {csv_files[idx]}")
            except ValueError:
                pass
    
    print("\n🚀 Setup complete! To start the application, run:")
    print("   python run.py")
    print("\nThen open http://localhost:5000 in your browser")
    print("\nFor more options, run: python run.py --help")


if __name__ == '__main__':
    main()