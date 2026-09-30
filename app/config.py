from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    secret_key: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    session_secret_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()