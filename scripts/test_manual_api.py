#!/usr/bin/env python3
"""
Manual test to verify the API returns proper error messages
"""

import requests
import json

# Start the web app first: python src/run.py

def test_playlist_update():
    """Test updating playlists via API"""
    base_url = "http://localhost:5001"
    
    playlist_types = ['most_listened', 'recent_favorites', 'binged_songs']
    
    for playlist_type in playlist_types:
        print(f"\nTesting {playlist_type} playlist update...")
        
        try:
            response = requests.post(f"{base_url}/api/playlists/update/{playlist_type}")
            data = response.json()
            
            print(f"Status code: {response.status_code}")
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if not data.get('success'):
                error_msg = data.get('error', 'undefined')
                print(f"Error message: {error_msg}")
                
                # Check if error is meaningful
                if error_msg == 'undefined' or not error_msg:
                    print("❌ ERROR: No meaningful error message!")
                else:
                    print("✅ Good: Error message is present and meaningful")
            else:
                print("✅ Playlist updated successfully")
                
        except requests.exceptions.ConnectionError:
            print("❌ Could not connect to server. Make sure the app is running.")
            print("Start it with: python src/run.py")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Testing API error responses...")
    print("Make sure the web app is running first!")
    test_playlist_update()