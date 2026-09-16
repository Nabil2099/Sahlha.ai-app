"""Central application settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Sahlha AI Learning Platform"
    database_url: str = "sqlite:///./data/sahlha.db"
    upload_dir: str = "./data/uploads"
    vectorizer_path: str = "./data/tfidf_vectorizer.pkl"
    vector_cache_path: str = "./data/vectors.npz"
    dense_embeddings_enabled: bool = True
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_warmup: bool = True
    vector_incremental_churn: float = 0.35
    mmr_lambda: float = 0.7
    dense_min_score: float = 0.05
    retrieval_backoff_ratio: float = 0.5
    tesseract_cmd: str = ""
    poppler_path: str = ""
    ocr_min_chars: int = 50
    ocr_languages: str = "eng"
    ocr_dpi: int = 250
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    enable_llm_critique: bool = False
    legacy_dev_api_enabled: bool = False

    # ---- Auth (JWT) ----
    # Prototype default; override via SAHLHA_JWT_SECRET in real deployments.
    jwt_secret: str = "sahlha-dev-secret-change-me-in-production-32"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 days (mobile prototype convenience)

    # ---- Mastery thresholds (student-facing states) ----
    mastery_developing_min: float = 0.6  # accuracy >= this => developing
    mastery_mastered_min: float = 0.8  # accuracy >= this (+ min attempts) => mastered
    mastery_min_attempts: int = 4  # attempts required before "mastered" is awarded

    # ---- Uploads ----
    max_upload_mb: int = 25
    allowed_extensions: str = ".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg,.tiff,.bmp"

    # ---- CORS (mobile development) ----
    # Comma-separated origins allowed in addition to the mobile defaults.
    cors_extra_origins: str = ""

    # LLM provider: Groq (OpenAI-compatible API). Empty key => grounded fallback generator.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = ""
    provider_timeout_seconds: float = 45

    # Optional OpenAI override (used only if Groq key is absent).
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""

    # Groq text-to-speech (Orpheus English). Requires GROQ_API_KEY + accepted model terms
    # in the Groq console. No offline fallback exists for audio.
    groq_tts_model: str = "canopylabs/orpheus-v1-english"
    groq_tts_voice: str = "troy"
    groq_tts_max_chars: int = 900  # per TTS request; longer text is chunked + stitched
    audio_dir: str = "./data/audio"
    openrouter_tts_model: str = ""
    openrouter_tts_voice: str = "alloy"
    openrouter_tts_format: str = "pcm"
    openrouter_tts_sample_rate: int = 24000

    # Pexels image search (one related image per skill). Empty => image tool unavailable.
    pexels_api_key: str = ""
    image_dir: str = "./data/images"

    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k_retrieval: int = 5
    assessment_num_questions: int = 4  # questions selected from EACH approved bank


settings = Settings()
