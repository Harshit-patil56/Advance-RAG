"""Application configuration loaded from environment variables.

All settings are read once at startup via pydantic-settings.
# No values are hardcoded in source code. (auto-reload trigger 2)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Supabase
    supabase_url: str
    supabase_service_role_key: str

    # Qdrant
    qdrant_url: str
    qdrant_api_key: str

    # HuggingFace
    huggingface_api_token: str
    huggingface_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash-lite"

    # Groq
    groq_api_key: str
    groq_model: str = "llama3-8b-8192"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # App behaviour
    app_version: str = "1.0.0"
    max_file_size_mb: int = 10
    max_query_chars: int = 2000
    retrieval_top_k: int = 4
    retrieval_score_threshold: float = 0.0
    embedding_batch_size: int = 32
    max_summary_tokens: int = 300
    llm_timeout_seconds: int = 15

    # Qdrant collection names
    qdrant_finance_collection: str = "finance_chunks"
    qdrant_law_collection: str = "law_chunks"
    qdrant_global_collection: str = "global_chunks"

    # Supabase storage bucket
    storage_bucket: str = "raw-uploads"

    # Vector dimension for all-MiniLM-L6-v2
    embedding_dimension: int = 384

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
