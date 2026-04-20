# backend/app/crud/crud_veille.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from sqlalchemy import desc
from typing import List, Optional

from ..models import veille as veille_model


# --- Fonctions de Lecture (Read) ---
async def get_article_by_id(db: AsyncSession, article_id: int) -> Optional[veille_model.Article]:
    """Récupère un article par sa clé primaire (ID)."""
    result = await db.execute(select(veille_model.Article).filter(veille_model.Article.id == article_id))
    return result.scalars().first()

async def get_articles(
    db: AsyncSession,
    published: Optional[bool] = None,
    score_min: Optional[int] = None,
    cluster: Optional[str] = None
) -> List[veille_model.Article]:
    """Récupère une liste d'articles avec filtres."""
    query = select(veille_model.Article)
    if published is not None:
        query = query.filter(veille_model.Article.published == published)
    if cluster is not None:
        query = query.filter(veille_model.Article.sujet_cluster == cluster)
    if score_min is not None:
        query = query.filter(veille_model.Article.score_pertinence >= score_min)
    
    query = query.order_by(desc(veille_model.Article.score_pertinence))
    result = await db.execute(query)
    articles_sequence = result.scalars().all()
    return list(articles_sequence)

async def get_articles_without_cluster(db: AsyncSession) -> List[veille_model.Article]:
    """Récupère tous les articles où le sujet_cluster est NULL ou une chaîne vide."""
    query = select(veille_model.Article).filter((veille_model.Article.sujet_cluster == None) | (veille_model.Article.sujet_cluster == ''))
    result = await db.execute(query)
    return list(result.scalars().all())

# --- Fonctions d'Écriture (Create, Update, Delete) ---
async def create_or_update_article(db: AsyncSession, article_data: dict) -> veille_model.Article:
    """
    Crée un nouvel article ou met à jour un article existant basé sur son URL.
    Parfaitement compatible avec le modèle `Article` utilisant les dataclasses.
    """
    # On utilise `await` car la fonction `get_article_by_url` est asynchrone
    result = await db.execute(select(veille_model.Article).filter(veille_model.Article.url == article_data["url"]))
    db_article = result.scalars().first()
    
    # On prépare un dictionnaire contenant uniquement les champs valides pour le modèle
    valid_fields = {k: v for k, v in article_data.items() if hasattr(veille_model.Article, k)}

    if db_article:
        # --- MISE À JOUR ---
        # On met à jour chaque champ de l'objet existant.
        for key, value in valid_fields.items():
            setattr(db_article, key, value)
        print(f"Mise à jour de l'article : {db_article.url}")
    else:
        # --- CRÉATION ---
        # *** LA CORRECTION EST ICI ***
        # On crée l'objet en passant les arguments par mot-clé.
        # Comme le modèle `Article` a `id: Mapped[id_key] = mapped_column(init=False)`,
        # Python n'exigera pas de valeur pour `id` dans le constructeur.
        db_article = veille_model.Article(**valid_fields)
        db.add(db_article)
        print(f"Création d'un nouvel article : {db_article.url}")
        
    await db.commit()
    await db.refresh(db_article)
    return db_article

async def update_publish_status(db: AsyncSession, article_id: int, published: bool) -> Optional[veille_model.Article]:
    """Met à jour le statut de publication d'un article."""
    db_article = await get_article_by_id(db, article_id=article_id)
    if db_article:
        db_article.published = published
        await db.commit()
        await db.refresh(db_article)
    return db_article


async def delete_all_articles(db: AsyncSession) -> int:
    """Supprime tous les articles de la table 'article'."""
    result = await db.execute(delete(veille_model.Article))
    deleted_rows_count = result.rowcount
    await db.commit()
    print(f"INFO: Tous les {deleted_rows_count} articles ont été supprimés de la base de données.")
    return deleted_rows_count

async def get_distinct_clusters(db: AsyncSession) -> List[str]:
    """
    Récupère la liste de tous les sujets de cluster uniques,
    en ignorant les NULL et les chaînes vides.
    """
    result = await db.execute(
        select(veille_model.Article.sujet_cluster)
        .where(veille_model.Article.sujet_cluster.isnot(None))
        .where(veille_model.Article.sujet_cluster != "")
        .distinct()
    )
    return [row[0] for row in result.all()]
