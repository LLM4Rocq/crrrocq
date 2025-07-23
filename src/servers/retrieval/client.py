from typing import Dict, Tuple, List

import requests


class ClientError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


class RetrievalClient:
    """
    A simple client to retrieve docstrings from flask server.
    """
    def __init__(self, base_url: str):
        """
        Initialize the client by setting the base URL.
        """
        self.base_url = base_url.rstrip("/")

    def query(self, query:str, top_k:int=10, source=""):
        """
        Retrieve top_k docstrings given the query.
        """
        url = f"{self.base_url}/query"
        payload = {'query': query, "top_k": top_k, "source": source}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            output = response.json()
            return output
        else:
            raise ClientError(response.status_code, response.text)

if __name__ == '__main__':
    client = RetrievalClient('http://127.0.0.1:5000')
    result = client.query("test")
    print(result)