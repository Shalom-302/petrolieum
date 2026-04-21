"""
Main CLI entry point for Kaapi management commands.
"""
import typer
from rich.console import Console
from typing import Optional
import asyncio
# Import sub-commands
from app.commands.migrate import app as migrate_app
from app.commands.init_auth_simple import init_auth_simple
from app.commands.seed_system import seed_all
# Main app
app = typer.Typer(help="Kaapi - Management CLI")
auth_app = typer.Typer(help="Authentication commands")
console = Console()

@auth_app.command("init-simple")
def auth_init_simple_cmd():
    """Initializes basic authentication components."""
    init_auth_simple()

# Add sub-commands
app.add_typer(migrate_app, name="db", help="Database migration commands")
app.add_typer(auth_app, name="auth", help="Authentication commands")

@app.command()
def info():
    """Display information about the Kaapi installation."""
    from app.core.config import settings
    
    console.print("[bold blue]Kaapi Information[/bold blue]")
    console.print(f"Project Name: {settings.PROJECT_NAME}")
    console.print(f"Environment: {settings.ENVIRONMENT}")
    console.print(f"Database URL: {settings.DB_URL.replace('://', '://***:***@')}")

@auth_app.command("seed")
def auth_seed_cmd():
    """Initialise le système multi-tenant (Boss, Stations, Prix)."""
    console.print("[bold yellow]🚀 Lancement du Seed Multi-tenant SEV OIL...[/bold yellow]")
    try:
        asyncio.run(seed_all())
        console.print("[bold green]✅ Données injectées avec succès sur le VPS ![/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ Erreur lors du seed : {str(e)}[/bold red]")

@app.callback()
def main(ctx: typer.Context):
    """
    Kaapi CLI - Manage your Kaapi application.
    """
    pass

if __name__ == "__main__":
    app()
