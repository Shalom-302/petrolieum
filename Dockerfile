# ===================================================================
# STAGE 1: Le "Builder" - Optimisé pour le cache pip
# ===================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Installer les dépendances système
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Mettre à jour pip
RUN pip install --upgrade pip

# Copier UNIQUEMENT les fichiers de dépendances
COPY requirements.txt .
COPY install_plugin_requirements.py .

# Installer les dépendances. Cette couche sera maintenant correctement mise en cache !
# Si requirements.txt ne change pas, cette étape sera sautée.
# Si requirements.txt change, pip installera SEULEMENT les nouvelles dépendances.
RUN pip install --no-cache-dir -r requirements.txt
RUN python install_plugin_requirements.py


# ===================================================================
# STAGE 2: L'image Finale - Légère
# ===================================================================
FROM python:3.11-slim

WORKDIR /app

# Installer UNIQUEMENT les dépendances système nécessaires à l'exécution
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copier les paquets Python pré-installés depuis le "builder"
# C'est beaucoup plus efficace que de recréer un venv.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Définir les variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Copier le code source de l'application
COPY . .

# Exposer le port
EXPOSE 8000

# Commande par défaut
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]