import argparse
import os
from datetime import datetime
import json
import shutil
import concurrent.futures

from tqdm import tqdm
import yaml

from src.servers.script.client import PetClient
from src.inference.agent_compress import MathAgentCompress
from src.inference.agent import MathAgentError

def try_proof(agent_config, thm_name, export_dir, id):
    agent = MathAgentCompress(agent_config)
    try:
        agent.start_thm(thm_name)
        agent.run_proof()
        filepath = os.path.join(export_dir, f'SUCCESS_{thm_name}_{id}.json')
        result = {"status": "success"}
    except Exception as e:
        filepath = os.path.join(export_dir, f'FAIL_{thm_name}_{id}.json')
        result = {"status": "fail", "message": str(e)}
    
    result = agent.export_result() | result
    with open(filepath, 'w') as file:
        json.dump(result, file, indent=4)
    
def main():
    """Main entry point for the inference CLI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Coq Proof Assistant CLI")
    parser.add_argument(
        "--config-file",
        type=str,
        default="config/inference/inference.yaml"
    )
    parser.add_argument(
        "--pass-k",
        type=int,
        default=64
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=64
    )
    parser.add_argument(
        "--evaluation-file",
        type=str,
        default="/lustre/fsn1/projects/rech/tdm/commun/dataset/new_evaluation.json"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="agent_logs"
    )
    args = parser.parse_args()

    folder_path = os.path.join(args.log_dir, datetime.now() .strftime("logs_%m_%d_%H_%M_%S"))
    os.makedirs(folder_path, exist_ok=True)
    with open(args.config_file, 'r') as file:
        config = yaml.safe_load(file)
    
    with open(os.environ['MODEL_IP_PATH'], 'r') as file:
        model_ip = file.read().strip()
    with open(os.environ['RETRIEVAL_IP_PATH'], 'r') as file:
        retrieval_ip = file.read().strip()
    with open(os.environ['PET_IP_PATH'], 'r') as file:
        pet_ip = file.read().strip()

    config['llm_config']['base_url'] = f"http://{model_ip}/v1"
    config['tools']['search']['base_url'] = f"http://{retrieval_ip}"
    config['tools']['script']['base_url'] = f"http://{pet_ip}"

    with open(args.evaluation_file, 'r') as file:
        thm_names = json.load(file)

    shutil.copyfile(args.config_file, os.path.join(folder_path, 'config.yaml'))

    # pet client, only needed to restart server
    pet_client = PetClient(pet_ip)
    futures = []
    for thm_name in tqdm(thm_names, desc="Theorems", position=0):
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            for i in range(args.pass_k):
                futures.append(executor.submit(try_proof, config, thm_name, folder_path, i))
        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Pass@k", position=1, total=len(futures)):
            pass
        pet_client.restart_server()
if __name__ == "__main__":
    main()