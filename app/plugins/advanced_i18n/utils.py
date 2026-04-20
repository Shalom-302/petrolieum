"""
Utility functions for the Advanced Internationalization plugin.
"""

from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
import io
import csv
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from app.plugins.advanced_i18n.models import Language, Translation


def get_language_from_headers(accept_language: str) -> str:
    """
    Parse the Accept-Language header and return the most preferred language.
    
    Args:
        accept_language: The Accept-Language header string
        
    Returns:
        The ISO language code of the most preferred language
    """
    # Placeholder - actual implementation is in the middleware
    return "en"


def get_default_language_code(db: Session) -> str:
    """
    Get the code of the default language.
    
    Args:
        db: Database session
        
    Returns:
        The language code of the default language or "en" if not found
    """
    default_lang = db.query(Language).filter(Language.is_default == True).first()
    return default_lang.code if default_lang else "en"


def get_all_translation_keys(db: Session) -> List[str]:
    """
    Get all unique translation keys in the database.
    
    Args:
        db: Database session
        
    Returns:
        List of unique translation keys
    """
    return [row[0] for row in db.query(Translation.key).distinct().all()]


def get_translation_value(db: Session, language_code: str, key: str) -> Optional[str]:
    """
    Get a translation value for a specific language and key.
    
    Args:
        db: Database session
        language_code: ISO language code
        key: Translation key
        
    Returns:
        Translation value or None if not found
    """
    language = db.query(Language).filter(Language.code == language_code).first()
    if not language:
        return None
    
    translation = db.query(Translation).join(Language).filter(
        Language.code == language_code,
        Translation.key == key
    ).first()
    
    return translation.value if translation else None


def translate(db: Session, key: str, language_code: str, fallback_code: str = "en", **kwargs) -> str:
    """
    Translate a key to the specified language.
    
    Args:
        db: Database session
        key: Translation key
        language_code: ISO language code
        fallback_code: Fallback language code if translation is not found
        **kwargs: Variables to format the translation string
        
    Returns:
        Translated string or key if not found
    """
    # Try to get translation in requested language
    translation = get_translation_value(db, language_code, key)
    
    # If not found, try fallback language
    if translation is None and fallback_code != language_code:
        translation = get_translation_value(db, fallback_code, key)
    
    # If still not found, return the key
    if translation is None:
        return key
    
    # Format translation with variables if any
    if kwargs:
        try:
            return translation.format(**kwargs)
        except KeyError:
            # If formatting fails, return unformatted translation
            return translation
    
    return translation


def get_missing_translations(db: Session, language_code: str) -> List[str]:
    """
    Get all keys that are missing translations for a specific language.
    
    Args:
        db: Database session
        language_code: ISO language code
        
    Returns:
        List of keys missing translations
    """
    language = db.query(Language).filter(Language.code == language_code).first()
    if not language:
        raise HTTPException(status_code=404, detail=f"Language with code {language_code} not found")
    
    # Get all keys
    all_keys = get_all_translation_keys(db)
    
    # Get translated keys for this language
    translated_keys = [row[0] for row in db.query(Translation.key).filter(
        Translation.language_id == language.id
    ).distinct().all()]
    
    # Return keys that are not in translated_keys
    return list(set(all_keys) - set(translated_keys))


def export_translations_to_csv(db: Session, language_code: Optional[str] = None) -> StreamingResponse:
    """
    Export translations to a CSV file.
    
    Args:
        db: Database session
        language_code: Optional ISO language code to filter by
        
    Returns:
        StreamingResponse with CSV content
    """
    # Create CSV buffer
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["group", "key", "language", "value", "context"])
    
    # Query translations
    query = db.query(Translation).join(Language)
    if language_code:
        query = query.filter(Language.code == language_code)
    
    # Write data
    for translation in query.all():
        writer.writerow([
            translation.group.name,
            translation.key,
            translation.language.code,
            translation.value,
            translation.context or ""
        ])
    
    # Prepare response
    output.seek(0)
    filename = f"translations_{language_code if language_code else 'all'}.csv"
    
    return StreamingResponse(
        io.StringIO(output.getvalue()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def generate_js_translations(db: Session, language_code: str) -> str:
    """
    Generate a JavaScript file with translations for a specific language.
    
    Args:
        db: Database session
        language_code: ISO language code
        
    Returns:
        JavaScript content as string
    """
    language = db.query(Language).filter(Language.code == language_code).first()
    if not language:
        raise HTTPException(status_code=404, detail=f"Language with code {language_code} not found")
    
    # Get all translations for this language
    translations = db.query(Translation).filter(Translation.language_id == language.id).all()
    
    # Organize translations by group
    translations_by_group = {}
    for translation in translations:
        group_name = translation.group.name
        if group_name not in translations_by_group:
            translations_by_group[group_name] = {}
        
        translations_by_group[group_name][translation.key] = translation.value
    
    # Generate JavaScript content
    js_content = f"// Generated translations for {language.name} ({language.code})\n"
    js_content += "const translations = " + json.dumps(translations_by_group, indent=2) + ";\n\n"
    js_content += "export default translations;\n"
    
    return js_content
