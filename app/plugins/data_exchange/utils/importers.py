"""
Utility functions for importing data from various formats.
"""

import csv
import json
import os
import pandas as pd
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Tuple, Optional

from app.plugins.data_exchange.models import DataFormatType
from app.plugins.data_exchange.schemas import DataValidationError
from app.plugins.data_exchange.utils.validators import validate_data


def detect_file_format(file_path: str) -> str:
    """
    Detect the format of a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Detected format as a string (csv, json, excel, xml)
    """
    extension = os.path.splitext(file_path)[1].lower()
    
    if extension == '.csv':
        return DataFormatType.CSV
    elif extension == '.json':
        return DataFormatType.JSON
    elif extension in ['.xlsx', '.xls']:
        return DataFormatType.EXCEL
    elif extension == '.xml':
        return DataFormatType.XML
    else:
        # Default to CSV if unknown
        return DataFormatType.CSV


def get_importer(format_type: str):
    """
    Get the appropriate importer function for a given format.
    
    Args:
        format_type: The format type (csv, json, excel, xml)
        
    Returns:
        The importer function
    """
    importers = {
        DataFormatType.CSV: import_csv,
        DataFormatType.JSON: import_json,
        DataFormatType.EXCEL: import_excel,
        DataFormatType.XML: import_xml
    }
    
    format_type = format_type.lower()
    if format_type not in importers:
        raise ValueError(f"Unsupported format type: {format_type}")
    
    return importers[format_type]


def preview_import_data(
    file_path: str, 
    format_type: str, 
    target_entity: str, 
    config: Dict[str, Any] = None, 
    sample_size: int = 5
) -> Dict[str, Any]:
    """
    Preview data import by returning headers, sample data, and suggested mappings.
    
    Args:
        file_path: Path to the file to import
        format_type: The format type (csv, json, excel, xml)
        target_entity: The target entity to import into
        config: Optional configuration including column mappings
        sample_size: Number of sample rows to return
        
    Returns:
        Dictionary with headers, sample_data, detected_types, and suggested_mappings
    """
    # Get the appropriate importer
    importer = get_importer(format_type)
    
    # Read a limited number of rows
    data = importer(file_path, target_entity, config, sample_size=sample_size, preview_only=True)
    
    # Extract sample rows
    sample_data = data[:sample_size] if len(data) > sample_size else data
    
    # Get headers from the first row (assuming all rows have the same keys)
    headers = list(sample_data[0].keys()) if sample_data else []
    
    # Detect data types
    detected_types = {}
    for header in headers:
        detected_types[header] = detect_data_type(sample_data, header)
    
    # Generate suggested mappings
    suggested_mappings = generate_suggested_mappings(headers, target_entity)
    
    # Return preview data
    return {
        "headers": headers,
        "sample_data": sample_data,
        "detected_types": detected_types,
        "suggested_mappings": suggested_mappings
    }


def validate_import_data(
    file_path: str,
    format_type: str,
    target_entity: str,
    config: Dict[str, Any] = None
) -> List[DataValidationError]:
    """
    Validate data to be imported without actually importing it.
    
    Args:
        file_path: Path to the file to import
        format_type: The format type (csv, json, excel, xml)
        target_entity: The target entity to import into
        config: Optional configuration including column mappings and validation rules
        
    Returns:
        List of validation errors
    """
    # Get the appropriate importer
    importer = get_importer(format_type)
    
    # Read data
    data = importer(file_path, target_entity, config, preview_only=True)
    
    # Validate the data
    validation_errors = []
    
    # Apply validation rules from config
    validation_rules = config.get('validation_rules', {}) if config else {}
    
    # Process each row
    for row_index, row in enumerate(data):
        # Apply column mapping if provided
        mapped_row = {}
        column_mapping = config.get('column_mapping', {}) if config else {}
        
        if column_mapping:
            for source_col, target_col in column_mapping.items():
                if source_col in row:
                    mapped_row[target_col] = row[source_col]
        else:
            mapped_row = row
        
        # Validate each field
        row_errors = validate_data(mapped_row, validation_rules, target_entity, row_index)
        validation_errors.extend(row_errors)
    
    return validation_errors


def import_data_to_db(
    file_path: str, 
    format_type: str, 
    target_entity: str, 
    config: Dict[str, Any] = None,
    db_session=None
) -> Dict[str, Any]:
    """
    Import data from a file into the database.
    
    Args:
        file_path: Path to the file to import
        format_type: The format type (csv, json, excel, xml)
        target_entity: The target entity to import into
        config: Optional configuration including column mappings
        db_session: Database session to use for the import
        
    Returns:
        Dictionary with import statistics
    """
    # Get the appropriate importer
    importer = get_importer(format_type)
    
    # Read data
    data = importer(file_path, target_entity, config)
    
    # Import statistics
    stats = {
        "total": len(data),
        "success": 0,
        "error": 0,
        "errors": []
    }
    
    # Apply column mapping if provided
    column_mapping = config.get('column_mapping', {}) if config else {}
    
    # Process each row
    for row_index, row in enumerate(data):
        try:
            # Apply column mapping
            mapped_row = {}
            if column_mapping:
                for source_col, target_col in column_mapping.items():
                    if source_col in row:
                        mapped_row[target_col] = row[source_col]
            else:
                mapped_row = row
            
            # Import the row into the database
            import_row_to_db(mapped_row, target_entity, db_session)
            
            stats["success"] += 1
        except Exception as e:
            stats["error"] += 1
            stats["errors"].append({
                "row_index": row_index,
                "error": str(e),
                "data": row
            })
    
    return stats


# Import functions for different formats

def import_csv(
    file_path: str, 
    target_entity: str, 
    config: Dict[str, Any] = None, 
    sample_size: int = None,
    preview_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Import data from a CSV file.
    
    Args:
        file_path: Path to the CSV file
        target_entity: Target entity name
        config: Import configuration
        sample_size: Optional limit on the number of rows to import
        preview_only: Whether this is just a preview
        
    Returns:
        List of dictionaries, one per row
    """
    # Default configuration
    default_config = {
        "delimiter": ",",
        "quotechar": '"',
        "encoding": "utf-8"
    }
    
    # Merge with provided config
    csv_config = {**default_config, **(config or {})}
    
    # Read the CSV file
    data = []
    with open(file_path, 'r', encoding=csv_config["encoding"]) as f:
        reader = csv.DictReader(
            f, 
            delimiter=csv_config["delimiter"], 
            quotechar=csv_config["quotechar"]
        )
        
        for i, row in enumerate(reader):
            # Convert empty strings to None
            processed_row = {k: (v if v != "" else None) for k, v in row.items()}
            data.append(processed_row)
            
            # Stop if we've reached the sample size
            if sample_size and i >= sample_size - 1:
                break
    
    return data


def import_json(
    file_path: str, 
    target_entity: str, 
    config: Dict[str, Any] = None, 
    sample_size: int = None,
    preview_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Import data from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        target_entity: Target entity name
        config: Import configuration
        sample_size: Optional limit on the number of rows to import
        preview_only: Whether this is just a preview
        
    Returns:
        List of dictionaries, one per row
    """
    # Read the JSON file
    with open(file_path, 'r') as f:
        json_data = json.load(f)
    
    # Handle different JSON structures
    data = []
    
    # Case 1: Array of objects
    if isinstance(json_data, list):
        data = json_data
    
    # Case 2: Object with data array
    elif isinstance(json_data, dict):
        # Try to find an array field
        for key, value in json_data.items():
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                data = value
                break
        
        # If no array found, use the object itself as a single row
        if not data:
            data = [json_data]
    
    # Limit to sample size if specified
    if sample_size and len(data) > sample_size:
        data = data[:sample_size]
    
    return data


def import_excel(
    file_path: str, 
    target_entity: str, 
    config: Dict[str, Any] = None, 
    sample_size: int = None,
    preview_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Import data from an Excel file.
    
    Args:
        file_path: Path to the Excel file
        target_entity: Target entity name
        config: Import configuration
        sample_size: Optional limit on the number of rows to import
        preview_only: Whether this is just a preview
        
    Returns:
        List of dictionaries, one per row
    """
    # Default configuration
    default_config = {
        "sheet_name": 0,  # First sheet
        "header": 0,      # First row as header
        "na_values": ["", "NA", "N/A"]
    }
    
    # Merge with provided config
    excel_config = {**default_config, **(config or {})}
    
    # Read the Excel file
    df = pd.read_excel(
        file_path,
        sheet_name=excel_config["sheet_name"],
        header=excel_config["header"],
        na_values=excel_config["na_values"]
    )
    
    # Convert to list of dictionaries
    data = df.replace({pd.NA: None}).to_dict('records')
    
    # Limit to sample size if specified
    if sample_size and len(data) > sample_size:
        data = data[:sample_size]
    
    return data


def import_xml(
    file_path: str, 
    target_entity: str, 
    config: Dict[str, Any] = None, 
    sample_size: int = None,
    preview_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Import data from an XML file.
    
    Args:
        file_path: Path to the XML file
        target_entity: Target entity name
        config: Import configuration
        sample_size: Optional limit on the number of rows to import
        preview_only: Whether this is just a preview
        
    Returns:
        List of dictionaries, one per row
    """
    # Default configuration
    default_config = {
        "record_tag": None,  # Tag that represents a single record
        "flatten": True      # Flatten nested structures
    }
    
    # Merge with provided config
    xml_config = {**default_config, **(config or {})}
    
    # Parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Find records
    data = []
    
    if xml_config["record_tag"]:
        # Find all elements with the specified tag
        records = root.findall(f".//{xml_config['record_tag']}")
    else:
        # Try to guess the record tag
        # Assume immediate children of root or first level of nesting
        children = list(root)
        if len(children) > 0 and all(child.tag == children[0].tag for child in children):
            records = children
        else:
            # Look one level deeper
            potential_records = []
            for child in children:
                potential_records.extend(list(child))
            
            # Check if all have the same tag
            if potential_records and all(record.tag == potential_records[0].tag for record in potential_records):
                records = potential_records
            else:
                # Default to root's children
                records = children
    
    # Convert XML elements to dictionaries
    for record in records:
        record_dict = xml_element_to_dict(record, flatten=xml_config["flatten"])
        data.append(record_dict)
        
        # Stop if we've reached the sample size
        if sample_size and len(data) >= sample_size:
            break
    
    return data


def xml_element_to_dict(element, flatten=True):
    """Convert an XML element to a dictionary."""
    result = {}
    
    # Add attributes
    for key, value in element.attrib.items():
        result[f"@{key}"] = value
    
    # Add children
    for child in element:
        child_data = xml_element_to_dict(child, flatten)
        
        if child.tag in result:
            # If this tag already exists, convert to a list
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_data)
        else:
            result[child.tag] = child_data
    
    # Add text
    if element.text and element.text.strip():
        if flatten and not result:
            # Just return the text if no attributes or children and flatten is True
            return element.text.strip()
        else:
            result["#text"] = element.text.strip()
    
    return result


# Helper functions

def detect_data_type(data: List[Dict[str, Any]], field: str) -> str:
    """
    Detect the data type of a field based on sample data.
    
    Args:
        data: List of data dictionaries
        field: Field name to detect type for
        
    Returns:
        Detected type as a string (string, number, boolean, date, null)
    """
    # Collect non-null values
    values = [row[field] for row in data if field in row and row[field] is not None]
    
    if not values:
        return "null"
    
    # Check if all values are numeric
    numeric_count = sum(1 for v in values if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit()))
    if numeric_count == len(values):
        return "number"
    
    # Check if all values are booleans
    bool_values = ["true", "false", "yes", "no", "1", "0"]
    bool_count = sum(1 for v in values if str(v).lower() in bool_values)
    if bool_count == len(values):
        return "boolean"
    
    # Check if all values look like dates
    date_formats = [
        r'\d{4}-\d{2}-\d{2}',  # ISO format (YYYY-MM-DD)
        r'\d{2}/\d{2}/\d{4}',  # US format (MM/DD/YYYY)
        r'\d{2}\.\d{2}\.\d{4}'  # European format (DD.MM.YYYY)
    ]
    
    import re
    date_count = 0
    for v in values:
        if not isinstance(v, str):
            continue
        
        for pattern in date_formats:
            if re.fullmatch(pattern, v):
                date_count += 1
                break
    
    if date_count == len(values):
        return "date"
    
    # Default to string
    return "string"


def generate_suggested_mappings(headers: List[str], target_entity: str) -> Dict[str, str]:
    """
    Generate suggested mappings from source headers to target entity fields.
    
    Args:
        headers: List of headers from the source file
        target_entity: Target entity name
        
    Returns:
        Dictionary mapping source headers to target entity fields
    """
    # This would typically involve looking up the database schema for the target entity
    # and mapping based on field names, but here we'll just use a simple direct mapping
    
    # For demonstration, just return a direct mapping
    return {header: header.lower().replace(" ", "_") for header in headers}


def import_row_to_db(row: Dict[str, Any], target_entity: str, db_session) -> bool:
    """
    Import a single row into the database.
    
    Args:
        row: Dictionary with row data
        target_entity: Target entity to import into
        db_session: Database session
        
    Returns:
        True if successful, False otherwise
    """
    # This function would typically:
    # 1. Map the row data to the target entity's fields
    # 2. Create a new entity object
    # 3. Add it to the database session
    # 4. Commit the session
    
    # For now, just return True as a placeholder
    # In a real implementation, this would interact with the database
    return True
