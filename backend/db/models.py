import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users import schemas
from fastapi_users_db_sqlalchemy.generics import GUID


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# User auth (fastapi-users)
# ---------------------------------------------------------------------------

class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    display_name: Mapped[str | None] = mapped_column(String(128))


# fastapi-users Pydantic schemas (required for router registration in main.py)

class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


# ---------------------------------------------------------------------------
# Property data
# ---------------------------------------------------------------------------

class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    address_input: Mapped[str] = mapped_column(String(512), nullable=False)
    address_matched: Mapped[str | None] = mapped_column(String(512), unique=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    county: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(2))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    price: Mapped[float | None] = mapped_column(Float)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[float | None] = mapped_column(Float)
    sqft: Mapped[int | None] = mapped_column(Integer)
    year_built: Mapped[int | None] = mapped_column(Integer)
    lot_size: Mapped[float | None] = mapped_column(Float)
    property_type: Mapped[str | None] = mapped_column(String(64))
    avm_estimate: Mapped[float | None] = mapped_column(Float)
    neighborhood_context: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    analyses: Mapped[list["Analysis"]] = relationship("Analysis", back_populates="listing")


class Comp(Base):
    __tablename__ = "comps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("analyses.id"), nullable=False)
    address: Mapped[str] = mapped_column(String(512))
    sold_price: Mapped[float | None] = mapped_column(Float)
    sold_date: Mapped[str | None] = mapped_column(String(32))
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[float | None] = mapped_column(Float)
    sqft: Mapped[int | None] = mapped_column(Integer)
    price_per_sqft: Mapped[float | None] = mapped_column(Float)
    distance_miles: Mapped[float | None] = mapped_column(Float)
    pct_over_asking: Mapped[float | None] = mapped_column(Float)
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="comps")


class RateLimitEntry(Base):
    __tablename__ = "rate_limit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("listings.id"), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    offer_low: Mapped[float | None] = mapped_column(Float)
    offer_high: Mapped[float | None] = mapped_column(Float)
    offer_recommended: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text)
    market_summary: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[str | None] = mapped_column(String(32))
    investment_rating: Mapped[str | None] = mapped_column(String(32))
    property_data_json: Mapped[str | None] = mapped_column(Text)
    neighborhood_data_json: Mapped[str | None] = mapped_column(Text)
    offer_data_json: Mapped[str | None] = mapped_column(Text)
    risk_data_json: Mapped[str | None] = mapped_column(Text)
    investment_data_json: Mapped[str | None] = mapped_column(Text)
    permits_data_json: Mapped[str | None] = mapped_column(Text)
    renovation_data_json: Mapped[str | None] = mapped_column(Text)
    crime_data_json: Mapped[str | None] = mapped_column(Text)
    buyer_context: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    listing: Mapped["Listing"] = relationship("Listing", back_populates="analyses")
    comps: Mapped[list["Comp"]] = relationship("Comp", back_populates="analysis", cascade="all, delete-orphan")
