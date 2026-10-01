from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    BASE_URL: str = "http://localhost:8000"

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"

    DATABASE_URL: str

    ACTIVE_COMMERCE_ADAPTER: str = "shopify"
    SHOPIFY_STORE_DOMAIN: str = ""
    SHOPIFY_STOREFRONT_TOKEN: str = ""
    SHOPIFY_ADMIN_ACCESS_TOKEN: str = ""
    SHOPIFY_API_VERSION: str = "2026-07"
    GMC_DB_PATH: str = ":memory:"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()