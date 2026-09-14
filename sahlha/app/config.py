"""Central application settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Sahlha AI Learning Agent (MVP)"
    database_url: str = "sqlite:///./data/sahlha.db"
    upload_dir: str = "./data/uploads"
    vectorizer_path: str = "./data/tfidf_vectorizer.pkl"

    # LLM provider: Groq (OpenAI-compatible API). Empty key => grounded fallback generator.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"

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

    # Pexels image search (one related image per skill). Empty => image tool unavailable.
    pexels_api_key: str = ""
    image_dir: str = "./data/images"

    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k_retrieval: int = 5
    assessment_num_questions: int = 4  # questions selected from EACH approved bank


settings = Settings()
