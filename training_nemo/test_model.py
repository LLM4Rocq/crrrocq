import json

from transformers import AutoTokenizer, AutoModelForCausalLM

with open('export/dataset/prompt.json') as file:
    content = json.load(file)

PROMPT_TEMPLATE = content['instruction']
initial_goal = """R  : idomainType
d, p, q  : {poly R}
dvd_dp  : d %| q
eq_pq  : p %= q
|-p %/ d %= q %/ d"""


prompt = PROMPT_TEMPLATE.format(initial_goal=initial_goal)
messages = [
    {"role": "system", "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."},
    {"role": "user", "content": prompt}
]

model_id = 'Qwen/Qwen2.5-Coder-32B-Instruct'
model_path = 'model/'
tokenizer = AutoTokenizer.from_pretrained(model_id)

text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    attn_implementation='flash_attention_2',
    torch_dtype="auto",
    device_map="auto")


input_ids = tokenizer(text, return_tensors="pt").to(model.device)

output_ids = model.generate(**input_ids, max_new_tokens=256, do_sample=True, temperature=0.6)
output_str = tokenizer.decode(output_ids[0])
print(output_str)
