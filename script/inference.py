import argparse
import os
from datetime import datetime
import json
import shutil
import concurrent.futures

from tqdm import tqdm
import yaml

from src.inference.agent import MathAgent, MathAgentError

def try_proof(agent_config, thm_name, export_dir, id):
    agent = MathAgent(agent_config)
    agent.start_thm(thm_name)
    try:
        agent.run_proof()
        filepath = os.path.join(export_dir, f'SUCCESS_{thm_name}_{id}.json')
        result = {"status": "success"}
    except MathAgentError as e:
        filepath = os.path.join(export_dir, f'FAIL_{thm_name}_{id}.json')
        result = {"status": "fail"}
    
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
        default="config/inference.yaml"
    )
    parser.add_argument(
        "--pass-k",
        type=int,
        default=4096
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=256
    )
    parser.add_argument(
        "--thms-file",
        type=str,
        default="export/benchmark/thm_names.json"
    )
    args = parser.parse_args()

    folder_path = os.path.join(args.log_dir, datetime.now() .strftime("logs_%m_%d_%H_%M_%S"))

    with open(args.config_file, 'r') as file:
        config = yaml.safe_load(file)
    with open(args.thms_file, 'r') as file:
        thm_names = yaml.safe_load(file)

    shutil.copyfile(args.config_file, os.path.join(folder_path, 'config.yaml'))
    
    futures = []
    for thm_name in tqdm(thm_names, desc="Theorems", position=0):
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            for i in range(args.pass_k):
                futures.append(executor.submit(try_proof, config, thm_name, folder_path, i))
        for _ in tqdm(concurrent.futures.as_completed(futures), desc="Pass@k", position=1, total=len(futures)):
            pass

if __name__ == "__main__":
    main()