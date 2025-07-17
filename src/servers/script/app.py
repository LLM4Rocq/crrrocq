import json

import yaml
from pytanque import Pytanque, State
from flask import Flask, request, jsonify

app = Flask(__name__)

with open('config/server/script/config.yaml', 'r') as file:
    config = yaml.safe_load(file)

with open('config/server/script/thm_filename.json', 'r') as file:
    thm_filename = json.load(file)

# Global index to balance load across pet servers
server_idx_counter = 0

# Initialize Pytanque instances for each server (assumed to run on ports 8765, 8766, ..., etc.)
pytanques = [Pytanque("127.0.0.1", config['pet_server_start_port'] + k) for k in range(config['num_pet_server'])]
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

        filepath = thm_filename[thm_name]

        worker = pytanques[login_idx]
        state = worker.start(file=filepath, thm=thm_name)
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config['port'])