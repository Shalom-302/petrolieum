"""
CLI utilities for database migrations and management.
"""
import subprocess
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from app.core.config import settings


def get_backend_dir() -> Path:
    """Return the path to the backend directory."""
    return Path(__file__).resolve().parent.parent.parent


def run_alembic_command(command: List[str], use_docker: bool = False) -> Tuple[str, str, int]:
    """
    Run an alembic command with proper environment settings.
    
    Args:
        command: The alembic command to run
        use_docker: If True, run the command inside the Docker container
        
    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    backend_dir = get_backend_dir()
    
    if use_docker:
        # Run inside Docker container
        docker_cmd = ["docker", "exec", "kaapi-api", "sh", "-c", " ".join(command)]
        process = subprocess.Popen(
            docker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(backend_dir)
        )
    else:    
        # Set up environment for local execution
        env = os.environ.copy()
        env["PYTHONPATH"] = str(backend_dir)
        env["DB_URL"] = settings.DB_URL
        
        # Run command locally
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


def generate_migration(message: str = "Kaapi changes", use_docker: bool = True) -> Dict[str, Any]:
    """
    Generate a new migration using alembic autogenerate.
    
    Args:
        message: Migration message
        use_docker: If True, run inside Docker container
        
    Returns:
        Dictionary with status and output
    """
    command = ["alembic", "revision", "--autogenerate", "-m", message]
    stdout, stderr, return_code = run_alembic_command(command, use_docker)
    
    if return_code != 0:
        return {
            "success": False,
            "error": f"Migration generation failed:\n{stderr}"
        }
    
    return {
        "success": True,
        "message": "Migration generated successfully",
        "output": stdout
    }


def apply_migrations(use_docker: bool = True) -> Dict[str, Any]:
    """
    Apply pending migrations by running alembic upgrade head.
    
    Args:
        use_docker: If True, run inside Docker container
    
    Returns:
        Dictionary with status and output
    """
    command = ["alembic", "upgrade", "head"]
    
    # Définir un environnement spécifique pour indiquer qu'il s'agit de la commande db apply
    env = os.environ.copy()
    env["KAAPI_COMMAND"] = "apply"
    
    # Utiliser l'environnement personnalisé pour la commande
    if use_docker:
        # Pour Docker, on doit passer la variable d'environnement différemment
        docker_prefix = ["docker", "exec", "-e", "KAAPI_COMMAND=apply", "kaapi-api"]
        docker_command = docker_prefix + ["sh", "-c", " ".join(command)]
        process = subprocess.Popen(
            docker_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(get_backend_dir())
        )
        stdout, stderr = process.communicate()
        return_code = process.returncode
    else:
        # Exécuter avec notre environnement personnalisé
        env["PYTHONPATH"] = str(get_backend_dir())
        env["DB_URL"] = settings.DB_URL
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(get_backend_dir()),
            env=env
        )
        stdout, stderr = process.communicate()
        return_code = process.returncode
    
    if return_code != 0:
        return {
            "success": False,
            "error": f"Migration application failed:\n{stderr}"
        }
    
    return {
        "success": True,
        "message": "Migrations applied successfully",
        "output": stdout
    }


def get_pending_migrations(use_docker: bool = True) -> Dict[str, Any]:
    """
    Get information about pending migrations.
    
    Args:
        use_docker: If True, run inside Docker container
    
    Returns:
        Dictionary with status and pending migrations info
    """
    command = ["alembic", "history", "--verbose"]
    stdout, stderr, return_code = run_alembic_command(command)
    
    if return_code != 0:
        return {
            "success": False,
            "error": f"Failed to get migration history:\n{stderr}"
        }
    
    # Get current revision
    current_command = ["alembic", "current"]
    current_stdout, current_stderr, current_return_code = run_alembic_command(current_command)
    
    if current_return_code != 0:
        return {
            "success": False,
            "error": f"Failed to get current migration:\n{current_stderr}"
        }
    
    return {
        "success": True,
        "current": current_stdout.strip(),
        "history": stdout
    }


def preview_migration_changes(use_docker: bool = True) -> Dict[str, Any]:
    """
    Generate a temporary migration to preview changes without applying them.
    
    Args:
        use_docker: If True, run inside Docker container
    
    Returns:
        Dictionary with status and preview of changes
    """
    temp_msg = f"temp_{uuid.uuid4().hex[:8]}"
    
    # Generate temporary migration
    command = ["alembic", "revision", "--autogenerate", "-m", temp_msg]
    stdout, stderr, return_code = run_alembic_command(command)
    
    if return_code != 0:
        return {
            "success": False,
            "error": f"Preview generation failed:\n{stderr}"
        }
    
    # Find the generated file
    backend_dir = get_backend_dir()
    versions_dir = backend_dir / "migrations" / "versions"
    
    revision_file = None
    for file in versions_dir.glob("*.py"):
        if temp_msg in file.name:
            revision_file = file
            break
    
    if not revision_file:
        return {
            "success": False,
            "error": "Could not locate generated migration file"
        }
    
    # Read the file contents
    try:
        revision_content = revision_file.read_text()
        
        # Delete the temporary file
        revision_file.unlink()
        
        return {
            "success": True,
            "message": "Migration preview generated",
            "preview": revision_content
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error reading migration preview: {str(e)}"
        }
