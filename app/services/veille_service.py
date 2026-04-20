import os
from typing import List, Dict, TypedDict, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import trafilatura
import asyncio
from sqlalchemy.orm import Session
from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.output_parsers import StrOutputParser

# Imports depuis notre module `veille`, corrigés
from app.schemas import veille as veille_schema
from app.crud import  crud_veille

from app.core.config import settings

# Initialisation du LLM en utilisant la configuration centrale
from pydantic import SecretStr

llm = ChatDeepSeek(api_key=SecretStr(settings.DEEPSEEK_API_KEY), model="deepseek-chat", temperature=0)


# --- Fonctions de Scraping et Registre ---
class FoundArticle(TypedDict):
    title: str; url: str; source: str

DOMAINES_A_IGNORER = ['bloomberg.com', 'wsj.com', 'nytimes.com', 'reuters.com', 'ft.com', 'theinformation.com', 'axios.com', 't.co', 'ad.doubleclick.net']

async def scrape_techmeme(soup: BeautifulSoup, base_url: str) -> List[FoundArticle]:
    articles = []
    for link in soup.select('strong > a'):
        href, title = link.get('href'), link.get_text(strip=True)
        if href and title and not any(domaine in href for domaine in DOMAINES_A_IGNORER):
            articles.append({"title": title, "url": urljoin(base_url, str(href)), "source": "Techmeme"})
        # Limite à 20 articles
        if len(articles) >= 20:
            break
    return articles

async def scrape_techcabal(soup: BeautifulSoup, base_url: str) -> List[FoundArticle]:
    articles = []
    for link in soup.select("article.article-list-item a.article-list-title"):
        title, href = link.get_text(strip=True), link.get('href')
        if title and href: 
            articles.append({"title": title, "url": urljoin(base_url, str(href)), "source": "TechCabal"})
        # Limite à 20 articles
        if len(articles) >= 20:
            break
    return articles

async def scrape_techpoint_africa(soup: BeautifulSoup, base_url: str) -> List[FoundArticle]:
    articles = []
    for link in soup.select("div.gb-query-loop-item .value a"):
        href, title = link.get_text(strip=True), link.get('href')
        if href and title: 
            articles.append({"title": title, "url": urljoin(base_url, href), "source": "TechPoint Africa"})
        # Limite à 20 articles
        if len(articles) >= 20:
            break
    return articles

async def scrape_disruptafrica(soup: BeautifulSoup, base_url: str) -> List[FoundArticle]:
    articles = []
    for link in soup.select(".post-title a"):
        href, title = link.get_text(strip=True), link.get('href')
        if href and title: 
            articles.append({"title": title, "url": urljoin(base_url, href), "source": "Disrupt Africa"})
        # Limite à 20 articles
        if len(articles) >= 20:
            break
    return articles

async def scrape_weetracker(soup: BeautifulSoup, base_url: str) -> List[FoundArticle]:
    articles = []
    for link in soup.select("h5.f-title a"):
        href, title = link.get_text(strip=True), link.get('href')
        if href and title: 
            articles.append({"title": title, "url": urljoin(base_url, href), "source": "WeeTracker"})
        # Limite à 20 articles
        if len(articles) >= 20:
            break
    return articles
SCRAPER_REGISTRY = {
    "https://www.techmeme.com/": scrape_techmeme,
    "https://techcabal.com/": scrape_techcabal,
    "https://techpoint.africa/": scrape_techpoint_africa,
    "https://disruptafrica.com/": scrape_disruptafrica,
    "https://weetracker.com/": scrape_weetracker,
}

# --- Logique LangGraph interne au service ---
class AgentState(TypedDict):
    db_session: AsyncSession
    query: str
    sites_to_process: List[str]
    current_site: str
    found_articles: List[FoundArticle]

# --- Nœuds du Graphe ---
async def plan_next_site(state: AgentState) -> dict:
    sites = state.get("sites_to_process", []).copy()
    if sites:
        return {"current_site": sites.pop(0), "sites_to_process": sites}
    else:
        return {"current_site": ""}

async def scraper_dispatcher(state: AgentState) -> dict:
    site_url = state["current_site"]
    scraper_function = SCRAPER_REGISTRY.get(site_url)
    if not scraper_function: return {}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(site_url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        new_articles = await scraper_function(soup, site_url)
        print(f"Trouvé {len(new_articles)} articles sur {site_url}.")
        current_articles = state.get("found_articles", [])
        return {"found_articles": current_articles + new_articles}
    except Exception as e:
        print(f"ERREUR lors du scraping de {site_url}: {e}")
        return {}

async def extract_analyze_and_save(state: AgentState) -> dict:
    print("\n--- NŒUD FINAL : Extraction, Analyse et Sauvegarde ---")
    all_found_articles = state.get("found_articles", [])
    if not all_found_articles:
        return {}

    # Déduplication des articles par URL
    unique_articles_list = list({article['url']: article for article in all_found_articles}.values())
    print(f"Traitement de {len(unique_articles_list)} articles uniques.")

    # Prompt pour le LLM
    analysis_prompt_template = """Vous êtes un analyste technologique mondial doublé d'un stratège pour l'Afrique. Pour l'article fourni, effectuez une analyse complète en deux temps : une analyse globale et neutre, puis une analyse stratégique spécifique à l'Afrique.

**Partie 1 : Analyse Globale (Neutre)**
1.  **Résumé Neutre :** Rédigez un résumé factuel et dense de l'article, de style journalistique (type agence de presse), strictement compris entre 700 et 800 caractères.
2.  **Problématique Générale :** Identifiez la problématique principale ou universelle soulevée.

**Partie 2 : Analyse Stratégique pour l'Afrique**
3.  **Impact sur l'Afrique :** Quel est l'impact direct ou indirect pour le continent ?
4.  **Problématique Spécifique à l'Afrique :** Quelle dépendance ou faiblesse cela révèle-t-il pour l'Afrique ?
5.  **Éveil de Conscience :** Quelle est la leçon critique pour les acteurs de la tech africaine ?
6.  **Piste d'Opportunité :** Quelle opportunité concrète cela crée-t-il ?
7.  **Score de Pertinence :** Attribuez un score de 1 à 10 sur l'importance de cette nouvelle pour l'Afrique.
    
Article à analyser : <article_text>{content}</article_text>"""

    analysis_prompt = ChatPromptTemplate.from_template(analysis_prompt_template)
    analysis_chain = analysis_prompt | llm.with_structured_output(veille_schema.ArticleAnalysis)

    db = state["db_session"]

    for article in unique_articles_list:
        article_data_for_crud = {**article}
        try:
            downloaded = trafilatura.fetch_url(article['url'])
            if not downloaded:
                article_data_for_crud["error"] = "Téléchargement échoué"
            else:
                content = trafilatura.extract(downloaded, favor_recall=True)
                metadata = trafilatura.extract_metadata(downloaded)
                date = metadata.date if metadata else "N/A"

                article_data_for_crud.update({
                    "date": str(date),
                    "content": content
                })

                if content and len(content) > 250:
                    try:
                        # Appel LLM
                        analysis_result_obj = analysis_chain.invoke({"content": content[:8000]})

                        # S'assurer que c'est bien un Pydantic Model avant model_dump
                        if isinstance(analysis_result_obj, veille_schema.ArticleAnalysis):
                            analysis_dict = analysis_result_obj.model_dump()
                        else:
                            analysis_dict = dict(analysis_result_obj)

                        article_data_for_crud["analysis"] = analysis_dict
                        article_data_for_crud["score_pertinence"] = analysis_dict.get("score_pertinence", 0)
                    except Exception as llm_error:
                        article_data_for_crud["error"] = f"Erreur du LLM: {llm_error}"
                else:
                    article_data_for_crud["error"] = "Contenu insuffisant"
        except Exception as e:
            article_data_for_crud["error"] = f"Erreur d'extraction: {e}"

        # Sauvegarde en base
        await crud_veille.create_or_update_article(db=db, article_data=article_data_for_crud)

    print(f"Traitement et sauvegarde terminés pour {len(unique_articles_list)} articles.")
    return {"status": "SUCCESS", "processed_articles": len(unique_articles_list)}


# --- Logique de Routage et Construction ---
async def should_continue(state: AgentState) -> str:
    return "continue_scraping" if state.get("current_site") else "end_scraping"

def create_langgraph_app():
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", plan_next_site)
    workflow.add_node("dispatcher", scraper_dispatcher)
    workflow.add_node("analyze_and_save", extract_analyze_and_save)
    workflow.set_entry_point("planner")
    workflow.add_conditional_edges("planner", should_continue, {"continue_scraping": "dispatcher", "end_scraping": "analyze_and_save"})
    workflow.add_edge("dispatcher", "planner")
    workflow.add_edge("analyze_and_save", END)
    return workflow.compile()

langgraph_app =  create_langgraph_app()

# --- Fonction principale du Service ---
async def run_veille_workflow(db: AsyncSession, query: str):
    initial_state = AgentState(
        db_session=db,
        query=query,
        sites_to_process=list(SCRAPER_REGISTRY.keys()),
        current_site="",
        found_articles=[],
    )
    
    print(f"Lancement du workflow de veille pour la requête : '{query}'")
    result = await langgraph_app.ainvoke(initial_state, recursion_limit=15)
    print("Workflow de veille terminé.")
    return result



# 1. Liste fixe de clusters prédéfinis
POSSIBLE_CLUSTERS = [
    "Souveraineté Numérique",
    "Propriété Intellectuelle",
    "Fintech Inclusive",
    "Éducation Numérique",
    "IA et Contenus Locaux",
    "Infrastructure Technologique",
    "Économie Numérique Africaine",
    "Cybersécurité et Gouvernance",
]

async def backfill_clusters_service(db: AsyncSession):
    """
    Service de backfill pour générer et assigner des clusters prédéfinis aux articles sans cluster.
    """
    print("--- Démarrage du service de backfill des clusters ---")

    # 2. Prompt contraint : le LLM doit choisir dans la liste
    cluster_prompt_template = f"""
    Tu es un expert en stratégie numérique africaine.
    J'ai défini une liste de clusters prédéfinis :

    {", ".join(POSSIBLE_CLUSTERS)}

    Analyse le texte suivant, puis choisis **uniquement un cluster de cette liste**
    qui correspond le mieux à la problématique décrite.

    Texte à analyser : "{{problematique_africaine}}"

    Réponds uniquement par un des clusters EXACTS ci-dessus.
    """
    cluster_prompt = ChatPromptTemplate.from_template(cluster_prompt_template)
    cluster_chain = cluster_prompt | llm | StrOutputParser()   # ton LLM déjà configuré

    # 3. Récupérer les articles sans cluster
    articles_to_process = await crud_veille.get_articles_without_cluster(db)
    print(f"Trouvé {len(articles_to_process)} articles à traiter pour le backfill.")

    updated_count = 0

    # 4. Itérer et mettre à jour
    for article in articles_to_process:
        if article.analysis and "problematique_africaine" in article.analysis:
            problematique = article.analysis["problematique_africaine"]

            response = await cluster_chain.ainvoke({"problematique_africaine": problematique})
            chosen_cluster = response.strip()


            if chosen_cluster not in POSSIBLE_CLUSTERS:
                print(f"[WARNING] Article {article.id} → Cluster invalide généré: {chosen_cluster}")
                continue

            # Mise à jour dans la DB
            await crud_veille.create_or_update_article(
                db,
                {"url": article.url, "sujet_cluster": chosen_cluster}
            )
            updated_count += 1
            print(f"Article {article.id} → Sujet cluster assigné: {chosen_cluster}")

    print(f"--- Backfill terminé : {updated_count} articles mis à jour. ---")
