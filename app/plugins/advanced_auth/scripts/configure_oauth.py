#!/usr/bin/env python
"""
OAuth configuration script for the advanced authentication plugin.

This script helps configure OAuth providers by setting up client IDs and secrets.
"""
import os
import sys
import logging
import argparse
import json
from pathlib import Path
from typing import Dict, Any

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).resolve().parents[5]))

import dotenv
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.plugins.advanced_auth.config import get_auth_config


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def save_oauth_config(provider: str, client_id: str, client_secret: str, env_file: str = None) -> None:
    """
    Save OAuth provider configuration to environment variables or .env file.
    
    Args:
        provider: Name of the provider (e.g., 'github', 'google')
        client_id: OAuth client ID
        client_secret: OAuth client secret
        env_file: Path to .env file to update (optional)
    """
    # Normalize provider name
    provider = provider.lower()
    
    # Define environment variable names
    client_id_var = f"{provider.upper()}_CLIENT_ID"
    client_secret_var = f"{provider.upper()}_CLIENT_SECRET"
    
    if env_file:
        # Update .env file
        env_path = Path(env_file)
        if not env_path.exists():
            logger.warning(f"Environment file {env_file} does not exist. Creating it.")
            env_path.touch()
        
        # Load existing variables
        dotenv.load_dotenv(env_file)
        
        # Update variables
        dotenv.set_key(env_file, client_id_var, client_id)
        dotenv.set_key(env_file, client_secret_var, client_secret)
        
        logger.info(f"Updated {env_file} with {provider} OAuth credentials")
    else:
        # Just set environment variables for this session
        os.environ[client_id_var] = client_id
        os.environ[client_secret_var] = client_secret
        
        logger.info(f"Set {provider} OAuth environment variables for this session")


def list_providers() -> None:
    """List all supported OAuth providers."""
    providers = [
        {"name": "github", "description": "GitHub OAuth provider"},
        {"name": "google", "description": "Google OAuth provider"},
        {"name": "facebook", "description": "Facebook OAuth provider (not implemented yet)"},
        {"name": "microsoft", "description": "Microsoft OAuth provider (not implemented yet)"},
        {"name": "apple", "description": "Apple OAuth provider (not implemented yet)"},
        {"name": "linkedin", "description": "LinkedIn OAuth provider (not implemented yet)"}
    ]
    
    print("\nSupported OAuth Providers:")
    print("-------------------------")
    for provider in providers:
        print(f"- {provider['name']}: {provider['description']}")
    
    print("\nCurrently Configured Providers:")
    print("-----------------------------")
    auth_config = get_auth_config()
    for name, config in auth_config.OAUTH_PROVIDERS.items():
        client_id = config.get("client_id")
        if client_id:
            print(f"- {name}: Client ID is configured")
        else:
            print(f"- {name}: Not configured")


def setup_provider_interactive(provider: str, env_file: str = None) -> None:
    """
    Set up an OAuth provider interactively.
    
    Args:
        provider: Name of the provider
        env_file: Path to .env file to update (optional)
    """
    print(f"\nConfiguring {provider} OAuth provider")
    print("----------------------------------")
    
    client_id = input(f"Enter {provider} Client ID: ")
    client_secret = input(f"Enter {provider} Client Secret: ")
    
    if not client_id or not client_secret:
        print("Error: Client ID and Client Secret are required.")
        return
    
    save_oauth_config(provider, client_id, client_secret, env_file)
    print(f"\n{provider} OAuth provider configured successfully!")


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Configure OAuth providers")
    parser.add_argument("--list", action="store_true", help="List all supported OAuth providers")
    parser.add_argument("--provider", type=str, help="Provider to configure (e.g., github, google)")
    parser.add_argument("--client-id", type=str, help="OAuth Client ID")
    parser.add_argument("--client-secret", type=str, help="OAuth Client Secret")
    parser.add_argument("--env-file", type=str, default=".env", help="Path to .env file to update")
    args = parser.parse_args()
    
    if args.list:
        list_providers()
        return
    
    if args.provider:
        provider = args.provider.lower()
        if args.client_id and args.client_secret:
            save_oauth_config(provider, args.client_id, args.client_secret, args.env_file)
            logger.info(f"{provider} OAuth provider configured successfully!")
        else:
            setup_provider_interactive(provider, args.env_file)
    else:
        print("Please specify a provider with --provider or use --list to see all providers")
        parser.print_help()


if __name__ == "__main__":
    main()
