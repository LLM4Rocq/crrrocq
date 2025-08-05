import json

import yaml
from pytanque import Pytanque, State
from flask import Flask, request, jsonify
import os
import time
import threading

app = Flask(__name__)

with open('config/server/script/config.yaml', 'r') as file:
    config = yaml.safe_load(file)

with open(config['thm_paths'], 'r') as file:
    thm_filename = json.load(file)

# Global index to balance load across pet servers
server_idx_counter = 0


def get_current_ports():
    """Get current pet server ports from file"""
    ports_file = os.environ.get('PET_PORTS_PATH', 'pet_ports.txt')
    try:
        with open(ports_file, 'r') as f:
            port_data = json.loads(f.read())
            return port_data['ports']
    except:
        # Fallback to default ports
        return [config['pet_server_start_port'] + k for k in range(config['num_pet_server'])]

def create_pytanques():
    """Create Pytanque instances with current ports"""
    ports = get_current_ports()
    return [Pytanque("127.0.0.1", port) for port in ports]

# Initialize Pytanque instances for each server
pytanques = create_pytanques()
for pet in pytanques:
    pet.connect()

pet_loaded = True

@app.route('/health', methods=['GET'])
def health():
    if pet_loaded:
        return "OK", 200
    else:
        return "Pet servers not ready", 500

@app.route('/login', methods=['GET'])
def login():
    """
    Return a server index (integer in 0 .. NUM_PET_SERVER-1) to help balance the load across pet servers.

    Returns:
            - status_code
            - output: the assigned server index
    """
    global server_idx_counter
    try:
        assigned_idx = server_idx_counter
        server_idx_counter = (server_idx_counter + 1) % config['num_pet_server']
        return jsonify({"idx": assigned_idx}), 200
    except Exception as e:
        return str(e), 500

@app.route('/restart', methods=['POST'])
def restart():
    """
    Restart the pet-servers and reconnect the sockets of all workers.
    """
    print("[restart] Restarting pet-servers via file coordination...")
    global pytanques
    for pet in pytanques:
        pet.close()
    
    # Signal both arbiter and workers to restart
    lock_file = os.environ.get('PET_LOCK_PATH', 'pet_lock.txt')
    with open(lock_file, 'w') as f:
        f.write(json.dumps({
            'sender': os.getpid(),
            'timestamp': time.time(),
            'message': 'restart_pet_servers'
        }))
        
    time.sleep(3)  # Wait for port file to be updated
    
    # Recreate Pytanque instances with new ports
    pytanques = create_pytanques()
    
    # Connect to new pet servers
    for pet in pytanques:
        try:
            pet.connect()
        except Exception as e:
            print(f"[restart] Failed to connect: {e}")

    return jsonify(status="pet-servers restarting"), 200

@app.route('/start_thm', methods=['POST'])
def start_thm():
    """
    Start a theorem by selecting a theorem based on its index.

    Expects:
        - idx (int): the index of the theorem in the description file.
        - login (int): the server index assigned from /login.

    Returns:
            - status_code
            - output: A dictionary containing:
                - state: The initial proof state (in JSON format)
                - goals: A list of pretty-printed goals
    """
    try:
        data = request.get_json()
        thm_name = data['name']
        login_idx = data['login']

        entry = thm_filename[thm_name]
        filepath, line, character = entry['filepath'], entry['position']['line'], entry['position']['character']
        worker = pytanques[login_idx]
        state = worker.get_state_at_pos(filepath, line, character, 0)
        goals = worker.goals(state)
        goals_json = [goal.to_json() for goal in goals]
        output = {"state": state.to_json(), "goals": goals_json}
        return jsonify(output), 200
    except Exception as e:
        return str(e), 500

@app.route('/run_tac', methods=['POST'])
def run_tac():
    """
    Execute a given tactic on the current proof state.

    Expects:
        - state: the current proof state.
        - tactic: the tactic command to execute.
        - login: the server index assigned from /login.

    Returns:
            - status_code
            - output:
                - state: new proof state
                - goals: goals
    """
    try:
        data = request.get_json()
        current_state = State.from_json(data['state'])
        tactic = data['tactic']
        login_idx = data['login']

        worker = pytanques[login_idx]
        new_state = worker.run(current_state, tactic, verbose=False, timeout=10)
        goals = worker.goals(new_state)
        goals_json = [goal.to_json() for goal in goals]
        output = {"state": new_state.to_json(), "goals": goals_json}
        return jsonify(output), 200
    except Exception as e:
        return str(e), 500
    
def start_reconnect_listener():
    """Listen for reconnect messages from other workers via file"""
    def listener():
        current_pid = os.getpid()
        lock_file = os.environ.get('PET_LOCK_PATH', 'pet_lock.txt')
        print(f"Worker {current_pid}: Monitoring {lock_file} for reconnect messages")
        last_mtime = 0
        
        while True:
            try:
                if os.path.exists(lock_file):
                    stat = os.stat(lock_file)
                    if stat.st_mtime > last_mtime:
                        last_mtime = stat.st_mtime
                        with open(lock_file, 'r') as f:
                            data = json.loads(f.read())
                            sender = data.get('sender')                            
                            # Only react if message is from another worker
                            if sender != current_pid:
                                print(f"Worker {current_pid}: Received restart message from worker {sender}")
                                global pytanques
                                for pet in pytanques:
                                    pet.close()
                                time.sleep(5)  # Brief wait before reconnecting
                                pytanques = create_pytanques()
                                for pet in pytanques:
                                    try:
                                        pet.connect()
                                    except Exception as e:
                                        print(f"Worker {current_pid}: Failed to reconnect: {e}")
                time.sleep(1)  # Check every second
            except Exception as e:
                print(f"Worker {current_pid}: Error handling reconnect message: {e}")
                time.sleep(1)
    # Start listener thread
    thread = threading.Thread(target=listener, daemon=True)
    thread.start()

# Start reconnect listener for all workers (including gunicorn workers)
start_reconnect_listener()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config['port'])