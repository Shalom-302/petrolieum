## Configuration Sécurité

1. Installer HashiCorp Vault
2. Définir les variables d'environnement :
```bash
export VAULT_ADDR="http://vault:8200"
export VAULT_TOKEN="s.XXXXXX"
export AES_KEY="$(vault read -field=key encryption/aes-key)"
export FERNET_KEY="$(vault read -field=key encryption/fernet-key)"


Ce plugin fournit :

Chiffrement AES-256-GCM avec nonce aléatoire
Rotation automatique des clés via Vault
Middleware de sécurité HTTP renforcé
API de chiffrement/déchiffrement
Gestion centralisée des secrets



Système unifié de détection et réponse
Journalisation centralisée des événements
Double couche de sécurité :
Alerte précoce pour activité suspecte
Verrouillage automatique en cas d'attaque confirmée
Métadonnées enrichies pour les alertes
Configuration centralisée et modifiable

# Ordre d'exécution des middlewares :
graph TD
    A[CORS Middleware] --> B[SecurityMiddlewareEnhanced]
    B --> C[Gestion des requêtes]
    C --> D[Application des en-têtes de sécurité]


## 🍯 Honeypot System

Détecte les scanners automatisés et les attaquants passifs via :
- Endpoint `/decrypt-fake` camouflé
- Analyse comportementale des requêtes
- Fingerprinting des outils d'attaque
- Délais de réponse réalistes


## 🔍 Détection avancée

### Analyse de payloads :
- Injection SQL
- Cross-site scripting (XSS) 
- Injection de commandes
- Traversal de chemin
- Template injection

### Vérification des headers :
- User-Agent connus des outils d'attaque
- IP locales en X-Forwarded-For  
- Accept headers trop permissifs
- Absence des headers de sécurité critiques


## ⏱ Rate Limiting

Protection contre les attaques par force brute :
- `/decrypt` : 10 requêtes/minute
- `/decrypt-fake` : 2 requêtes/minute 
- Alerte automatique après 3 violations
- Blocage temporaire de l'IP (30min)

# Tester la limite
for i in {1..11}; do
  curl -X POST http://localhost:8000/plugins/security/decrypt \
    -d '{"encrypted":"..."}'
done


## 📜 Audit Logs - GDPR/HIPAA Compliance

### Features:
- End-to-end encrypted audit trails
- Automatic PII masking for GDPR
- PHI protection for HIPAA compliance
- Immutable log structure with cryptographic signatures

### Logged Events:
| Event Type        | Data Collected                  | Retention Period |
|-------------------|---------------------------------|------------------|
| Decryption        | User ID, IP, Success Status     | 365 days         |
| Auth Attempts     | Method, Success/Failure         | 180 days         |
| Config Changes    | Modified Settings, Author       | Permanent        |

### Verification Test:
```bash
curl -X POST http://localhost:8000/plugins/security/decrypt \
  -H "Content-Type: application/json" \
  -d '{"encrypted":"valid_data_here"}'
  
# Check audit logs
cat /var/log/security_audit.log | grep "ENCRYPTED_LOG_ENTRY"



## 🧪 Vulnerability Scanning

Configuration example for Trivy/ZAP:
```yaml
vulnerability_scanning:
  enabled: true
  schedule: "0 3 * * *"
  trivy:
    targets: ["/app", "package.json"]
  zap:
    target_url: "http://yourapp:8000"


# Scan Trivy
docker run --rm -v $(pwd):/app aquasec/trivy fs --severity HIGH,CRITICAL /app

# Scan OWASP ZAP
docker run --rm -v $(pwd):/zap/wrk owasp/zap2docker-stable zap-baseline.py \
  -t http://yourapp:8000 -g gen.conf -r zap_report.html



## 🔐 Authentification à Deux Facteurs (MFA)

### Activation du MFA :
```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" http://localhost:8000/plugins/security/mfa/setup
# Scannez le QR code avec Google Authenticator

curl -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"code": "<CODE>"}' http://localhost:8000/plugins/security/mfa/verify
```

### Désactivation :
```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" http://localhost:8000/plugins/security/mfa/disable
```

### Vérification :
```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" http://localhost:8000/plugins/security/mfa/verify
```

### Requête avec MFA :
```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" -H "X-MFA-Code: <CODE>" http://localhost:8000/plugins/security/decrypt
```


Checklist de validation ✅ :

Fonctionnalités de base :
[x] MFA avec génération QR Code et vérification OTP
[x] Gestion des sessions avec rotation de tokens
[x] Middleware de sécurité avec CSP et HSTS
[x] Journalisation chiffrée des audits
Sécurité renforcée :
[x] Cookies sécurisés (HttpOnly, Secure, SameSite Strict)
[x] Chiffrement AES-256 pour les tokens de session
[x] Validation des permissions en chaîne
[x] Protection contre le session hijacking
Intégrations :
[x] Compatibilité avec le système custom_auth existant
[x] Configuration centralisée via YAML
[x] Monitoring Prometheus intégré


# Tester le flux complet
docker-compose run --rm tests pytest \
  tests/security/test_mfa.py \
  tests/security/test_sessions.py \
  tests/security/test_middleware.py \
  -v --cov-report=html





  # Simuler une IP bloquée (ex: 192.168.0.1)
curl -H "X-Forwarded-For: 192.168.0.1" http://localhost:8000/api/test

# Vérifier les logs
tail -f /var/log/waf_threats.log