# Audit et Suivi du Projet - Mini ERP Pétrolier (kaapi-shalom)

Date de création : 15 Avril 2026
État : En cours de développement

## 1. Structure du Projet
- [x] Modèles de base (Product, Client, Purchase, Sale, StockMovement, Storage)
- [x] CRUD de base (Petro)
- [x] Services (Logique métier achats/ventes/stock)
- [x] Routers (Endpoints API initiaux)

## 2. Authentification et Autorisation (Advanced Auth)
- [x] Intégration de `get_current_user` dans les routes `petroleum`
- [x] Gestion des rôles :
    - **Boss** : Accès total, dashboards, gestion des utilisateurs.
    - **Employers** : Gestion des achats, ventes, clients.
    - **Operateurs Stations** : Saisie des données de vente, consultation stock local.
- [ ] Protection Granulaire (Casbin / RBAC) - *Note: Utilisation de require_role pour l'instant*

## 3. Scalabilité et Performance
- [x] Implémentation de la pagination sur les listes (Achats, Ventes, Produits)
- [ ] Optimisation des requêtes de stock
- [ ] Découpage modulaire (Plugins)

## 4. Prochaines Étapes
1. [x] Sécuriser les routes dans `app/routers/petro.py` avec `get_current_user`.
2. [x] Implémenter la logique de pagination dans le CRUD de base (Produits, Ventes, Achats).
3. [ ] Finaliser la gestion des Clients avec pagination et protection.
4. [ ] Ajouter des logs d'audit pour les actions critiques (ventes, annulations) via le plugin `advanced_audit`.
5. [ ] Valider la gestion des tokens et le rafraîchissement.

---
*Note: Ce fichier sert de journal de bord pour la coordination du projet.*
