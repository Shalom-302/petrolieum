from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool, MetaData, Table, inspect, text
from alembic import context
from datetime import datetime
import json
import shutil
import importlib
from pathlib import Path
from sqlalchemy_schemadisplay import create_schema_graph
import sqlalchemy
from app.core.config import settings

# The Alembic Config object
config = context.config

fileConfig(config.config_file_name)

from app.core.db import Base
from app.models import *

target_metadata = Base.metadata

# 2) Load DB_URL from settings
# Make sure we're using the right host based on environment
# This will automatically use the POSTGRES_HOST from settings or environment variable
DB_URL = settings.DB_URL

# 3) Tell Alembic which DB to connect to
config.set_main_option("sqlalchemy.url", DB_URL)


def include_object(object, name, type_, reflected, compare_to):
    # Exclure la table 'casbin_rule' des migrations autogénérées
    if type_ == "table" and name == "casbin_rule":
        return False
    
    # Pour les colonnes JSON/JSONB, nous retournons True pour les inclure dans les migrations,
    # mais nous modifions le comportement de comparaison dans run_migrations_online ci-dessous
    return True

# Configuration pour ignorer les comparaisons de JSON qui causent des erreurs
def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    # Si c'est une colonne JSON ou JSONB, on considère qu'elles sont compatibles
    # pour éviter l'erreur "operator does not exist: json = unknown"
    if hasattr(inspected_type, "__class__") and hasattr(metadata_type, "__class__") and \
       (inspected_type.__class__.__name__ in ("JSON", "JSONB") or \
        metadata_type.__class__.__name__ in ("JSON", "JSONB")):
        return False  # False signifie qu'il n'y a pas de différence à migrer
    
    # Pour les autres types, on utilise la comparaison standard
    return None  # None signifie utiliser la comparaison par défaut

# Fonction personnalisée pour éviter les problèmes de comparaison de valeurs par défaut avec JSON
def compare_server_default(context, inspected_column, metadata_column, inspected_default, metadata_default, rendered_metadata_default=None):
    # Si la colonne est de type JSON ou JSONB, ignorer la comparaison des valeurs par défaut
    if hasattr(inspected_column.type, "__class__") and \
       (inspected_column.type.__class__.__name__ in ("JSON", "JSONB")):
        return False
    # Si la colonne est de type TEXT, ignorer la comparaison entre '' et None
    if hasattr(inspected_column.type, "__class__") and \
       inspected_column.type.__class__.__name__ == "Text" and \
       (inspected_default == "''") and metadata_default is None:
        return False
    # Pour les autres types, on laisse Alembic faire sa comparaison standard
    return None

def get_project_root() -> Path:
    """Return the path to the project root directory."""
    return Path(__file__).resolve().parent.parent


def import_all_models():
    """
    Ensures that all models defined in the application are loaded,
    including those defined in plugins.
    """
    # Import models from the main application
    importlib.import_module("app.models")
    
    # Import models from plugins
    plugins_path = get_project_root() / "app" / "plugins"
    if plugins_path.exists():
        for plugin_dir in plugins_path.iterdir():
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
                continue
                
            models_path = plugin_dir / "models.py"
            if models_path.exists():
                module_name = f"app.plugins.{plugin_dir.name}.models"
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"Error importing models from plugin {plugin_dir.name}: {e}")


def generate_schema_diagram(output_dir=None):
    """
    Generates database schema diagrams and saves them to the specified directory.
    """
    # Import all models to ensure they are loaded
    import_all_models()
    
    # If no output directory is specified, use the project root docs directory
    if output_dir is None:
        output_dir = get_project_root() / "docs"
        os.makedirs(output_dir, exist_ok=True)
    
    # Create the schema graph
    graph = create_schema_graph(
        metadata=Base.metadata,
        show_datatypes=True,
        show_indexes=True,
        rankdir='LR',
        concentrate=False
    )
    
    # Save the graph in PNG format
    png_path = output_dir / "db_schema.png"
    graph.write_png(str(png_path))
    print(f"Database schema diagram saved to {png_path}")
    
    # Save the graph in PDF format
    pdf_path = output_dir / "db_schema.pdf"
    graph.write_pdf(str(pdf_path))
    print(f"Database schema diagram saved to {pdf_path}")


def generate_text_schema(output_dir=None):
    """
    Generates a detailed text description of the database schema in Markdown format.
    """
    # Import all models to ensure they are loaded
    import_all_models()
    
    # If no output directory is specified, use the project root docs directory
    if output_dir is None:
        output_dir = get_project_root() / "docs"
        os.makedirs(output_dir, exist_ok=True)
    
    # Generate the text description
    text_path = output_dir / "db_schema.md"
    
    with open(text_path, "w") as f:
        f.write("# Database Schema\n\n")
        
        # Create a clean database connection
        engine = sqlalchemy.create_engine(DB_URL)
        inspector = inspect(engine)
        
        # Get all table names
        table_names = sorted(inspector.get_table_names())
        
        # Generate documentation for each table
        for table_name in table_names:
            if table_name == "casbin_rule":
                continue
                
            f.write(f"## {table_name}\n\n")
            
            # Get table information
            table = Table(table_name, MetaData(), autoload_with=engine)
            columns = inspector.get_columns(table_name)
            primary_key = inspector.get_pk_constraint(table_name)
            
            # Document columns
            f.write("### Columns\n\n")
            f.write("| Name | Type | Nullable | Default | Primary Key |\n")
            f.write("|------|------|----------|---------|-------------|\n")
            
            for column in columns:
                col_name = column["name"]
                col_type = str(column["type"])
                nullable = "Yes" if column["nullable"] else "No"
                default = str(column.get("default", "")) if column.get("default") else "-"
                is_primary = "Yes" if col_name in primary_key["constrained_columns"] else "No"
                
                f.write(f"| {col_name} | {col_type} | {nullable} | {default} | {is_primary} |\n")
            
            f.write("\n")
            
            # Document foreign keys
            foreign_keys = inspector.get_foreign_keys(table_name)
            if foreign_keys:
                f.write("### Foreign Keys\n\n")
                f.write("| Column | References | On Delete | On Update |\n")
                f.write("|--------|------------|-----------|----------|\n")
                
                for fk in foreign_keys:
                    col_names = ", ".join(fk["constrained_columns"])
                    ref_table = fk["referred_table"]
                    ref_cols = ", ".join(fk["referred_columns"])
                    on_delete = fk.get("options", {}).get("ondelete", "NO ACTION")
                    on_update = fk.get("options", {}).get("onupdate", "NO ACTION")
                    
                    f.write(f"| {col_names} | {ref_table}.{ref_cols} | {on_delete} | {on_update} |\n")
                
                f.write("\n")
            
            # Document indexes
            if table.indexes:
                f.write("### Indexes\n\n")
                f.write("| Name | Columns | Unique |\n")
                f.write("|------|---------|--------|\n")
                
                for index in table.indexes:
                    columns = ", ".join(column.name for column in index.columns)
                    unique = "Yes" if index.unique else "No"
                    
                    f.write(f"| {index.name} | {columns} | {unique} |\n")
                
                f.write("\n")
    
    print(f"Database schema description saved to {text_path}")


def generate_schema_visualization(connection):
    """Generate database schema visualization in both high-level and detailed formats."""
    # Ensure all models are loaded
    import_all_models()
    
    # Get schema info using inspector
    inspector = inspect(connection)
    schema_info = {
        "tables": {},
        "relationships": []
    }
    
    # Collect table information
    for table_name in inspector.get_table_names():
        if table_name == "casbin_rule":
            continue
            
        columns = inspector.get_columns(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        indices = inspector.get_indexes(table_name)
        
        schema_info["tables"][table_name] = {
            "columns": [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                    "primary_key": col.get("primary_key", False),
                    "default": str(col["default"]) if col.get("default") else None,
                } for col in columns
            ],
            "indices": [
                {
                    "name": idx["name"],
                    "unique": idx["unique"],
                    "columns": idx["column_names"]
                } for idx in indices
            ]
        }
        
        # Add relationships
        for fk in foreign_keys:
            schema_info["relationships"].append({
                "source_table": table_name,
                "source_columns": fk["constrained_columns"],
                "target_table": fk["referred_table"],
                "target_columns": fk["referred_columns"]
            })
    
    # Create docs directory if it doesn't exist
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    os.makedirs(docs_dir, exist_ok=True)
    
    # Save schema information with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed schema
    detailed_schema_file = os.path.join(docs_dir, f"db_schema_detailed_{timestamp}.json")
    with open(detailed_schema_file, "w") as f:
        json.dump(schema_info, f, indent=2)
    
    # Save latest version
    latest_schema_file = os.path.join(docs_dir, "db_schema_detailed_latest.json")
    with open(latest_schema_file, "w") as f:
        json.dump(schema_info, f, indent=2)
    
    # Generate high-level schema (just tables and their relationships)
    high_level_schema = {
        "tables": list(schema_info["tables"].keys()),
        "relationships": [
            {
                "source": rel["source_table"],
                "target": rel["target_table"]
            } for rel in schema_info["relationships"]
        ]
    }
    
    # Save high-level schema
    high_level_file = os.path.join(docs_dir, f"db_schema_high_level_{timestamp}.json")
    with open(high_level_file, "w") as f:
        json.dump(high_level_schema, f, indent=2)
    
    # Save latest high-level version
    latest_high_level_file = os.path.join(docs_dir, "db_schema_high_level_latest.json")
    with open(latest_high_level_file, "w") as f:
        json.dump(high_level_schema, f, indent=2)
    
    # Copy visualization template if it doesn't exist in the target directory
    template_dir = os.path.join(docs_dir, "templates")
    os.makedirs(template_dir, exist_ok=True)
    
    # Copy schema visualizer template
    template_path = os.path.join(os.path.dirname(__file__), "schema_visualizer.html")
    target_path = os.path.join(template_dir, "schema_visualizer.html")
    shutil.copy(template_path, target_path)
    
    # Create index.html that redirects to the visualizer
    index_html = os.path.join(docs_dir, "index.html")
    with open(index_html, "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0; url=templates/schema_visualizer.html">
</head>
<body>
    <p>Redirecting to schema visualizer...</p>
</body>
</html>""")
    
    # Generate schema diagrams (PNG and PDF)
    try:
        docs_path = Path(docs_dir)
        generate_schema_diagram(docs_path)
    except Exception as e:
        print(f"Warning: Could not generate schema diagrams: {e}")
    
    # Generate textual schema description (Markdown)
    try:
        docs_path = Path(docs_dir)
        generate_text_schema(docs_path)
    except Exception as e:
        print(f"Warning: Could not generate schema description: {e}")


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=compare_type,  # Utilise notre fonction personnalisée pour la comparaison des types
        compare_server_default=compare_server_default,
        include_object=include_object,
        dialect_opts={"paramstyle": "named", "drop_cascade": True},  # Ajoute CASCADE lors de la suppression
    )

    with context.begin_transaction():
        context.run_migrations()
    
    # Generate schema documentation only when running from ./kaapi db apply
    if os.environ.get("KAAPI_COMMAND") == "apply":
        engine = engine_from_config(
            {"sqlalchemy.url": url},
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with engine.connect() as connection:
            generate_schema_visualization(connection)

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        url=DB_URL,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_type,  # Utilise notre fonction personnalisée pour la comparaison des types
            compare_server_default=compare_server_default,  # Utilise notre fonction personnalisée pour la comparaison des valeurs par défaut
            include_object=include_object,
            render_as_batch=True,  # Utilise des opérations de type batch pour gérer les dépendances
            dialect_opts={"paramstyle": "named", "drop_cascade": True},  # Ajoute CASCADE lors de la suppression
        )
        with context.begin_transaction():
            context.run_migrations()
        
        # Generate schema documentation only when running from ./kaapi db apply
        if os.environ.get("KAAPI_COMMAND") == "apply":
            generate_schema_visualization(connection)

def run_migrations():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()

run_migrations()
