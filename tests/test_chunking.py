from app.services.chunking import chunk_text


def test_chunk_splits_long_text():
    text = " ".join(["word"] * 2000)
    chunks = chunk_text(text, chunk_size=800, overlap=150)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_chunk_empty_returns_empty():
    assert chunk_text("") == []
