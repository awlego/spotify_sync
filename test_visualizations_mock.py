#!/usr/bin/env python3
"""
Mock test for visualizations using Puppeteer
Since we can't start the service due to dependency issues,
this script will create mock HTML pages to test with Puppeteer
"""
import os
import time
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

# Create a simple mock server
class MockHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # Mock responses for each visualization
        pages = {
            '/': self.mock_home(),
            '/genre-galaxy': self.mock_genre_galaxy(),
            '/mood-spectrum': self.mock_mood_spectrum(),
            '/discovery-network': self.mock_discovery_network(),
            '/diversity-index': self.mock_diversity_index(),
            '/weather-correlation': self.mock_weather_correlation()
        }
        
        if self.path in pages:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(pages[self.path].encode())
        else:
            super().do_GET()
    
    def mock_home(self):
        return """
        <html>
        <head><title>Analytics Service Mock</title></head>
        <body style="background: #121212; color: white; font-family: Arial;">
            <h1 style="color: #1db954;">Analytics Service - Test Mode</h1>
            <h2>Visualizations:</h2>
            <ul>
                <li><a href="/genre-galaxy" style="color: #1db954;">Genre Galaxy Explorer</a></li>
                <li><a href="/mood-spectrum" style="color: #1db954;">Mood Spectrum Analyzer</a></li>
                <li><a href="/discovery-network" style="color: #1db954;">Discovery Network Graph</a></li>
                <li><a href="/diversity-index" style="color: #1db954;">Musical Diversity Index</a></li>
                <li><a href="/weather-correlation" style="color: #1db954;">Weather-Music Correlation</a></li>
            </ul>
        </body>
        </html>
        """
    
    def mock_genre_galaxy(self):
        return """
        <html>
        <head><title>Genre Galaxy Explorer</title></head>
        <body style="background: #121212; color: white; font-family: Arial;">
            <h1 style="color: #1db954;">Genre Galaxy Explorer 🌌</h1>
            <div style="background: #282828; padding: 20px; margin: 20px; border-radius: 8px;">
                <p>3D visualization of your genre landscape</p>
                <div style="width: 600px; height: 400px; background: #1a1a1a; display: flex; align-items: center; justify-content: center; color: #666;">
                    [3D Galaxy Visualization Would Be Here]
                </div>
                <div style="margin-top: 20px;">
                    <button style="background: #1db954; color: white; padding: 10px 20px; border: none; border-radius: 20px;">Rotate View</button>
                    <button style="background: #1db954; color: white; padding: 10px 20px; border: none; border-radius: 20px;">Zoom In</button>
                    <select style="background: #121212; color: white; padding: 8px;">
                        <option>Last Month</option>
                        <option>Last Year</option>
                        <option>All Time</option>
                    </select>
                </div>
            </div>
        </body>
        </html>
        """
    
    def mock_mood_spectrum(self):
        return """
        <html>
        <head><title>Mood Spectrum Analyzer</title></head>
        <body style="background: #121212; color: white; font-family: Arial;">
            <h1 style="color: #1db954;">Mood Spectrum Analyzer 🎭</h1>
            <div style="background: #282828; padding: 20px; margin: 20px; border-radius: 8px;">
                <p>Track the emotional journey of your music</p>
                <div style="width: 600px; height: 300px; background: #1a1a1a; display: flex; align-items: center; justify-content: center; color: #666;">
                    [Mood Timeline Chart Would Be Here]
                </div>
                <div style="margin-top: 20px;">
                    <h3>Current Mood: <span style="color: #1db954;">Energetic</span></h3>
                    <p>Recommendations: Try some upbeat pop or electronic music!</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def mock_discovery_network(self):
        return """
        <html>
        <head><title>Discovery Network Graph</title></head>
        <body style="background: #121212; color: white; font-family: Arial;">
            <h1 style="color: #1db954;">Discovery Network Graph 🕸️</h1>
            <div style="background: #282828; padding: 20px; margin: 20px; border-radius: 8px;">
                <p>Interactive network showing artist connections</p>
                <div style="width: 600px; height: 400px; background: #1a1a1a; display: flex; align-items: center; justify-content: center; color: #666;">
                    [Network Graph Would Be Here]
                </div>
                <div style="margin-top: 20px;">
                    <input type="text" placeholder="Search artists..." style="background: #121212; color: white; padding: 8px;">
                    <button style="background: #1db954; color: white; padding: 8px 16px; border: none;">Find Path</button>
                </div>
            </div>
        </body>
        </html>
        """
    
    def mock_diversity_index(self):
        return """
        <html>
        <head><title>Musical Diversity Index</title></head>
        <body style="background: #121212; color: white; font-family: Arial;">
            <h1 style="color: #1db954;">Musical Diversity Index 📊</h1>
            <div style="background: #282828; padding: 20px; margin: 20px; border-radius: 8px;">
                <h2>Diversity Score: <span style="color: #1db954; font-size: 48px;">73</span></h2>
                <p>Your music portfolio is well-diversified!</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
                    <div style="background: #1a1a1a; padding: 20px;">
                        <h3>Genre Distribution</h3>
                        <div style="color: #666;">[Donut Chart]</div>
                    </div>
                    <div style="background: #1a1a1a; padding: 20px;">
                        <h3>Risk/Return Analysis</h3>
                        <div style="color: #666;">[Scatter Plot]</div>
                    </div>
                </div>
                <button style="background: #1db954; color: white; padding: 10px 20px; border: none; border-radius: 20px; margin-top: 20px;">Export Report</button>
            </div>
        </body>
        </html>
        """
    
    def mock_weather_correlation(self):
        return """
        <html>
        <head><title>Weather-Music Correlation</title></head>
        <body style="background: #121212; color: white; font-family: Arial;">
            <h1 style="color: #1db954;">Weather-Music Correlation 🌤️</h1>
            <div style="background: #282828; padding: 20px; margin: 20px; border-radius: 8px;">
                <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #FFD700, #FFA500);">
                    <h2 style="font-size: 72px;">☀️</h2>
                    <h2>Clear - 22°C</h2>
                    <p>Perfect weather for upbeat music!</p>
                </div>
                <div style="margin-top: 20px;">
                    <h3>Music Recommendations:</h3>
                    <ul>
                        <li>Try some happy music - it's popular in clear weather</li>
                        <li>High-energy tracks work well in this weather</li>
                        <li>Recently played in similar weather: Summer Vibes playlist</li>
                    </ul>
                </div>
                <div style="margin-top: 20px;">
                    <button style="background: #1db954; color: white; padding: 10px 20px; border: none; border-radius: 20px;">Refresh Predictions</button>
                </div>
            </div>
        </body>
        </html>
        """
    
    def log_message(self, format, *args):
        # Suppress logs
        pass

def start_mock_server():
    server = HTTPServer(('localhost', 5002), MockHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server

if __name__ == "__main__":
    print("Starting mock server on http://localhost:5002")
    server = start_mock_server()
    
    # Give server time to start
    time.sleep(2)
    
    print("Mock server is running. Press Ctrl+C to stop.")
    
    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down mock server...")
        server.shutdown()