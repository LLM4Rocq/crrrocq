import os
import json
import gc
import argparse

import torch
from accelerate import Accelerator
from datasets import load_dataset
from tqdm.auto import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM
from torch.utils.tensorboard import SummaryWriter
from transformers.optimization import get_cosine_schedule_with_warmup

from training.dataset import load_and_process, merge_and_pad_entries

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=str, default='dataset/')
    parser.add_argument("--export", type=str, default='ckpt/')
    parser.add_argument("--prompt-path", type=str, default='training/prompts/prompt.json')
    parser.add_argument("--model-name", type=str, default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--lr", type=float, default=1e-05, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--num-epochs", type=int, default=5)
    parser.add_argument("--empty-cache", type=bool, default=False)
    parser.add_argument("--num-workers", type=int, default=4, help="Number of workers to process dataset")
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--adam-beta1", type=float, default=0.9)
    parser.add_argument("--adam-beta2", type=float, default=0.95)
    parser.add_argument("--lr-warmup-ratio", type=float, default=0.05)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--log-dir", type=str)
    args = parser.parse_args()
    return args

args = parse_args()
accelerator = Accelerator()

writer = None
if accelerator.is_main_process:
    writer = SummaryWriter(log_dir=args.log_dir)

torch.manual_seed(53)
torch.cuda.manual_seed(53)


def train_loop(model, tokenizer, train_dataloader, optimizer, scheduler, args):
    model.train()
    loop = tqdm(total=int(len(train_dataloader)*args.num_epochs/args.gradient_accumulation_steps), disable=not accelerator.is_main_process)
    global_step = 0
    accumulation_steps = args.gradient_accumulation_steps
    device = accelerator.device
    avg_loss = torch.tensor(0., device=device)
    for epoch in range(args.num_epochs):
        for step, inputs in enumerate(train_dataloader):
            # To avoid OoM in edge case
            if args.empty_cache:
                gc.collect()
                torch.cuda.empty_cache()
                accelerator.free_memory()
            
            # I wasn't able to leverage accelerator accumulate
            if (step + 1) % accumulation_steps == 0:
                out = model(**inputs)
                accelerator.backward(out.loss/accumulation_steps)
                avg_loss += out.loss.detach()
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1
                reduced_loss = accelerator.reduce(avg_loss,reduction="mean")/ accumulation_steps
                if accelerator.is_main_process:
                    writer.add_scalar("loss_train", reduced_loss , global_step)
                    print(f"Step: {global_step}, Loss: {reduced_loss}, lr: {optimizer.param_groups[0]['lr']}.")
                    loop.update(1)
                avg_loss = torch.tensor(0., device=device)
            else:
                with accelerator.no_sync(model):
                    out = model(**inputs)
                    accelerator.backward(out.loss/accumulation_steps)
                    avg_loss += out.loss.detach()               
        folder_path = os.path.join(args.export, f"checkpoint-epoch-{epoch}")
        model.save_pretrained(
                        folder_path,
                        is_main_process=accelerator.is_main_process,
                        save_function=accelerator.save,
                        state_dict=accelerator.get_state_dict(model),
                    )
        if accelerator.is_main_process:
            tokenizer.save_pretrained(folder_path)
        # to avoid issue for the last epoch, since children will exit before main process finish retrieving shards
        accelerator.wait_for_everyone()
    return model

def eval_loop(model, tokenizer, eval_dataloader, filename):
    model.eval()
    outputs_list = []
    with torch.no_grad():
        for inputs in eval_dataloader:
            del inputs['target']
            out = model.generate(**inputs, do_sample=True, temperature=0.5, num_return_sequences=3, max_length=10_000)
            out = accelerator.pad_across_processes(out, dim=1, pad_index=tokenizer.pad_token_id, pad_first=True)
            out = accelerator.gather(out)
            outputs_list += tokenizer.batch_decode(out).tolist()
    if accelerator.is_main_process:
        with open(filename, "w") as f:
            json.dump(outputs_list, f, indent=4)

def main(args):
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name
    )
    dataset = load_and_process(tokenizer, args.data_path, args.prompt_path)
    train_dataloader = torch.utils.data.DataLoader(
        dataset["train"],
        batch_size=args.batch_size,
        num_workers=4,
        pin_memory=True,
        prefetch_factor=2,
        shuffle=True,
        collate_fn=lambda x:merge_and_pad_entries(x, tokenizer.pad_token_id, pad_first=False)
    )

    torch.set_default_device(accelerator.device)
    model = AutoModelForCausalLM.from_pretrained(args.model_name, attn_implementation="flash_attention_2", torch_dtype=torch.bfloat16, trust_remote_code=True)
    if not model.config.pad_token_id:
        model.config.pad_token_id = model.config.eos_token_id
    model.gradient_checkpointing_enable({"use_reentrant": False})
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, betas=(args.adam_beta1, args.adam_beta2), weight_decay=args.weight_decay)

    num_training_steps = int(len(train_dataloader) *args.num_epochs/args.gradient_accumulation_steps)
    lr_warmup_iters = int(num_training_steps * args.lr_warmup_ratio)
    lr_scheduler = get_cosine_schedule_with_warmup(optimizer, num_warmup_steps=lr_warmup_iters, num_training_steps=num_training_steps)

    model, optimizer, train_dataloader, lr_scheduler = accelerator.prepare(
        model, optimizer, train_dataloader, lr_scheduler
    )
    
    model = train_loop(model, tokenizer, train_dataloader, optimizer, lr_scheduler, args)


if __name__ == "__main__":
    main(args)