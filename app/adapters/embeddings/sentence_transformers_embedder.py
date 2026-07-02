"""Local embeddings. First run downloads the model once (~130MB) from
HuggingFace; after that it runs fully offline. For a truly air-gapped
deployment, pre-stage the model files on the server."""
from app.config import settings
from app.core.embeddings import Embedder


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer

        name = model_name or settings.embedding_model
        try:
            # Once cached, never phone home to check for updates — this is a
            # "fully local / air-gapped" product (see rules.md); a live HEAD
            # request to huggingface.co on every cold start also adds a
            # couple of real seconds to the first request after any restart.
            self.model = SentenceTransformer(name, local_files_only=True)
        except OSError:
            self.model = SentenceTransformer(name)  # first run: allow the download

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode([text], normalize_embeddings=True)[0].tolist()
