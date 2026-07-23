from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text,
    Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Competitor(Base):
    """
    Represents the retail brands we are tracking.
    e.g., David Jones, The Iconic, Forever New
    """
    __tablename__ = 'competitors'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(100), unique=True, nullable=False)
    enabled     = Column(Boolean, default=True, nullable=False)
    added_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    promotions  = relationship("Promotion", back_populates="competitor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Competitor(id={self.id}, name='{self.name}')>"


class Promotion(Base):
    """
    Core table. Every scraped offer with raw fields.
    The offer_hash (SHA-256) ensures deduplication across runs.
    """
    __tablename__ = 'promotions'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    competitor_id   = Column(Integer, ForeignKey('competitors.id', ondelete='CASCADE'), nullable=False)
    brand           = Column(String(100), nullable=False)

    # Raw scraped content
    offer_title     = Column(Text, nullable=False)
    category        = Column(String(100))

    # Source tracking
    source_name            = Column(String(50), nullable=False)
    source_url             = Column(Text)
    extraction_confidence  = Column(String(10))   # "high" | "medium" | "low" — set by Vision LLM

    # Deduplication fingerprint: SHA-256 of (source_name + competitor.name + offer_title)
    offer_hash      = Column(String(64), unique=True, nullable=False)

    # Timestamps
    scraped_at      = Column(DateTime, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    competitor       = relationship("Competitor", back_populates="promotions")
    team_assignments = relationship("PromotionTeamAssignment", back_populates="promotion", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Promotion(id={self.id}, brand='{self.brand}', title='{self.offer_title[:40]}...')>"


class PromotionTeamAssignment(Base):
    """
    Junction table recording team visibility for promotions.
    A promotion can be assigned to multiple business teams based on policy rules.
    """
    __tablename__ = 'promotion_team_assignments'

    id             = Column(Integer, primary_key=True, autoincrement=True)
    promotion_id   = Column(Integer, ForeignKey('promotions.id', ondelete='CASCADE'), nullable=False)
    team_id        = Column(String(50), nullable=False)
    assigned_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    promotion      = relationship("Promotion", back_populates="team_assignments")

    def __repr__(self):
        return f"<PromotionTeamAssignment(promotion_id={self.promotion_id}, team_id='{self.team_id}')>"

