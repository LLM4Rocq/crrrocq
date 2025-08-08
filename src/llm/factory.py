from .openai_instruct import OpenAIInstructLLM, BaseLLM

DICT_LLM = {
    "openai_instruct": OpenAIInstructLLM
}

def get_llm(llm_name: str, *args, **kwargs) -> BaseLLM:
    if llm_name not in DICT_LLM:
        raise ValueError(f"Unknown model: {llm_name}")
    return DICT_LLM[llm_name](*args, **kwargs)