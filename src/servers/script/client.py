from typing import Dict, Tuple, List

import requests

State = Dict[str, str]
Goals = List[Dict[str, str]]

class ClientError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


class PetClient:
    """
    A simple client API for interacting with the pet Flask server.
    """
    def __init__(self, base_url: str):
        """
        Initialize the client by setting the base URL, logging in, and fetching theorem descriptions.
        """
        self.base_url = base_url.rstrip("/")
        self.descr_thms = {}
        self.login = None
        self._login()

    def _login(self):
        """
        Log in to the server to retrieve a load-balanced server index.
        """
        url = f"{self.base_url}/login"
        response = requests.get(url)
        if response.status_code == 200:
            self.login = response.json()['idx']
        else:
            raise ClientError(response.status_code, response.text)

    def restart_server(self):
        """
        Restart pet server
        """
        url = f"{self.base_url}/restart"
        payload = {'login': self.login}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            pass
        else:
            raise ClientError(response.status_code, response.text)
    
    def start_thm(self, name: str) -> Tuple[State, Goals]:
        """
        Start a theorem proving session for the theorem at the given index.
        """
        url = f"{self.base_url}/start_thm"
        payload = {'login': self.login, 'name': name}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            output = response.json()
            return output['state'], output['goals']
        else:
            raise ClientError(response.status_code, response.text)

    def run_tac(self, state: State, tactic: str) -> Tuple[State, Goals]:
        """
        Execute a given tactic on the current proof state.
        """
        url = f"{self.base_url}/run_tac"
        payload = {'login': self.login, 'state': state, 'tactic': tactic}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            output = response.json()
            return output['state'], output['goals']
        else:
            raise ClientError(response.status_code, response.text)

if __name__ == '__main__':
    client = PetClient('http://127.0.0.1:5000')
    state, goals = client.start_thm('foo')
    print(goals)
    state, goals = client.run_tac(state, 'intros n.')
    print(goals)