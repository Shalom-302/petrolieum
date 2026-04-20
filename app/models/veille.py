"""Scraap plugin models."""

from typing import List, Dict, TypedDict, Optional, Any
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base
import datetime
from sqlalchemy import func, DateTime

from app.core.db import Base
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
import datetime


class Article(Base):
    """
    Modèle SQLAlchemy pour stocker les articles de veille, parfaitement mappé
    aux schémas Pydantic ArticleBase, ArticleAnalysis, et ArticleResponse.
    """
    __tablename__ = "articles"

    # --- Clé Primaire ---
    # Converti en str dans le schéma Pydantic de réponse
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # --- Champs de Base (correspondant à ArticleBase) ---
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[Optional[str]] = mapped_column(String(50), default=None) # Date de publication

    # --- Champs de Contenu et d'État ---
    content: Mapped[Optional[str]] = mapped_column(Text, default=None)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, default=None)

    # --- Champs d'Analyse ---
    
    # Champ "dénormalisé" pour un accès et un tri rapides.
    # Il est aussi présent dans l'objet 'analysis' ci-dessous.
    score_pertinence: Mapped[Optional[int]] = mapped_column(Integer, index=True, default=None)
    
    # Champ pour le clustering sémantique, généré par le LLM.
    # Indexé pour un filtrage ultra-rapide.
    sujet_cluster: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    
    # Cette colonne de type JSON stockera l'intégralité de l'objet Pydantic 'ArticleAnalysis'.
    # C'est la manière la plus flexible et robuste de stocker des données structurées.
    analysis: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    
    # Champ technique pour savoir quand l'analyse a été faite.
    # Il est automatiquement rempli par la base de données.
    analysis_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, 
        server_default=func.now(), 
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title[:30]}...')>"