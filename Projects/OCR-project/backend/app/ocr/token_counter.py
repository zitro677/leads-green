import tiktoken

_enc = None


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding(model)
    return len(_enc.encode(text))
