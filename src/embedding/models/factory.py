from .gteqwen import GteQwenEmbedding
from .mxbai import MxbaiEmbedding
from .qwen_embedding import Qwen3Embedding600m, Qwen3Embedding4b, Qwen3Embedding8b

DICT_MODEL = {
    "gte_qwen": GteQwenEmbedding,
    "mxbai": MxbaiEmbedding,
    "qwen_embedding_600m": Qwen3Embedding600m,
    "qwen_embedding_4b": Qwen3Embedding4b,
    "qwen_embedding_8b": Qwen3Embedding8b,
}

def get_embedding_model(model_name: str, *args, **kwargs):
    if model_name not in DICT_MODEL:
        raise ValueError(f"Unknown model: {model_name}")
    return DICT_MODEL[model_name](*args, **kwargs)