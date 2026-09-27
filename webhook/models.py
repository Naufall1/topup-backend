from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

class Base(DeclarativeBase):
    pass

# NOTE: buyer_sku_code/user_id are FKs to games/users at the DB level, but
# those tables aren't mapped here (webhook never queries them) — declaring
# ForeignKey() without the target table mapped breaks SQLAlchemy's flush-time
# dependency sort (NoReferencedTableError), so they're plain columns here.
class Transaction(Base):
    __tablename__ = "transactions"

    trx_id: Mapped[str] = mapped_column(primary_key=True)
    ref_id: Mapped[str] = mapped_column(unique=True, server_default=func.gen_random_uuid())
    user_id: Mapped[int | None]
    customer_no: Mapped[str]
    buyer_sku_code: Mapped[str]
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