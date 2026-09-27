from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    password: Mapped[str]

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class Game(Base):
    __tablename__ = "games"

    buyer_sku_code: Mapped[str] = mapped_column(primary_key=True)
    product_name: Mapped[str]
    brand: Mapped[str]
    buy_price: Mapped[float]
    sell_price: Mapped[float]
    stock: Mapped[int]
    desc: Mapped[str | None]

class UsernameCache(Base):
    __tablename__ = "username_cache"

    game: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str | None]
    valid: Mapped[bool]
    message: Mapped[str]
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

class Transaction(Base):
    __tablename__ = "transactions"

    trx_id: Mapped[str] = mapped_column(primary_key=True)
    ref_id: Mapped[str] = mapped_column(unique=True, server_default=func.gen_random_uuid())
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    customer_no: Mapped[str]
    buyer_sku_code: Mapped[str] = mapped_column(ForeignKey("games.buyer_sku_code"))
    status: Mapped[str]
    price: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )