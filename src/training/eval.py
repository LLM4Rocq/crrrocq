import subprocess
import time
import signal
import random


def start_pet_server(port=8765, mean_wait=10):
    """
    Starts the pet-server process and returns the process handle.
    """
    process = subprocess.Popen(["pet-server", "--port", f"{port}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # wait a bit to ensure the server is fully up before proceeding
    wait = random.randint(1, 2*mean_wait)
    time.sleep(wait)
    return process

def stop_pet_server(process):
    """
    Gracefully stops the pet-server process.
    """
    process.terminate()  # Sends SIGTERM
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()  # Force kill if not terminated
        process.wait()

# Define a custom exception for timeouts
class TimeoutError(Exception):
    pass

def timeout(seconds=5, error_message="Function call timed out"):
    """
    A decorator that raises a TimeoutError if the decorated function
    does not return within 'seconds' seconds.
    """
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)
        def wrapper(*args, **kwargs):
            # Set the signal handler and a timeout alarm
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                # Cancel the alarm
                signal.alarm(0)
            return result
        return wrapper
    return decorator
