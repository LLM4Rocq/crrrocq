import os
import requests
import json
from pathlib import Path

from utils import multi_shot_prompt

thm_map = {
    "homGrp_trans" : "../dataset/traced_mathcomp/presentation/term_2.json",
    "mk_invgK" : "../dataset/traced_mathcomp/fingroup/term_0.json",
    "mk_invMg" : "../dataset/traced_mathcomp/fingroup/term_1.json",
    "prodsgP" : "../dataset/traced_mathcomp/fingroup/term_80.json",
    "repr_classesP" : "../dataset/traced_mathcomp/fingroup/term_261.json",
    "comm_group_setP" : "../dataset/traced_mathcomp/fingroup/term_290.json",
    "rcosets_partition_mul" : "../dataset/traced_mathcomp/fingroup/term_322.json",
    "gen_expgs" : "../dataset/traced_mathcomp/fingroup/term_347.json",
    "gen_prodgP" : "../dataset/traced_mathcomp/fingroup/term_348.json",
    "cyclePmin"   : "../dataset/traced_mathcomp/fingroup/term_402.json",  
}

def generate_cot(thm):
    path = thm_map[thm]
    prompt = multi_shot_prompt(path)

    response = requests.post(
      url="https://openrouter.ai/api/v1/chat/completions",
      headers={
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
      },
      data=json.dumps({
        "model": "anthropic/claude-3.7-sonnet", # Optional
        "transforms": [],
        "messages": [
          {
            "role": "user",
            "content": prompt
          }
        ]
      })
    )

    output = Path(f"./cot_{thm}.json")
    with output.open('w') as output_file:
        print(response.json(), file=output_file)

for thm in thm_map:
    generate_cot(thm)
    print(f"Generated COT for {thm}")
