"""
Debug script to diagnose GitHub authentication.
"""
import os
from pathlib import Path
import logging

# Configuring logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check .env file
env_path = Path(__file__).parent / ".env"
logger.info(f"Checking .env file at: {env_path}")
if env_path.exists():
    logger.info("👍 .env file exists")
else:
    logger.error("❌ .env file does not exist")

# Check GitHub variables
github_client_id = os.getenv("GITHUB_CLIENT_ID")
github_client_secret = os.getenv("GITHUB_CLIENT_SECRET")

logger.info(f"GITHUB_CLIENT_ID set: {bool(github_client_id)}")
logger.info(f"GITHUB_CLIENT_SECRET set: {bool(github_client_secret)}")

# Log to help configure a new GitHub OAuth account
logger.info("\n=== To configure GitHub OAuth ===")
logger.info("1. Go to https://github.com/settings/applications/new")
logger.info("2. Register a new OAuth application:")
logger.info("   - Application name: Simple Kaapi")
logger.info("   - Application URL: http://localhost:3000")
logger.info("   - Description: Application de gestion de café (facultatif)")
logger.info("   - Callback URL: http://localhost:3000/oauth/callback")
logger.info("3. Once created, copy the Client ID and generate a new Client Secret")
logger.info("4. Add the following lines to your .env file:")
logger.info("GITHUB_CLIENT_ID=<votre-client-id>")
logger.info("GITHUB_CLIENT_SECRET=<votre-client-secret>")
logger.info("5. Restart your application")
