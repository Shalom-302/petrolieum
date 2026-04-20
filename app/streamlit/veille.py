import streamlit as st
import requests
import json
from typing import Dict, Any

# --- Configuration de la Page ---
st.set_page_config(page_title="Dashboard de Veille", layout="wide")

# --- URL de l'API ---
FASTAPI_BASE_URL = "http://localhost:8000"

# --- Fonctions d'aide ---
def format_key(key_string):
    """Transforme une clé_snake_case en Titre lisible."""
    return ' '.join(word.capitalize() for word in key_string.split('_'))

@st.cache_data(ttl=600) # Mettre en cache la liste des clusters pendant 10 minutes
def get_available_clusters():
    """Récupère la liste des clusters disponibles depuis l'API."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/api/veille/clusters")
        if response.status_code == 200:
            return ["Tous"] + response.json()
        return ["Tous"]
    except requests.exceptions.ConnectionError:
        return ["Tous"]

# --- Interface Principale ---
st.title("📊 Dashboard de Veille Technologique")
st.info("Ce dashboard appelle directement les routes de l'API sans authentification pour le test.")

# --- Section 1: Lancer une nouvelle veille ---
with st.expander("🚀 Lancer une nouvelle veille", expanded=False):
    veille_query = st.text_input("Sujet de la veille", "Tendances IA en Afrique")
    if st.button("Démarrer la veille"):
        endpoint = f"{FASTAPI_BASE_URL}/api/veille/run"
        try:
            with st.spinner("Lancement de la tâche de veille en arrière-plan..."):
                response = requests.post(endpoint, params={"query": veille_query})
                if response.status_code == 202:
                    st.success(f"✅ {response.json().get('message')}")
                else:
                    st.error(f"❌ Erreur: {response.status_code}")
                    st.json(response.json())
        except requests.exceptions.ConnectionError as e:
            st.error(f"🔌 Impossible de se connecter à l'API. Détails: {e}")

# --- Section 2: Afficher les articles collectés ---
st.header("📚 Articles Collectés")

# Filtres
clusters = get_available_clusters()

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    selected_cluster = st.selectbox("Filtrer par Sujet (Cluster)", clusters)
with col2:
    published_status = st.selectbox("Filtrer par Statut", ["Tous", "Publiés", "Non publiés"])
with col3:
    min_score = st.slider("Filtrer par Score de Pertinence Minimum", 1, 10, 1)

if st.button("🔄 Rafraîchir les articles", use_container_width=True):
    # On type explicitement le dictionnaire pour que Pylance accepte plusieurs types de valeurs
    params: Dict[str, Any] = {"score_min": min_score}
    if published_status == "Publiés":
        params["published"] = True
    elif published_status == "Non publiés":
        params["published"] = False
    
    if selected_cluster != "Tous":
        params["cluster"] = selected_cluster
    endpoint = f"{FASTAPI_BASE_URL}/api/veille/articles"
    try:
        response = requests.get(endpoint, params=params)
        if response.status_code == 200:
            st.session_state['articles'] = response.json()
        else:
            st.error(f"❌ Erreur lors de la récupération: {response.status_code}")
            st.json(response.json())
            st.session_state['articles'] = []
    except requests.exceptions.ConnectionError as e:
        st.error(f"🔌 Impossible de se connecter à l'API. Détails: {e}")
        st.session_state['articles'] = []

# Afficher les articles depuis le session_state
if 'articles' in st.session_state and st.session_state['articles']:
    articles = st.session_state['articles']
    st.success(f"🔍 {len(articles)} article(s) trouvé(s).")
    
    for article in articles:
        with st.container(border=True):
            col_info, col_action = st.columns([4, 1])
            
            with col_info:
                st.markdown(f"##### <span style='color: #28a745;'>Score: {article.get('score_pertinence', 'N/A')}/10</span> | {article['title']}", unsafe_allow_html=True)
                st.caption(f"Cluster: {article.get('sujet_cluster', 'Non défini')} | Source: {article['source']} | Date: {article.get('date', 'N/A')}")
                st.markdown(f"[Lire l'article original]({article['url']})", unsafe_allow_html=True)

            with col_action:
                is_published = article['published']
                button_text = "✅ Dépublier" if is_published else "▶️ Publier"
                button_type = "secondary" if is_published else "primary"
                
                if st.button(button_text, key=f"pub_{article['id']}", use_container_width=True, type=button_type):
                    pub_endpoint = f"{FASTAPI_BASE_URL}/api/veille/articles/{article['id']}/publish"
                    try:
                        pub_response = requests.post(pub_endpoint, json={"published": not is_published})
                        if pub_response.status_code == 200:
                            st.success("Statut mis à jour !")
                            st.rerun()
                        else:
                            st.error(f"Erreur: {pub_response.text}")
                    except requests.exceptions.ConnectionError:
                        st.error("API non joignable.")

            if article.get('analysis'):
                with st.expander("🧠 Voir l'analyse stratégique"):
                    # Also display sujet_cluster inside the analysis if it exists
                    if 'sujet_cluster' in article['analysis'] and article['analysis']['sujet_cluster']:
                         st.markdown(f"**Sujet Cluster**")
                         st.markdown(f"> {article['analysis']['sujet_cluster']}")

                    for key, value in article['analysis'].items():
                        if value and key != 'sujet_cluster': # Avoid duplicating the cluster
                            st.markdown(f"**{format_key(key)}**")
                            st.markdown(f"> {value}")
else:
    st.info("Cliquez sur 'Rafraîchir les articles' pour charger les données.")