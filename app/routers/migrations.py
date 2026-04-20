# File: backend/app/routers/migrations.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
import subprocess, os, uuid
from pathlib import Path
import uuid
from app.core.db import get_db
from app.plugins.advanced_auth.utils.security import get_current_user
from app.core.config import settings

router = APIRouter()


def preview_autogenerate_changes():
    """
    1) Create a temporary revision file with a random slug
    2) Read its contents
    3) Delete it
    4) Return the text
    """
    temp_msg = f"temp_{uuid.uuid4().hex[:8]}"
    backend_dir = Path(__file__).resolve().parent.parent.parent
    cmd_rev = ["alembic", "revision", "--autogenerate", "-m", temp_msg]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_dir) 

    env = os.environ.copy()
    env["DB_URL"] = settings.DB_URL
    # env["DB_URL"] = os.getenv("DB_URL", "sqlite:///./dev.db")
    

    # 1) Run alembic revision
    proc = subprocess.Popen(
        cmd_rev, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        text=True,
        cwd=str(backend_dir),  # Execute from the backend directory
        env=env
        )
    
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Autogenerate failed:\n{err}")
    
    # 2) Find the created .py file in migrations/versions
    #    Alembic will print something like "Generating ... migrations/versions/xxxx_temp_<uuid>.py"
    #    We can parse that from 'out' or just search the folder for a file containing our temp_msg.
    migrations_dir = Path("migrations/versions/")
    created_file = None
    for f in migrations_dir.iterdir():
        if f.is_file() and temp_msg in f.stem:
            created_file = f
            break
    if not created_file:
        raise RuntimeError("Could not find the temporary revision file.")

    # 3) Read the file
    content = created_file.read_text(encoding="utf-8")

    # 4) Remove the temp file
    created_file.unlink()

    return content  # or parse this further

@router.get("/changes")
def get_pending_migrations():
    try:
        revision_script = preview_autogenerate_changes()
        return {"changes": revision_script}
    except Exception as e:
        raise HTTPException(500, f"Error generating preview: {str(e)}")

@router.post("/apply")
def apply_migrations(
    message: Optional[str] = "Kaapi changes",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    1) Create a new Alembic revision with --autogenerate and the provided message.
    2) Run alembic upgrade head to apply changes.
    """
    try:
        # Step 1: Generate the migration
        cmd_rev = ["alembic", "revision", "--autogenerate", "-m", message]
        rev_process = subprocess.Popen(cmd_rev, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out_rev, err_rev = rev_process.communicate()
        if rev_process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Revision creation failed:\n{err_rev}")

        # Step 2: Apply the migration
        cmd_upgrade = ["alembic", "upgrade", "head"]
        upgrade_process = subprocess.Popen(cmd_upgrade, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out_up, err_up = upgrade_process.communicate()
        if upgrade_process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Upgrade failed:\n{err_up}")

        return {
            "detail": "Migrations applied successfully!",
            "revision_log": out_rev,
            "upgrade_log": out_up
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying migrations: {str(e)}")
