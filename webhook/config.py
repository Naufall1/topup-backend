import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    WEBHOOK_SECRET: str
    DATABASE_URL: str


def _load() -> Config:
    required = [
        "WEBHOOK_SECRET", "POSTGRES_USERNAME", "POSTGRES_PASSWORD",
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DATABASE",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return Config(
        WEBHOOK_SECRET=os.environ["WEBHOOK_SECRET"],
        DATABASE_URL=(
            f"postgresql://{os.environ['POSTGRES_USERNAME']}:{os.environ['POSTGRES_PASSWORD']}"
            f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DATABASE']}"
        ),
    )


config = _load()
