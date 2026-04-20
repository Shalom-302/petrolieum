"""
Script to correctly initialize Alembic migrations, taking into account
all plugins and templates available in the application.

Usage:
    python -m app.commands.init_migration

This script will:
1. Create an initial_schema migration that captures all models
2. Apply this migration to the database
"""
import os
import sys
import subprocess
import importlib
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from app.core.config import settings
from app.plugins.plugin_manager import load_plugins_into_app
from app.core.db import Base, engine


def get_backend_dir() -> Path:
    """Return the path to the backend directory."""
    return Path(__file__).resolve().parent.parent.parent


def run_alembic_command(command: List[str], env_vars=None) -> Tuple[str, str, int]:
    """
    Execute an alembic command with the correct environment variables.
    
    Args:
        command: The alembic command to execute
        env_vars: Additional environment variables
        
    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    # Check if we are already inside a Docker container
    in_docker = os.path.exists('/.dockerenv')
    backend_dir = get_backend_dir()
    
    # Configure the environment
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
        
    env["PYTHONPATH"] = str(backend_dir)
    
    # Use 'kaapi' as the container name for the database
    db_url = settings.DB_URL
    if "@db:" in db_url:
        db_url = db_url.replace("@db:", "@kaapi:")
    elif "@kaapi-db:" in db_url:
        db_url = db_url.replace("@kaapi-db:", "@kaapi:")
    env["DB_URL"] = db_url
    
    # Execute the command
    print(f"Executing: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(backend_dir),
        env=env
    )
    
    stdout, stderr = process.communicate()
    return stdout, stderr, process.returncode


def get_latest_migration_file():
    """Get the path to the latest migration file."""
    migrations_dir = get_backend_dir() / "migrations" / "versions"
    migration_files = list(migrations_dir.glob("*.py"))
    
    if not migration_files:
        return None
    
    # Sort by modification date to get the most recent
    latest_file = max(migration_files, key=lambda f: f.stat().st_mtime)
    return latest_file


def direct_fix_file(file_path):
    """Corrige directly the formatting of the file using a regular expression."""
    import re
    
    # Read the file completely
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Use a regular expression to locate and correct the problem precisely
    pattern = r'(# ### end Alembic commands ###)(def downgrade)'  # Group 1: marker, Group 2: function start
    
    if re.search(pattern, content):
        # Replace with the marker, followed by 3 line breaks, then the function start
        corrected_content = re.sub(pattern, r'\1\n\n\n\2', content)
        
        # Save the corrected content
        with open(file_path, 'w') as f:
            f.write(corrected_content)
        
        print(f"Formatting corrected with regex in file {file_path}")
        return True
    
    # Check for other possible variants of the problem
    alt_pattern = r'(# ### end Alembic commands ###)([^\n])'  # Marker followed directly by a character (no line break)
    
    if re.search(alt_pattern, content):
        # Add line breaks after the marker, then the content found
        corrected_content = re.sub(alt_pattern, r'\1\n\n\n\2', content)
        
        # Save the corrected content
        with open(file_path, 'w') as f:
            f.write(corrected_content)
        
        print(f"Formatting corrected (variant) with regex in file {file_path}")
        return True
    
    return False


def fix_migration_file(migration_file):
    """
    Cette fonction n'est plus utilisée car les commandes db preview, db generate et db apply 
    fonctionnent correctement. Conservée pour référence uniquement.
    """
    # Fonction conservée pour référence mais désactivée
    print("Note: fix_migration_file n'est plus utilisée car le processus de migration fonctionne correctement.")
    return


def auto_fix_migration_format(content):
    """Tries to correct common formatting issues in migration files."""
    import re
    
    # More robust detection of the common formatting issue
    pattern_downgrade_issue = r'(# ### end Alembic commands ###)def downgrade\(\)'
    if re.search(pattern_downgrade_issue, content):
        print("Problem detected: 'def downgrade()' is attached to Alembic comments.")
        # Direct correction with ample space to avoid problems
        content = content.replace(
            '# ### end Alembic commands ###def downgrade()',
            '# ### end Alembic commands ###\n\n\ndef downgrade()'
        )
        print("Correction applied for the format of 'def downgrade()'")
    
    # Case 1: Other variants where a 'def' is attached to the end of comments
    content = re.sub(r'(# ### end .*?commands ###)def', r'\1\n\n\ndef', content)
    
    # Case 2: Missing spaces or tabs for indentation
    lines = content.split('\n')
    for i in range(len(lines)):
        if lines[i].lstrip().startswith('op.') and not lines[i].startswith('    '):
            lines[i] = '    ' + lines[i].lstrip()
    content = '\n'.join(lines)
    
    # Case 3: Detect if the file contains upgrade and downgrade but without correct formatting
    if 'def upgrade()' in content and 'def downgrade()' in content:
        upgrade_index = content.find('def upgrade()')
        downgrade_index = content.find('def downgrade()')
        
        if upgrade_index > 0 and downgrade_index > upgrade_index:
            # The file contains the two functions in the correct order, but may be poorly formatted
            header = content[:upgrade_index].strip()
            between_funcs = content[upgrade_index:downgrade_index].strip()
            remainder = content[downgrade_index:].strip()
            
            # Reconstruct with correct formatting
            content = f"{header}\n\ndef upgrade() -> None:\n{between_funcs[len('def upgrade() -> None:'):].strip()}\n\n\ndef downgrade() -> None:\n{remainder[len('def downgrade() -> None:'):].strip()}"
    
    return content


def generate_models_script(migration_file):
    """Modifies the migration file to include the complete schema of existing tables."""
    from sqlalchemy import MetaData, Table
    from sqlalchemy.schema import CreateTable
    
    # Inspect the database to get the complete schema
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    # Generate CreateTable declarations for each table
    create_statements = []
    for table_name in sorted(metadata.tables):
        table = metadata.tables[table_name]
        create_statement = str(CreateTable(table).compile(engine))
        # Format for Python
        create_statement = create_statement.replace('\n', ' ').replace("'", "\\'").replace('"', '\\"')
        create_statements.append(f"    op.execute(\"\"\"CREATE TABLE IF NOT EXISTS {table_name} ({create_statement[len(f'CREATE TABLE {table_name} ('):]}\"\"\")")  
    
    # Read the existing file content
    with open(migration_file, 'r') as f:
        content = f.read()
    
    # Replace the existing upgrade() function with our instructions
    upgrade_content = "def upgrade() -> None:\n    # ### commands auto generated by init_migration ###\n"
    upgrade_content += "\n".join(create_statements)
    upgrade_content += "\n    # ### end of commands ###\n"
    
    # Search and replace the existing upgrade() function
    import re
    pattern = r"def upgrade\(\).*?def downgrade\(\)"
    replacement = upgrade_content + "\n\ndef downgrade()"
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write the modified content to the file
    with open(migration_file, 'w') as f:
        f.write(new_content)


# Import global models to ensure they are all loaded
from app.models import *

def import_all_models():
    """
    Ensures that all models defined in the application are loaded,
    including those defined in plugins.
    """
    
    # Create a dummy FastAPI app for plugin loading
    from fastapi import FastAPI
    dummy_app = FastAPI()
    # Explicitly load plugins to ensure their models are imported
    load_plugins_into_app(dummy_app)
    
    # Verify loaded models
    print(f"SQLAlchemy models loaded: {len(Base.metadata.tables)}")
    print("Tables detected:")
    for table_name in sorted(Base.metadata.tables.keys()):
        print(f"  - {table_name}")


def update_db_references_in_docker():
    """
    Updates references to 'db' to use 'kaapi' in the Docker container.
    """
    # Check if we are in Docker
    in_docker = os.path.exists('/.dockerenv')
    if not in_docker:
        return
        
    # Update /etc/hosts to point db to kaapi (localhost)
    try:
        with open('/etc/hosts', 'r') as f:
            hosts_content = f.read()
            
        if 'db' not in hosts_content:
            with open('/etc/hosts', 'a') as f:
                f.write('\n127.0.0.1 db\n')
            print("✅ Added 'db' in /etc/hosts to point to localhost")
    except Exception as e:
        print(f"⚠️ Failed to update /etc/hosts: {str(e)}")


def init_migration():
    """
    Initializes the Alembic migration by recreating the entire database.
    
    Returns:
        bool: True if initialization is successful, False otherwise
    """
    # Update database references in Docker
    update_db_references_in_docker()
    
    # Ensure all models are imported
    import_all_models()
    
    # Step 1: Delete all old revisions for a clean start
    versions_dir = get_backend_dir() / "migrations" / "versions"
    for file in versions_dir.glob("*.py"):
        if file.name != "__init__.py":
            print(f"Deletion of old revision: {file.name}")
            file.unlink()
    
    # Simple approach: empty the database, create tables, then generate an initial migration
    from sqlalchemy import text
    
    try:
        # Use the database connection
        print("\n1. Emptying the database...")
        conn = engine.connect()
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        
        # Disable foreign key constraints during operations
        conn.execute(text("SET session_replication_role = 'replica';"))
        
        # Delete all existing tables with CASCADE
        conn.execute(text("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = current_schema()) LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
        """))
        
        # Delete also existing sequences
        conn.execute(text("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT sequencename FROM pg_sequences WHERE schemaname = current_schema()) LOOP
                EXECUTE 'DROP SEQUENCE IF EXISTS ' || quote_ident(r.sequencename) || ' CASCADE';
            END LOOP;
        END $$;
        """))
        
        # Re-enable foreign key constraints
        conn.execute(text("SET session_replication_role = 'origin';"))
        
        conn.close()
        print("Database completely emptied.")
        
        # 5. Create tables directly with SQLAlchemy
        print("\n2. Creating tables via SQLAlchemy...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
        
        # 6. Initialize Alembic to recognize the current state as base
        print("\n3. Initializing Alembic with the current state...")
        
        # 6.1 - Create an initial revision
        stdout, stderr, return_code = run_alembic_command(["alembic", "revision", "--autogenerate", "-m", "initial schema"])
        if return_code != 0:
            print(f"Error during revision generation: {stderr}")
            sys.exit(1)
        print("Initial migration generation successful.")
        
        # 6.2 - Correct the migration content directly with Python
        migration_file = get_latest_migration_file()
        if migration_file:
            print(f"Migration file found: {migration_file}")
            
            # Create a new migration file
            print("Creating a custom migration file with correct format...")
            
            # Wait for the file to be completely written
            import time
            time.sleep(1)
            
            try:
                # Extract important information
                # Convert PosixPath object to string
                migration_file_str = str(migration_file)
                revision_id = migration_file_str.split("/")[-1].split("_")[0]
                migration_name = "initial_schema"
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                
                # Read the current content to extract important parts (tables created and deleted)
                # We can use the Path object directly with open()
                with open(migration_file, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Use a more secure approach to extract upgrade/downgrade blocks
                import re
                
                # Search for content between def upgrade() and # ### end Alembic commands ###
                upgrade_match = re.search(r'def upgrade\(\)[^#]*?(# ### commands auto generated by Alembic.*?# ### end Alembic commands ###)', original_content, re.DOTALL)
                upgrade_body = ""
                if upgrade_match:
                    upgrade_body = upgrade_match.group(1)
                
                # Search for content between def downgrade() and # ### end Alembic commands ###
                downgrade_match = re.search(r'def downgrade\(\)[^#]*?(# ### commands auto generated by Alembic.*?# ### end Alembic commands ###)', original_content, re.DOTALL)
                downgrade_body = ""
                if downgrade_match:
                    downgrade_body = downgrade_match.group(1)
                
                # If we haven't found the bodies, use default values
                if not upgrade_body:
                    upgrade_body = "    # ### commands auto generated by Alembic - please adjust! ###\n    pass\n    # ### end Alembic commands ###"
                
                if not downgrade_body:
                    downgrade_body = "    # ### commands auto generated by Alembic - please adjust! ###\n    pass\n    # ### end Alembic commands ###"
                
                # Create a new file content avoiding multiline f-strings
                new_content = (
                    f'"""{migration_name}\n\n'
                    f'Revision ID: {revision_id}\n'
                    f'Revises: \n'
                    f'Create Date: {timestamp}\n\n"""\n'
                    'from typing import Sequence, Union\n\n'
                    'from alembic import op\n'
                    'import sqlalchemy as sa\n\n\n'
                    '# revision identifiers, used by Alembic.\n'
                    f"revision = '{revision_id}'\n"
                    'down_revision = None\n'
                    'branch_labels = None\n'
                    'depends_on = None\n\n\n'
                    'def upgrade() -> None:\n'
                    f'{upgrade_body}\n\n\n'
                    'def downgrade() -> None:\n'
                    f'{downgrade_body}'
                )
                
                # Write the new content to the file
                # The PosixPath object works directly with open()
                with open(migration_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                # Note: fix_migration_file est désactivée car elle n'est plus nécessaire
                print("Migration écrite avec le bon format pour les fonctions upgrade et downgrade.")
                
                
            except Exception as e:
                print(f"Error during migration file correction: {str(e)}")
                return False
        else:
            print("No migration file found.")
            return False
        
        # 6.3 - Mark the database as being up-to-date without trying to create tables (since they already exist)
        stdout, stderr, return_code = run_alembic_command(["alembic", "stamp", "head"])
        if return_code != 0:
            print(f"Error during database marking as up-to-date: {stderr}")
            return False
            
        print("Database marked as up-to-date with Alembic migrations.")
            
    except Exception as e:
        print(f"Error during database initialization: {str(e)}")
        return False
    
    print("\n✅ Migration initialization completed")
    print("The database is now synchronized with the models")
    return True


if __name__ == "__main__":
    success = init_migration()
    if not success:
        sys.exit(1)
