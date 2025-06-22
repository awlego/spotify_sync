#!/usr/bin/env python3
"""
Setup script for Spotify Sync project
"""

import os
import sys
import shutil
from pathlib import Path


def setup_project():
    """Set up the Spotify Sync project structure"""
    print("Setting up Spotify Sync project...")
    
    # Create necessary directories
    directories = [
        "data/csv",
        "data/cache",
        "data/db",
        "logs",
        "scripts",
        "notebooks"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {directory}")
    
    # Check for .env file
    if not Path(".env").exists():
        if Path(".env.example").exists():
            print("\n⚠️  No .env file found. Please copy .env.example to .env and update with your credentials.")
        else:
            print("\n⚠️  No .env file found. Please create one with your API credentials.")
    else:
        print("\n✓ .env file found")
    
    # Check Python version
    python_version = sys.version_info
    if python_version.major == 3 and python_version.minor >= 10:
        print(f"✓ Python {python_version.major}.{python_version.minor} detected")
    else:
        print(f"⚠️  Python {python_version.major}.{python_version.minor} detected. Python 3.10+ recommended")
    
    print("\n📋 Next steps:")
    print("1. Create/update your .env file with API credentials")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Run the automated system: cd spotify_sync_automated && python run.py")
    print("4. Access the web dashboard at http://localhost:5001")


if __name__ == "__main__":
    setup_project()