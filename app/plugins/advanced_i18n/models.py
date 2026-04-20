"""
Database models for the Advanced Internationalization plugin.
"""

from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, JSON, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.core.db import Base


class Language(Base):
    """
    Represents a language supported by the application.
    """
    __tablename__ = "i18n_languages"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True, index=True)
    name = Column(String(50))
    native_name = Column(String(50))
    flag_code = Column(String(5), nullable=True)  # For displaying flag icons
    is_rtl = Column(Boolean, default=False)  # Right-to-left language
    is_default = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    translations = relationship("Translation", back_populates="language", cascade="all, delete-orphan")


class TranslationGroup(Base):
    """
    Represents a group of related translations (e.g., "admin", "frontend", "errors").
    """
    __tablename__ = "i18n_translation_groups"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    translations = relationship("Translation", back_populates="group", cascade="all, delete-orphan")


class Translation(Base):
    """
    Represents a single translation entry.
    """
    __tablename__ = "i18n_translations"
    
    id = Column(Integer, primary_key=True)
    language_id = Column(Integer, ForeignKey("i18n_languages.id"))
    group_id = Column(Integer, ForeignKey("i18n_translation_groups.id"))
    key = Column(String(255))
    value = Column(Text)
    context = Column(String(100), nullable=True)  # For disambiguation
    plural_forms = Column(JSON, nullable=True)  # For languages with complex plural rules
    is_machine_translated = Column(Boolean, default=False)
    needs_review = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    language = relationship("Language", back_populates="translations")
    group = relationship("TranslationGroup", back_populates="translations")


class TranslationHistory(Base):
    """
    Tracks the history of changes to translations.
    """
    __tablename__ = "i18n_translation_history"
    
    id = Column(Integer, primary_key=True)
    translation_id = Column(Integer, ForeignKey("i18n_translations.id"))
    language_code = Column(String(10))
    key = Column(String(255))
    old_value = Column(Text, nullable=True)
    new_value = Column(Text)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
