from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    secret_key: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    session_secret_key: str
    registration_token_expire_minutes: int = 15
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    verification_token_expire_hours: int = 24
    password_reset_token_expire_minutes: int = 30
    upload_dir: str = "uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()