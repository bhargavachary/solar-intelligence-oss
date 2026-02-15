#!/usr/bin/env python3
"""
Scraper API Server
==================
Lightweight HTTP API to trigger Waaree portal scraping on demand.
The dashboard calls this every 5 minutes to refresh data.

Usage:
    python3 scraper_api.py

Endpoints:
    POST /trigger_scrape - Start a scraping cycle (returns immediately)
    GET /status - Check last scrape status
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import sys
import os
import json
from datetime import datetime
import threading

app = Flask(__name__)
CORS(app)

# Global state
last_scrape = {
    "timestamp": None,
    "status": "idle",
    "pid": None,
    "message": "No scrapes yet"
}

VENV_PYTHON = "/Users/bhargav/Documents/GitHub/waaree_api_access/venv/bin/python3"
CRAWLER_SCRIPT = "/Users/bhargav/Documents/GitHub/waaree_api_access/waaree_deep_crawler.py"
LOCK_FILE = "/tmp/waaree_scraper.lock"


def run_scraper_background():
    """Run the crawler in background validation mode (1 fresh cycle, 0 reuse)"""
    global last_scrape
    
    # Check if already running
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, 'r') as f:
            old_pid = f.read().strip()
        try:
            # Check if process still alive
            os.kill(int(old_pid), 0)
            last_scrape["message"] = f"Scraper already running (PID {old_pid})"
            return
        except (OSError, ValueError):
            # Process dead, remove stale lock
            os.remove(LOCK_FILE)
    
    try:
        # Start crawler in background
        proc = subprocess.Popen(
            [VENV_PYTHON, CRAWLER_SCRIPT, '--validate', '--fresh-cycles', '1', '--reuse-cycles', '0'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(CRAWLER_SCRIPT)
        )
        
        # Write lock file
        with open(LOCK_FILE, 'w') as f:
            f.write(str(proc.pid))
        
        last_scrape.update({
            "timestamp": datetime.now().isoformat(),
            "status": "running",
            "pid": proc.pid,
            "message": f"Scraper started (PID {proc.pid})"
        })
        
        # Monitor completion in separate thread
        def monitor():
            proc.wait()
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
            last_scrape.update({
                "status": "completed" if proc.returncode == 0 else "failed",
                "message": f"Scrape finished with exit code {proc.returncode}"
            })
        
        threading.Thread(target=monitor, daemon=True).start()
        
    except Exception as e:
        last_scrape.update({
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "message": f"Failed to start scraper: {str(e)}"
        })


@app.route('/trigger_scrape', methods=['POST', 'GET'])
def trigger_scrape():
    """Trigger a scraping cycle (non-blocking)"""
    if last_scrape["status"] == "running":
        return jsonify({
            "success": False,
            "message": "Scraper already running",
            "last_scrape": last_scrape
        }), 409
    
    # Run in background thread so we can return immediately
    threading.Thread(target=run_scraper_background, daemon=True).start()
    
    return jsonify({
        "success": True,
        "message": "Scrape cycle initiated",
        "last_scrape": last_scrape
    })


@app.route('/status', methods=['GET'])
def status():
    """Get current scraper status and last run info"""
    # Read latest dashboard data timestamp
    try:
        with open('/Users/bhargav/Documents/GitHub/waaree_api_access/data/dashboard_data.json', 'r') as f:
            data = json.load(f)
            last_data_update = data.get('summary', {}).get('latest_timestamp')
    except:
        last_data_update = None
    
    return jsonify({
        "scraper": last_scrape,
        "last_data_update": last_data_update,
        "server_time": datetime.now().isoformat()
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "waaree-scraper-api"})


if __name__ == '__main__':
    print("=" * 60)
    print("Waaree Scraper API Server")
    print("=" * 60)
    print(f"Listening on: http://localhost:8006")
    print(f"Dashboard can call POST /trigger_scrape every 5 minutes")
    print(f"Status endpoint: GET /status")
    print("=" * 60)
    
    # Clean up stale lock on startup
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
    
    app.run(host='0.0.0.0', port=8006, debug=False, threaded=True)
