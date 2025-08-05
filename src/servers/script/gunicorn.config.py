# gunicorn_config.py
import subprocess
import yaml
import time
import os
import json

# keep references to the Popen objects
pet_servers = []
num_desired = 2
monitor_thread = None
port_offset = 0  # Track port offset for restarts

def start_pet_servers():
    """Spawn new pet-server processes."""
    global pet_servers, port_offset
    with open('config/server/script/config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    
    current_ports = []
    for k in range(config['num_pet_server']):
        # Calculate port with offset, cycling every 50
        port = config['pet_server_start_port'] + ((k + port_offset * config['num_pet_server']) % 50)
        current_ports.append(port)
        p = subprocess.Popen(['pet-server', '-p', str(port)])
        pet_servers.append(p)
    
    # Write current ports to file for workers

    ports_file = os.environ.get('PET_PORTS_PATH', 'pet_ports.txt')
    with open(ports_file, 'w') as f:
        f.write(json.dumps({
            'ports': current_ports,
            'base_port': config['pet_server_start_port'],
            'timestamp': time.time()
        }))
    
    port_offset += 1
    print(f"[arbiter] Started pet-servers on ports {current_ports}: {[p.pid for p in pet_servers]}")

def stop_pet_servers():
    """Terminate all currently tracked pet-servers."""
    global pet_servers
    for p in pet_servers:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
                p.wait(timeout=2)
            except Exception:
                pass
    pet_servers = []
    
    print("[arbiter] Stopped all pet-servers")

def restart_pet_servers():
    """Helper to stop & then start fresh."""
    print("[arbiter] Restarting pet-servers…")
    stop_pet_servers()
    start_pet_servers()

def monitor_restart_file():
    """Monitor lock file for restart signals"""
    import json
    restart_file = os.environ.get('PET_RESTART_PATH', 'pet_restart.txt')
    print(f"[arbiter] Monitoring {restart_file} for restart signals")
    last_mtime = 0
    while True:
        try:
            if os.path.exists(restart_file):
                stat = os.stat(restart_file)
                if stat.st_mtime > last_mtime:
                    last_mtime = stat.st_mtime
                    print("[arbiter] Restart signal detected - restarting pet servers...")
                    restart_pet_servers()
            time.sleep(0.5)
        except Exception as e:
            print(f"[arbiter] Error monitoring restart file: {e}")
            time.sleep(1)

def on_starting(server):
    start_pet_servers()
    # Start monitoring thread
    import threading
    monitor_thread = threading.Thread(target=monitor_restart_file, daemon=True)
    monitor_thread.start()

def on_exit(server):
    # clean up when Gunicorn shuts down
    stop_pet_servers()
