"""
Script to preview migration changes without applying them.
This script creates a temporary migration and displays the changes that would be applied.

Usage:
    python -m app.commands.preview_migration
"""
import os
import sys
import subprocess
import uuid
import re
from pathlib import Path

from app.core.config import settings
from app.commands.init_migration import get_backend_dir, run_alembic_command


def preview_migration():
    """
    Generates a temporary migration to preview changes.
    """
    # Generate a temporary migration ID
    temp_id = str(uuid.uuid4())[:8]
    temp_message = f"temp_preview_{temp_id}"
    
    try:
        # Generate a temporary migration
        print("Generating a temporary migration to preview changes...")
        stdout, stderr, return_code = run_alembic_command(["alembic", "revision", "--autogenerate", "-m", temp_message])
        
        if return_code != 0:
            print(f"Error generating migration: {stderr}")
            return False
        
        # Trouver le fichier de migration temporaire
        versions_dir = get_backend_dir() / "migrations" / "versions"
        temp_file = None
        
        for file in versions_dir.glob("*.py"):
            if temp_message in file.name:
                temp_file = file
                break
        
        if not temp_file:
            print("No temporary migration file found.")
            return False
        
        # Read and display the content of the migration file
        print("\n" + "=" * 80)
        print(f"CHANGES TO BE APPLIED:")
        print("=" * 80)
        
        with open(temp_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Extract upgrade() and downgrade() functions
            upgrade_match = re.search(r'def upgrade\(\).*?:(.+?)(?=def downgrade|\Z)', content, re.DOTALL)
            downgrade_match = re.search(r'def downgrade\(\).*?:(.+?)(?=\Z)', content, re.DOTALL)
            
            if upgrade_match:
                print("\nUPGRADE OPERATIONS:")
                print("-" * 80)
                upgrade_content = upgrade_match.group(1).strip()
                if upgrade_content:
                    print(upgrade_content)
                else:
                    print("No upgrade operations.")
            
            if downgrade_match:
                print("\nDOWNGRADE OPERATIONS:")
                print("-" * 80)
                downgrade_content = downgrade_match.group(1).strip()
                if downgrade_content:
                    print(downgrade_content)
                else:
                    print("No downgrade operations.")
        
        print("\n" + "=" * 80)
        print("END OF PREVIEW")
        print("=" * 80)
        
        # Delete the temporary migration file
        print(f"\nDeleting temporary migration file: {temp_file.name}")
        temp_file.unlink()
        
        return True
    
    except Exception as e:
        print(f"Error during migration preview: {str(e)}")
        return False


if __name__ == "__main__":
    success = preview_migration()
    if not success:
        sys.exit(1)
