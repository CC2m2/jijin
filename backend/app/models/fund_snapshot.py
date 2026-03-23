from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FundSnapshot(Base):
    __tablename__ = "fund_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    fund_code: Mapped[str] = mapped_column(String(32), index=True)
    nav_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    unit_nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="tiantian-fund")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
