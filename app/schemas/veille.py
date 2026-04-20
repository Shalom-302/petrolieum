from pydantic import BaseModel, Field, ConfigDict


class ArticleAnalysis(BaseModel): # Updated with all fields from your script
    """
    Schéma de la sortie structurée attendue du LLM pour l'analyse d'un article.
    """
    impact_afrique: str = Field(description="L'impact direct ou indirect de cet événement sur l'Afrique.")
    problematique_africaine: str = Field(description="La problématique de fond que cela révèle pour le continent.")
    eveil_de_conscience: str = Field(description="La leçon critique, le 'wake-up call' pour l'Afrique.")
    piste_opportunite: str = Field(description="Une idée d'opportunité concrète pour l'écosystème tech africain.")
    type_evenement: str = Field(description="Ex: 'Faillite', 'Lancement de produit', 'Tendance'")
    resume_strategique: str = Field(description="Résumé de l'événement et son importance.")
    lecon_a_retenir: str = Field(description="Le conseil principal à tirer de cet événement.")
    impact_potentiel: str = Field(description="L'impact potentiel sur l'industrie.")
    score_pertinence: int = Field(description="Un score de 1 à 10 indiquant l'importance de cet éveil de conscience pour l'Afrique. 10 est critique.", ge=1, le=10)
    sujet_cluster: str | None = Field(description="Catégorise l'article en 3-5 mots-clés (ex: 'Régulation Fintech', 'Sécurité des Paiements', 'E-commerce et Logistique'). Ce champ est essentiel pour le regroupement.", default=None)
    resume_neutre: str = Field(description="Un résumé factuel et dense de l'article, de style journalistique (type agence de presse), strictement compris entre 700 et 800 caractères.")
    problematique_generale: str = Field(description="La problématique principale ou universelle soulevée par l'article.")


class ArticleBase(BaseModel):
    """
    Schéma de base pour un article.
    """
    url: str
    title: str
    source: str


class ArticleResponse(ArticleBase):
    """
    Schéma de réponse de l'API pour un article, incluant les données d'analyse.
    """
    id: int
    published: bool
    type_evenement: str | None = None
    date: str | None = None
    score_pertinence: int | None = None
    analysis: ArticleAnalysis | None = None
    error: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PublishStatusUpdate(BaseModel):
    """
    Schéma pour la mise à jour du statut de publication d'un article.
    """
    published: bool

class TriggerVeilleRequest(BaseModel):
    query: str