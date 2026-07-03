def truncate_for_log(value, max_length=500):
    text = str(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}... [truncated {len(text) - max_length} chars]"