"""
Initialize storage providers for the application.
This command creates the MinIO storage provider and sets it as the default.
Uses direct SQL operations for simplicity and reliability.
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from sqlalchemy import create_engine
from app.core.config import settings
from sqlalchemy.orm import declarative_base, scoped_session
from sqlalchemy.orm.session import sessionmaker

engine = create_engine(settings.DB_URL)
Base = declarative_base()

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine)

def create_sql_commands(
    endpoint_url: str,
    bucket_name: str,
    access_key: str = "minioadmin",
    secret_key: str = "minioadmin",
    region: str = None,
    secure: bool = False,
    public_endpoint_url: str = None,
    force: bool = False
) -> str:
    """
    Generate SQL commands to initialize MinIO provider
    
    Args:
        endpoint_url: MinIO server endpoint URL
        bucket_name: Bucket name
        access_key: MinIO access key
        secret_key: MinIO secret key
        region: Region (optional)
        secure: Whether to use HTTPS
        public_endpoint_url: Public endpoint URL for direct access to files
        force: Whether to force recreation if exists
    
    Returns:
        SQL commands as a string
    """
    # Current timestamp for created_at and updated_at
    now = datetime.utcnow().isoformat()
    
    # Config options as JSON string
    config_options = json.dumps({
        "secure": secure,
        "public_endpoint_url": public_endpoint_url if public_endpoint_url else None
    })
    
    # SQL to check if MinIO provider exists
    check_sql = "SELECT id, is_default FROM file_storage_providers WHERE provider_type = 'minio';"
    
    # SQL to unset default on all providers
    unset_default_sql = "UPDATE file_storage_providers SET is_default = FALSE;"
    
    # SQL to delete existing MinIO provider if force is True
    delete_sql = "DELETE FROM file_storage_providers WHERE provider_type = 'minio';"
    
    # SQL to create new MinIO provider
    insert_sql = f"""
    INSERT INTO file_storage_providers (
        name, provider_type, is_default, is_active, bucket_name, region, 
        endpoint_url, access_key, secret_key, config_options, created_at, updated_at
    ) VALUES (
        'MinIO Storage', 'minio', TRUE, TRUE, '{bucket_name}', {repr(region) if region else 'NULL'}, 
        '{endpoint_url}', '{access_key}', '{secret_key}', '{config_options}', '{now}', '{now}'
    ) RETURNING id;
    """
    
    # SQL to set existing provider as default
    set_default_sql = "UPDATE file_storage_providers SET is_default = TRUE WHERE id = $PROVIDER_ID;"
    
    # Combined SQL script with conditional logic using DO blocks
    combined_sql = f"""
    -- Begin transaction
    BEGIN;
    
    -- Check if MinIO provider exists
    {check_sql}
    
    -- Use DO block for conditional logic
    DO $$
    DECLARE
        minio_provider record;
        should_create boolean := TRUE;
    BEGIN
        -- Get existing MinIO provider if any
        SELECT id, is_default INTO minio_provider FROM file_storage_providers 
        WHERE provider_type = 'minio' LIMIT 1;
        
        -- If provider exists and force is false, just set as default if needed
        IF minio_provider.id IS NOT NULL AND {str(force).lower()} = FALSE THEN
            should_create := FALSE;
            
            -- If not default, make it default
            IF minio_provider.is_default = FALSE THEN
                -- Unset defaults
                UPDATE file_storage_providers SET is_default = FALSE;
                
                -- Set this one as default
                UPDATE file_storage_providers SET is_default = TRUE WHERE id = minio_provider.id;
                
                RAISE NOTICE 'Set existing MinIO provider as default';
            ELSE
                RAISE NOTICE 'MinIO provider is already default';
            END IF;
        END IF;
        
        -- If force is true and provider exists, delete it
        IF {str(force).lower()} = TRUE AND minio_provider.id IS NOT NULL THEN
            DELETE FROM file_storage_providers WHERE provider_type = 'minio';
            RAISE NOTICE 'Deleted existing MinIO provider';
        END IF;
        
        -- Create new provider if needed
        IF should_create = TRUE OR {str(force).lower()} = TRUE THEN
            -- Unset all defaults first
            UPDATE file_storage_providers SET is_default = FALSE;
            
            -- Create new provider
            INSERT INTO file_storage_providers (
                name, provider_type, is_default, is_active, bucket_name, region, 
                endpoint_url, access_key, secret_key, config_options, created_at, updated_at
            ) VALUES (
                'MinIO Storage', 'minio', TRUE, TRUE, '{bucket_name}', {repr(region) if region else 'NULL'}, 
                '{endpoint_url}', '{access_key}', '{secret_key}', '{config_options}', '{now}', '{now}'
            );
            
            RAISE NOTICE 'Created new MinIO provider';
        END IF;
    END;
    $$;
    
    -- Commit the transaction
    COMMIT;
    """
    
    return combined_sql

def update_storage_provider_public_url():
    """Update the public URL for the existing MinIO provider"""
    db = SessionLocal()
    try:
        provider = db.query(StorageProvider).filter(
            StorageProvider.provider_type == "minio",
            StorageProvider.is_default == True
        ).first()
        
        if not provider:
            logger.error("No MinIO provider found")
            return
        
        # Load existing configuration
        try:
            config = json.loads(provider.config)
        except:
            config = {}
        
        # Add or update the public URL
        config["public_endpoint_url"] = "http://localhost:9000"
        
        # Save the updated configuration
        provider.config = json.dumps(config)
        db.commit()
        
        logger.info(f"Public URL updated for provider ID {provider.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating public URL: {str(e)}")
    finally:
        db.close()

def main():
    """
    Main function to execute the initialization
    """
    parser = argparse.ArgumentParser(description="Init Storage Provider")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Commande init
    init_parser = subparsers.add_parser("init", help="Initialize MinIO storage provider")
    init_parser.add_argument("--endpoint", default="minio:9000", help="MinIO endpoint URL")
    init_parser.add_argument("--bucket", default="files", help="MinIO bucket name")
    init_parser.add_argument("--access-key", default="minioadmin", help="MinIO access key")
    init_parser.add_argument("--secret-key", default="minioadmin", help="MinIO secret key")
    init_parser.add_argument("--region", default="", help="MinIO region")
    init_parser.add_argument("--secure", action="store_true", help="Use HTTPS for MinIO")
    init_parser.add_argument("--public-endpoint", default="http://localhost:9000", help="Public URL for MinIO")
    init_parser.add_argument("--force", action="store_true", help="Force recreate provider if exists")
    
    # Commande update-public-url
    subparsers.add_parser("update-public-url", help="Update the public URL for MinIO provider")
    
    args = parser.parse_args()
    
    if args.command == "init":
        sql_commands = create_sql_commands(
            endpoint_url=args.endpoint,
            bucket_name=args.bucket,
            access_key=args.access_key,
            secret_key=args.secret_key,
            region=args.region,
            secure=args.secure,
            public_endpoint_url=args.public_endpoint,
            force=args.force
        )
        
        # Write SQL to a file that can be executed by the calling script
        with open('/tmp/init_minio.sql', 'w') as f:
            f.write(sql_commands)
        
        logger.info("SQL commands generated and written to /tmp/init_minio.sql")
        print("SUCCESS")
        sys.exit(0)
    elif args.command == "update-public-url":
        update_storage_provider_public_url()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
