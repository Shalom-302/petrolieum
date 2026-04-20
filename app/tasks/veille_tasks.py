import asyncio
from app.core.celery import celery_app
from app.services import veille_service
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings


# ============================================================
# 1️⃣ Tâche principale : exécuter un workflow de veille
# ============================================================
@celery_app.task(name="veille.run_workflow")
def run_veille_workflow_task(query: str):
    """
    Tâche Celery synchrone qui exécute un workflow de veille asynchrone.
    Elle crée et gère sa propre session de base de données.
    """
    async def async_workflow():
        print(f"--- Tâche Celery Démarrée : Veille pour '{query}' ---")

        # ✅ Crée un engine et un sessionmaker locaux (et propres à cette loop)
        engine = create_async_engine(settings.ASYNC_DB_URL, echo=False, future=True)
        AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)

        session = None
        try:
            async with AsyncSessionFactory() as session:
                await veille_service.run_veille_workflow(db=session, query=query)

            print(f"--- Tâche de veille pour '{query}' terminée avec succès. ---")
            return {"status": "SUCCESS", "message": "Veille terminée."}
        except Exception as e:
            error_message = f"La tâche de veille a échoué pour la requête '{query}': {e}"
            print(f"--- ERREUR dans la Tâche Celery : {error_message} ---")
            return {"status": "FAILURE", "error": str(e)}
        finally:
            if session:
                await session.close()
                print("--- Session DB fermée proprement ---")
            await engine.dispose()  # ✅ ferme proprement la connexion à la DB

    return asyncio.run(async_workflow())


# ============================================================
# 2️⃣ Tâche secondaire : backfill des clusters
# ============================================================
@celery_app.task(name="veille.backfill_clusters")
def backfill_clusters_task():
    """
    Tâche Celery pour remplir les `sujet_cluster` manquants dans les articles.
    """
    async def async_backfill():
        print("--- Tâche Celery Démarrée : Backfill des clusters ---")

        # ✅ Même approche : chaque tâche a sa propre loop et son propre moteur
        engine = create_async_engine(settings.ASYNC_DB_URL, echo=False, future=True)
        AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)

        session = None
        try:
            async with AsyncSessionFactory() as session:
                await veille_service.backfill_clusters_service(db=session)
            print("--- Backfill terminé avec succès ---")
            return {"status": "SUCCESS"}
        except Exception as e:
            print(f"--- ERREUR dans la Tâche Celery de backfill : {e} ---")
            return {"status": "FAILURE", "error": str(e)}
        finally:
            if session is not None:
                await session.close()
                print("--- Session DB fermée proprement ---")
            await engine.dispose()

    return asyncio.run(async_backfill())
