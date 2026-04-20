# File: app/casbin_setup.py
import casbin
from casbin_sqlalchemy_adapter import Adapter
from app.core.config import settings

# Often you call it DATABASE_URL, but DB_URL is fine if that's your actual env var
DATABASE_URL = settings.DB_URL

def get_casbin_enforcer():
    """
    Initialize and return a Casbin enforcer with SQLAlchemy adapter.
    Make sure to load the policy from the DB so enforcement is ready.
    """
    adapter = Adapter(DATABASE_URL)  # Use your actual DB connection string
    enforcer = casbin.Enforcer("casbin_model.conf", adapter)  # Replace with your model file if needed

    # Load policy from the database so the enforcer sees the latest rules
    enforcer.load_policy()

    return enforcer