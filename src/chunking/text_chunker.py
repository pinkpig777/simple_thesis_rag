def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks

