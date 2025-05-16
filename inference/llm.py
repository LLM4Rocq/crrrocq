import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
import requests
from dataclasses import dataclass
from llm_logger import LLMLogger

# ===============================================
# LLM Interface and Implementations
# ===============================================


class LLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """Generate a completion using the LLM."""
        pass

    @abstractmethod
    def generate_batch(
        self, prompts: List[str], stop_sequences: Optional[List[str]] = None
    ) -> List[str]:
        """Generate completions for multiple prompts."""
        pass


class VLLM(LLM):
    """Implementation of LLM using VLLM's OpenAI-compatible API."""

    def __init__(
        self,
        api_url: str,
        model: str,
        temperature: float = 1.0,
        top_p: float = 0.9,
        top_k: int = 40,
        max_tokens: int = 16384,
        verbose: bool = False,
        log_dir: str = "llm_logs",
        log_to_console: bool = False,
    ):
        self.api_url = api_url
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.verbose = verbose

        # Initialize the LLM logger
        self.logger = LLMLogger(
            log_dir=log_dir, enabled=True, log_to_console=log_to_console or verbose
        )

    def build_prompt(
        self, goals: str, coq_tag: str, context: str = "", goals_tag: str = "GOALS"
    ) -> str:
        """
        Build the initial prompt for the LLM.

        Args:
            theorem_code: The theorem code to prove
            coq_tag: The XML tag to use for Coq code

        Returns:
            The constructed prompt
        """
        return f"""
You are an analytical and helpful assistant proficient in mathematics as well as in the use of the Coq theorem prover and programming language. You will be provided with a Coq/math-comp theorem and your task is to prove it. This will happen in interaction with a Coq proof engine which will execute the proof steps you give it, one at a time, and provide feedback.
Your goal is to write proof steps interactively until you manage to find a complete proof for the proposed theorem. You will be able to interact with the proof engine by issuing coq code enclosed in <{coq_tag}> </{coq_tag}> delimiters.
Do not attempt to directly write the complete proof, but rather only try to execute simple steps or tactics to make incremental progress.

At each step you will be provided with the current list of goals inside <{goals_tag}> </{goals_tag}> delimiters.
Please explain your reasoning before proposing a Coq proof inside <{coq_tag}> </{coq_tag}> delimiters.
Remember to close all your delimiters, for instance with a </{coq_tag}>.
DO NOT RESTATE THE THEOREM OR THE CURRENT GOAL.

Example 1.

Here are the current goals.
<{goals_tag}>
n, m, p : nat
|- nat, n + (m + p) = m + (n + p)
</{goals_tag}> 

and here is one possible proof step.

<{coq_tag}>
rewrite Nat.add_assoc.
</{coq_tag}>

Example 2.
Here are the current goals.

<{goals_tag}>
f nat -> nat 
I forall n : nat, n = f (f n) 
n1n2 nat 
H f n1 = f n2 
|- n1 = n2
</{goals_tag}>

and here is one possible proof step.

<{coq_tag}>
rewrite (I n1).
</{coq_tag}>


Ready?

{context}

Here are the current goals.
<{goals_tag}>
{goals}
</{goals_tag}>
"""

    def generate(self, prompt: str, stop_sequences: Optional[List[str]] = None) -> str:
        """Generate a completion using VLLM's OpenAI-compatible API."""
        responses = self.generate_batch([prompt], stop_sequences)
        return responses[0] if responses else ""

    def generate_batch(
        self, prompts: List[str], stop_sequences: Optional[List[str]] = None
    ) -> List[str]:
        """
        Generate completions for multiple prompts.

        Args:
            prompts: List of prompts to generate completions for
            stop_sequences: Optional list of stop sequences

        Returns:
            List of generated completions corresponding to each prompt
        """
        if not prompts:
            return []

        payload = {
            "model": self.model,
            "prompt": prompts,
            "temperature": self.temperature,
            # "top_p": self.top_p,
            # "top_k": self.top_k,
            "max_tokens": self.max_tokens,
            "include_stop_str_in_output": True,
            "stream": False,
        }

        # Add optional parameters if specified
        if stop_sequences:
            payload["stop"] = stop_sequences

        try:
            response = requests.post(
                f"{self.api_url}/v1/completions",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
            )

            if response.status_code != 200:
                raise Exception(
                    f"LLM API returned error: {response.status_code} - {response.text}"
                )

            data = response.json()

            # if self.verbose:
            #    print(f"LLM API response: {data}")

            # Extract the completions from the response
            llm_responses = [choice["text"] for choice in data["choices"]]

            # Log the interaction
            metadata = {
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stop_sequences": stop_sequences,
            }

            # Log the batch interaction
            self.logger.log_batch_interaction(
                prompts=prompts,
                responses=llm_responses,
                metadata=metadata,
                prefix=self.model.split("/")[-1],  # Use model name as prefix
            )

            return llm_responses

        except Exception as e:
            print(f"Error in generate_batch: {e}")
            # Return empty strings in case of error
            return [""] * len(prompts)
