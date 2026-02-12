#!/usr/bin/env python3
"""
Run all three Flask applications simultaneously
"""
import subprocess
import sys
import os
import signal
import time
from pathlib import Path

# Get the base directory
BASE_DIR = Path(__file__).parent

# Application configurations
APPS = [
    {
        'name': 'Product App (Azure SQL)',
        'path': BASE_DIR / 'product_app',
        'port': 5001,
        'color': '\033[94m'  # Blue
    },
    {
        'name': 'Order App (PostgreSQL)',
        'path': BASE_DIR / 'order_app',
        'port': 5002,
        'color': '\033[92m'  # Green
    },
    {
        'name': 'Logistics App (MongoDB)',
        'path': BASE_DIR / 'logistics_app',
        'port': 5003,
        'color': '\033[93m'  # Yellow
    }
]

RESET = '\033[0m'
processes = []


def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully shutdown all apps."""
    print("\n\nShutting down all applications...")
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    sys.exit(0)


def run_app(app_config):
    """Start a Flask application."""
    env = os.environ.copy()
    env['FLASK_APP'] = 'app.py'
    env['FLASK_ENV'] = 'development'
    
    proc = subprocess.Popen(
        [sys.executable, 'app.py'],
        cwd=str(app_config['path']),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True
    )
    
    return proc


def main():
    """Main function to start all applications."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("  Multi-DB Flask Demo - Starting All Applications")
    print("=" * 60)
    print()
    
    for app in APPS:
        print(f"{app['color']}Starting {app['name']} on port {app['port']}...{RESET}")
        proc = run_app(app)
        processes.append(proc)
        time.sleep(1)  # Give each app time to start
    
    print()
    print("=" * 60)
    print("  All applications started!")
    print("=" * 60)
    print()
    print("  Access the applications at:")
    for app in APPS:
        print(f"  {app['color']}• {app['name']}: http://localhost:{app['port']}{RESET}")
    print()
    print("  Press Ctrl+C to stop all applications")
    print("=" * 60)
    print()
    
    # Keep the script running and forward output
    try:
        while True:
            for i, proc in enumerate(processes):
                if proc.poll() is not None:
                    print(f"\n{APPS[i]['name']} has stopped unexpectedly!")
                
                # Read output without blocking
                try:
                    line = proc.stdout.readline()
                    if line:
                        print(f"{APPS[i]['color']}[{APPS[i]['name'][:10]}]{RESET} {line.strip()}")
                except:
                    pass
            
            time.sleep(0.1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == '__main__':
    main()
