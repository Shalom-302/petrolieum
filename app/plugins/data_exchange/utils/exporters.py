"""
Utility functions for exporting data to various formats.
"""

import csv
import json
import os
from typing import Dict, List, Any, Union, Optional

import pandas as pd
import xml.dom.minidom as md
from dicttoxml import dicttoxml

from app.plugins.data_exchange.models import DataFormatType
from app.plugins.data_exchange.utils.file_handlers import create_export_file_path


def get_exporter(format_type: str):
    """
    Get the appropriate exporter function for a given format.
    
    Args:
        format_type: The format type (csv, json, excel, xml)
        
    Returns:
        The exporter function
    """
    exporters = {
        DataFormatType.CSV: export_to_csv,
        DataFormatType.JSON: export_to_json,
        DataFormatType.EXCEL: export_to_excel,
        DataFormatType.XML: export_to_xml
    }
    
    format_type = format_type.lower()
    if format_type not in exporters:
        raise ValueError(f"Unsupported format type: {format_type}")
    
    return exporters[format_type]


def export_data_to_file(
    data: List[Dict[str, Any]],
    format_type: str,
    file_path: str,
    config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Export data to a file in the specified format.
    
    Args:
        data: List of dictionaries to export
        format_type: The format type (csv, json, excel, xml)
        file_path: Path to save the file
        config: Export configuration options
        
    Returns:
        Path to the exported file
    """
    # Get the appropriate exporter
    exporter = get_exporter(format_type)
    
    # Call the exporter function
    exporter(data, file_path, config or {})
    
    return file_path


def get_entity_data(
    entity_name: str,
    query_filters: Optional[Dict[str, Any]] = None,
    db_session=None
) -> List[Dict[str, Any]]:
    """
    Get data for an entity from the database.
    
    Args:
        entity_name: Name of the entity to get data for
        query_filters: Optional filters to apply to the query
        db_session: Database session
        
    Returns:
        List of dictionaries with entity data
    """
    # This would typically:
    # 1. Get the appropriate repository for the entity
    # 2. Query the database with the provided filters
    # 3. Convert the results to dictionaries
    
    # For now, return an empty list as a placeholder
    # In a real implementation, this would interact with the database
    return []


def get_supported_export_entities() -> List[str]:
    """
    Get a list of entities that can be exported.
    
    Returns:
        List of entity names
    """
    # This would typically:
    # 1. Get a list of all entities in the application
    # 2. Filter to only those that can be exported
    
    # For now, return a placeholder list
    return [
        "users",
        "products",
        "orders",
        "customers",
        "suppliers",
        "inventory",
        "transactions"
    ]


# Export functions for different formats

def export_to_csv(
    data: List[Dict[str, Any]],
    file_path: str,
    config: Dict[str, Any]
) -> None:
    """
    Export data to a CSV file.
    
    Args:
        data: List of dictionaries to export
        file_path: Path to save the CSV file
        config: Export configuration
    """
    # Default configuration
    default_config = {
        "delimiter": ",",
        "quotechar": '"',
        "encoding": "utf-8",
        "include_headers": True
    }
    
    # Merge with provided config
    csv_config = {**default_config, **config}
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # If data is empty, create an empty file
    if not data:
        with open(file_path, 'w', encoding=csv_config["encoding"]) as f:
            f.write("")
        return
    
    # Get headers from the first row
    headers = list(data[0].keys())
    
    # Write to CSV file
    with open(file_path, 'w', newline='', encoding=csv_config["encoding"]) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=headers,
            delimiter=csv_config["delimiter"],
            quotechar=csv_config["quotechar"],
            quoting=csv.QUOTE_MINIMAL
        )
        
        # Write headers if configured
        if csv_config["include_headers"]:
            writer.writeheader()
        
        # Write rows
        writer.writerows(data)


def export_to_json(
    data: List[Dict[str, Any]],
    file_path: str,
    config: Dict[str, Any]
) -> None:
    """
    Export data to a JSON file.
    
    Args:
        data: List of dictionaries to export
        file_path: Path to save the JSON file
        config: Export configuration
    """
    # Default configuration
    default_config = {
        "indent": 2,
        "encoding": "utf-8",
        "as_array": True,
        "root_key": "data"
    }
    
    # Merge with provided config
    json_config = {**default_config, **config}
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Prepare the data structure
    if json_config["as_array"]:
        output_data = data
    else:
        output_data = {json_config["root_key"]: data}
    
    # Write to JSON file
    with open(file_path, 'w', encoding=json_config["encoding"]) as f:
        json.dump(output_data, f, indent=json_config["indent"])


def export_to_excel(
    data: List[Dict[str, Any]],
    file_path: str,
    config: Dict[str, Any]
) -> None:
    """
    Export data to an Excel file.
    
    Args:
        data: List of dictionaries to export
        file_path: Path to save the Excel file
        config: Export configuration
    """
    # Default configuration
    default_config = {
        "sheet_name": "Data",
        "index": False,
        "engine": "openpyxl"
    }
    
    # Merge with provided config
    excel_config = {**default_config, **config}
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Write to Excel file
    df.to_excel(
        file_path,
        sheet_name=excel_config["sheet_name"],
        index=excel_config["index"],
        engine=excel_config["engine"]
    )


def export_to_xml(
    data: List[Dict[str, Any]],
    file_path: str,
    config: Dict[str, Any]
) -> None:
    """
    Export data to an XML file.
    
    Args:
        data: List of dictionaries to export
        file_path: Path to save the XML file
        config: Export configuration
    """
    # Default configuration
    default_config = {
        "root": "data",
        "item": "item",
        "encoding": "utf-8",
        "pretty": True,
        "attr_type": False
    }
    
    # Merge with provided config
    xml_config = {**default_config, **config}
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Convert to XML
    xml = dicttoxml(
        data,
        custom_root=xml_config["root"],
        item_func=lambda x: xml_config["item"],
        attr_type=xml_config["attr_type"]
    )
    
    # Pretty print if configured
    if xml_config["pretty"]:
        dom = md.parseString(xml)
        pretty_xml = dom.toprettyxml()
    else:
        pretty_xml = xml.decode(xml_config["encoding"])
    
    # Write to XML file
    with open(file_path, 'w', encoding=xml_config["encoding"]) as f:
        f.write(pretty_xml)
