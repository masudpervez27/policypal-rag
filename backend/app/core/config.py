from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Qdrant (namespaced collections per tenant/policy set)
    qdrant_url: str = "https://your-cluster.qdrant.io"
    qdrant_api_key: str = ""
    qdrant_collection_prefix: str = "policypal"   # collections: policypal_{tenant}

    # Neon PostgreSQL (conversation history)
    database_url: str = "postgresql://user:password@host/db?sslmode=require"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Embeddings (local, free)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # CORS
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
