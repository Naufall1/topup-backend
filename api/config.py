import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    BASE_URL: str
    USERNAME: str
    API_KEY: str
    WEBHOOK_ID: str
    WEBHOOK_SECRET: str
    DATABASE_URL: str
    DIGIFLAZZ_TESTING_MODE: bool
    JWT_SECRET: str
    JWT_ACCESS_EXPIRE_MINUTES: int
    JWT_REFRESH_EXPIRE_DAYS: int
    FRONTEND_ORIGIN: str
    COOKIE_SECURE: bool
    HTTP_PROXY: str | None


def _load() -> Config:
    required = [
        "BASE_URL", "DIGIFLAZZ_USERNAME", "DIGIFLAZZ_API_KEY", "WEBHOOK_ID",
        "WEBHOOK_SECRET", "POSTGRES_USERNAME", "POSTGRES_PASSWORD",
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE", "JWT_SECRET",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return Config(
        BASE_URL=os.environ["BASE_URL"],
        USERNAME=os.environ["DIGIFLAZZ_USERNAME"],
        API_KEY=os.environ["DIGIFLAZZ_API_KEY"],
        WEBHOOK_ID=os.environ["WEBHOOK_ID"],
        WEBHOOK_SECRET=os.environ["WEBHOOK_SECRET"],
        DATABASE_URL=(
            f"postgresql://{os.environ['POSTGRES_USERNAME']}:{os.environ['POSTGRES_PASSWORD']}"
            f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DATABASE']}"
        ),
        DIGIFLAZZ_TESTING_MODE=os.getenv("DIGIFLAZZ_TESTING_MODE", "true").lower() == "true",
        JWT_SECRET=os.environ["JWT_SECRET"],
        JWT_ACCESS_EXPIRE_MINUTES=int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "180")),
        JWT_REFRESH_EXPIRE_DAYS=int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7")),
        FRONTEND_ORIGIN=os.getenv("FRONTEND_ORIGIN", "http://localhost"),
        COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        HTTP_PROXY=os.getenv("HTTP_PROXY") or None,
    )


config = _load()
