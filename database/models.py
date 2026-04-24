from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float,
    Boolean, DateTime, Date, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Competitor(Base):
    """
    Represents the retail brands we are tracking.
    e.g., Myntra, Ajio, Amazon
    Replaces the hardcoded 'brands' section in targets.json.
    """
    __tablename__ = 'competitors'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(100), unique=True, nullable=False)
    category    = Column(String(50))                        # e.g., "Fashion"
    enabled     = Column(Boolean, default=True, nullable=False)
    added_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sources     = relationship("ScrapingSource", back_populates="competitor", cascade="all, delete-orphan")
    promotions  = relationship("Promotion", back_populates="competitor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Competitor(id={self.id}, name='{self.name}')>"


class ScrapingSource(Base):
    """
    Maps aggregator sites (CouponDunia, GrabOn) to competitor-specific URLs.
    This IS the dynamic, CRUD-able version of config/targets.json.
    """
    __tablename__ = 'scraping_sources'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    competitor_id   = Column(Integer, ForeignKey('competitors.id', ondelete='CASCADE'), nullable=False)
    source_name     = Column(String(50), nullable=False)    # e.g., "coupondunia"
    source_url      = Column(Text, unique=True, nullable=False)
    spider_name     = Column(String(50), nullable=False)    # Maps to the Scrapy spider class
    enabled         = Column(Boolean, default=True, nullable=False)
    added_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    modified_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    competitor      = relationship("Competitor", back_populates="sources")

    def __repr__(self):
        return f"<ScrapingSource(id={self.id}, source='{self.source_name}', url='{self.source_url}')>"


class Category(Base):
    """
    Master lookup table for offer categories.
    Supports subcategories via a self-referential parent_id.
    """
    __tablename__ = 'categories'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(100), unique=True, nullable=False)  # e.g., "Apparel"
    parent_id   = Column(Integer, ForeignKey('categories.id'), nullable=True)

    # Relationships
    children    = relationship("Category", backref="parent", remote_side=[id])
    promotions  = relationship("Promotion", back_populates="category")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"


class Promotion(Base):
    """
    Core table. Every scraped offer with structured, queryable fields.
    The offer_hash (SHA-256) ensures deduplication across spider runs.
    Structured fields (discount_min, coupon_code, etc.) are populated
    by the GLiNER enrichment pass after scraping.
    """
    __tablename__ = 'promotions'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    competitor_id   = Column(Integer, ForeignKey('competitors.id', ondelete='CASCADE'), nullable=False)
    category_id     = Column(Integer, ForeignKey('categories.id'), nullable=True)  # Set after enrichment

    # Raw scraped content
    offer_title     = Column(Text, nullable=False)
    raw_text        = Column(Text)

    # Structured fields - populated by GLiNER enrichment
    promo_type      = Column(String(30))    # "Percentage Off", "Flat Discount", "Cashback"
    discount_min    = Column(Float)         # e.g., 40.0
    discount_max    = Column(Float)         # e.g., 70.0 (for "40-70% off")
    flat_value      = Column(Float)         # e.g., 300.0 (for "₹300 off")
    min_purchase    = Column(Float)         # e.g., 1499.0
    coupon_code     = Column(String(50))
    user_type       = Column(String(20))    # "new", "existing", "all"
    valid_until     = Column(Date)          # Extracted date, NULL if not found

    # Source tracking
    source_name     = Column(String(50), nullable=False)
    source_url      = Column(Text)

    # Deduplication fingerprint: SHA-256 of (source_name + competitor.name + offer_title)
    offer_hash      = Column(String(64), unique=True, nullable=False)

    # Timestamps
    scraped_at      = Column(DateTime, nullable=False)  # Last time spider saw this
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    competitor      = relationship("Competitor", back_populates="promotions")
    category        = relationship("Category", back_populates="promotions")

    def __repr__(self):
        return f"<Promotion(id={self.id}, title='{self.offer_title[:40]}...')>"


class ScrapingRun(Base):
    """
    Audit log. Every Prefect flow run records its stats here.
    """
    __tablename__ = 'scraping_runs'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    spider_name     = Column(String(50), nullable=False)
    prefect_run_id  = Column(Text)          # Prefect flow run UUID for traceability
    started_at      = Column(DateTime, nullable=False)
    finished_at     = Column(DateTime)
    items_scraped   = Column(Integer, default=0)
    items_inserted  = Column(Integer, default=0)
    items_updated   = Column(Integer, default=0)
    status          = Column(String(20), default='running')  # "running", "success", "failed"

    def __repr__(self):
        return f"<ScrapingRun(id={self.id}, spider='{self.spider_name}', status='{self.status}')>"
