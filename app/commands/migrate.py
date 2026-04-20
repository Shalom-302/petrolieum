"""
Migration command line utilities for Kaapi.
Use these commands to generate and apply migrations from the command line.
"""
import typer
import os
import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from app.core.cli import (
    generate_migration, 
    apply_migrations, 
    get_pending_migrations,
    preview_migration_changes
)
from app.commands.init_migration import init_migration

app = typer.Typer(help="Database migration commands for Kaapi")
console = Console()

@app.command("reset")
def reset_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Force reset without confirmation")
):
    """Reset Alembic state for a fresh start - use with caution."""
    console.print("[bold red]WARNING: This will reset Alembic's migration tracking![/bold red]")
    console.print("This should only be used when Alembic is out of sync with your database.")
    
    if force or typer.confirm("Are you sure you want to continue?"):
        from app.core.cli import run_alembic_command
        
        # Stamp the database with the current head revision without running migrations
        command = ["alembic", "stamp", "head"]
        stdout, stderr, return_code = run_alembic_command(command)
        
        if return_code == 0:
            console.print(Panel(
                "Alembic has been reset to the current head revision.\n" +
                "You can now generate new migrations.",
                title="[bold green]Reset Successful[/bold green]",
                expand=False
            ))
        else:
            console.print(Panel(
                f"Error: {stderr}",
                title="[bold red]Reset Failed[/bold red]",
                expand=False
            ))
            raise typer.Exit(code=1)

@app.command("generate")
def generate_cmd(
    message: Optional[str] = typer.Option("Kaapi changes", "--message", "-m", help="Migration message")
):
    """Generate a new migration using alembic autogenerate."""
    console.print("[bold blue]Generating migration...[/bold blue]")
    
    result = generate_migration(message, use_docker=False)
    
    if result["success"]:
        console.print(Panel(
            Text(result["output"], style="green"),
            title="[bold green]Migration Generated Successfully[/bold green]",
            expand=False
        ))
    else:
        console.print(Panel(
            Text(result["error"], style="red"),
            title="[bold red]Migration Generation Failed[/bold red]",
            expand=False
        ))
        raise typer.Exit(code=1)

@app.command("apply")
def apply_cmd():
    """Apply pending migrations to upgrade to the latest version."""
    console.print("[bold blue]Applying migrations...[/bold blue]")
    
    result = apply_migrations(use_docker=False)
    
    if result["success"]:
        console.print(Panel(
            Text(result["output"], style="green"),
            title="[bold green]Migrations Applied Successfully[/bold green]",
            expand=False
        ))
    else:
        console.print(Panel(
            Text(result["error"], style="red"),
            title="[bold red]Migration Application Failed[/bold red]",
            expand=False
        ))
        raise typer.Exit(code=1)

@app.command("pending")
def pending_cmd():
    """Display information about pending migrations."""
    console.print("[bold blue]Checking pending migrations...[/bold blue]")
    
    result = get_pending_migrations()
    
    if result["success"]:
        console.print(Panel(
            f"Current revision: {result['current']}\n\n{result['history']}",
            title="[bold green]Migration History[/bold green]",
            expand=False
        ))
    else:
        console.print(Panel(
            Text(result["error"], style="red"),
            title="[bold red]Failed to Get Migration Info[/bold red]",
            expand=False
        ))
        raise typer.Exit(code=1)

@app.command("preview")
def preview_cmd():
    """Preview changes that would be included in a new migration."""
    console.print("[bold blue]Generating migration preview...[/bold blue]")
    
    result = preview_migration_changes()
    
    if result["success"]:
        console.print(Panel(
            Text(result["preview"], style="green"),
            title="[bold green]Migration Preview[/bold green]",
            expand=False
        ))
    else:
        console.print(Panel(
            Text(result["error"], style="red"),
            title="[bold red]Preview Generation Failed[/bold red]",
            expand=False
        ))
        raise typer.Exit(code=1)

@app.command("init")
def init_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Force reinitialization without confirmation")
):
    """Initialize migration and create a base schema from current models."""
    console.print("[bold blue]Initializing migration database...[/bold blue]")
    
    if force or typer.confirm("This will wipe the database and recreate it from scratch. Continue?"):
        try:
            # Rediriger stdout vers la console Rich
            original_stdout = sys.stdout
            
            class RichConsoleWriter:
                def write(self, text):
                    if text.strip():
                        console.print(text, end="")
                def flush(self):
                    pass
            
            sys.stdout = RichConsoleWriter()
            
            # Exécuter l'initialisation
            init_migration()
            
            # Restaurer stdout
            sys.stdout = original_stdout
            
            console.print(Panel(
                "Migration database has been successfully initialized.\n" +
                "Your database schema is now synchronized with your models.",
                title="[bold green]Initialization Successful[/bold green]",
                expand=False
            ))
        except Exception as e:
            sys.stdout = original_stdout
            console.print(Panel(
                f"Error: {str(e)}",
                title="[bold red]Initialization Failed[/bold red]",
                expand=False
            ))
            raise typer.Exit(code=1)
    else:
        console.print("Initialization cancelled.")

if __name__ == "__main__":
    app()
