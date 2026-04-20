from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from celery import Task
from typing import cast
from fastapi import status
from app.core.db import get_async_db
from app.crud import crud_veille
from app.schemas import veille as veille_schema
from app.tasks.veille_tasks import run_veille_workflow_task, backfill_clusters_task
from app.core.security import get_current_active_user


# router = APIRouter(dependencies=[Depends(get_current_active_user)])
router = APIRouter()

@router.post("/run", status_code=202, summary="Lancer une nouvelle veille en arrière-plan (Admin)")
def run_new_veille(
    query: str = Query(..., min_length=3, description="Le sujet de la veille, ex: 'Tendances Fintech'")
    # Note : cette route est maintenant `def` et non `async def` car elle est instantanée.
    # Elle n'a pas besoin de `Depends(get_async_db)` car elle ne touche pas à la DB.
):
    """
    Déclenche le processus de veille via Celery et répond immédiatement.
    Le travail lourd se fait en arrière-plan par un worker Celery.
    """
    try:
        print(f"Envoi de la tâche de veille pour '{query}' à Celery.")
        # On délègue le travail à Celery. `.delay()` envoie la tâche au broker (Redis).
        cast(Task,run_veille_workflow_task).delay(query)
        return {"message": "Tâche de veille lancée en arrière-plan. Les résultats seront disponibles via /articles dans ~30 minutes."}
    except Exception as e:
        # Gère le cas où le broker Celery/Redis est inaccessible
        print(f"ERREUR : Impossible de contacter le broker Celery. {e}")
        raise HTTPException(status_code=503, detail=f"Le service de tâches de fond est indisponible : {str(e)}")


@router.post("/backfill-clusters", status_code=202, summary="Lancer le backfill des clusters (Admin)")
def run_backfill_clusters():
    """
    Déclenche une tâche de fond pour analyser les articles existants sans cluster
    et leur assigner un `sujet_cluster` en utilisant le LLM.
    """
    try:
        print("Envoi de la tâche de backfill des clusters à Celery.")
        cast(Task, backfill_clusters_task).delay()
        return {"message": "Tâche de backfill des clusters lancée en arrière-plan."}
    except Exception as e:
        print(f"ERREUR : Impossible de contacter le broker Celery. {e}")
        raise HTTPException(status_code=503, detail=f"Le service de tâches de fond est indisponible : {str(e)}")



@router.get("/articles", response_model=List[veille_schema.ArticleResponse], summary="Lister les articles analysés (Admin)")
async def get_articles(
    published: Optional[bool] = Query(None, description="Filtrer par statut de publication."),
    score_min: Optional[int] = Query(None, ge=1, le=10, description="Score de pertinence minimum."),
    cluster: Optional[str] = Query(None, description="Filtrer par sujet de cluster."),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Récupère les articles de la base de données. Rapide et sécurisé.
    """
    articles = await crud_veille.get_articles(db=db, published=published, score_min=score_min, cluster=cluster)
    return articles


@router.get("/clusters", response_model=List[str], summary="Lister tous les sujets de cluster uniques")
async def get_clusters(db: AsyncSession = Depends(get_async_db)):
    """
    Récupère la liste de tous les sujets de cluster uniques pour peupler les filtres.
    """
    clusters = await crud_veille.get_distinct_clusters(db=db)
    return clusters


@router.post("/articles/{article_id}/publish", response_model=veille_schema.ArticleResponse, summary="Publier un article (Admin)")
async def publish_article(
    article_id: int,
    status: veille_schema.PublishStatusUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Modifie le statut de publication d'un article. Rapide et sécurisé.
    """
    updated_article = await crud_veille.update_publish_status(db, article_id=article_id, published=status.published)
    if not updated_article:
        raise HTTPException(status_code=404, detail="Article non trouvé.")
        
    if status.published:
        print(f"INFO: L'article {article_id} est maintenant marqué comme publié. Déclenchement de la diffusion...")
        # C'est ici que vous pourriez lancer une AUTRE tâche Celery pour la publication sociale.
        # from app.tasks.social import post_article_task
        # post_article_task.delay(article_id)

    return updated_article



@router.delete("/articles/all", status_code=status.HTTP_200_OK, summary="Supprimer tous les articles (Admin, DANGEREUX)")
async def delete_all_articles(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Supprime **tous** les articles de la base de données.
    
    **ATTENTION :** Cette opération est irréversible. Utilisez-la avec précaution,
    principalement pour le nettoyage en environnement de développement.
    """
    deleted_count = await crud_veille.delete_all_articles(db=db)
    return {"message": f"{deleted_count} articles ont été supprimés avec succès."}