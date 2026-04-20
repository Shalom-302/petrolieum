"""
CRUD operations for the Advanced Internationalization plugin.
"""

from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from fastapi import UploadFile, HTTPException
import csv
import io
import json
from datetime import datetime

from app.plugins.advanced_i18n.models import Language, TranslationGroup, Translation, TranslationHistory
from app.plugins.advanced_i18n.schemas import LanguageCreate, LanguageUpdate, TranslationCreate, TranslationUpdate, TranslationStatistics


# --- Language CRUD operations ---

def get_language(db: Session, language_id: int) -> Optional[Language]:
    """Get a language by ID."""
    return db.query(Language).filter(Language.id == language_id).first()


def get_language_by_code(db: Session, code: str) -> Optional[Language]:
    """Get a language by its code."""
    return db.query(Language).filter(Language.code == code).first()


def get_languages(db: Session, skip: int = 0, limit: int = 100, only_enabled: bool = False) -> List[Language]:
    """Get all languages."""
    query = db.query(Language)
    if only_enabled:
        query = query.filter(Language.is_enabled == True)
    return query.order_by(Language.name).offset(skip).limit(limit).all()


def get_default_language(db: Session) -> Optional[Language]:
    """Get the default language."""
    return db.query(Language).filter(Language.is_default == True).first()


def create_language(db: Session, language: LanguageCreate) -> Language:
    """Create a new language."""
    # If this is set as the default language, unset any existing default
    if language.is_default:
        db.query(Language).filter(Language.is_default == True).update({"is_default": False})
    
    db_language = Language(
        code=language.code,
        name=language.name,
        native_name=language.native_name,
        flag_code=language.flag_code,
        is_rtl=language.is_rtl,
        is_default=language.is_default,
        is_enabled=language.is_enabled
    )
    
    db.add(db_language)
    db.commit()
    db.refresh(db_language)
    
    return db_language


def update_language(db: Session, language_id: int, language: LanguageUpdate) -> Optional[Language]:
    """Update an existing language."""
    db_language = get_language(db, language_id)
    if not db_language:
        return None
    
    # Update fields if provided
    update_data = language.dict(exclude_unset=True)
    
    # Handle default language flag
    if "is_default" in update_data and update_data["is_default"] and not db_language.is_default:
        # If this language is being set as default, unset any existing default
        db.query(Language).filter(Language.is_default == True).update({"is_default": False})
    
    for key, value in update_data.items():
        setattr(db_language, key, value)
    
    db.commit()
    db.refresh(db_language)
    
    return db_language


def delete_language(db: Session, language_id: int) -> bool:
    """Delete a language."""
    db_language = get_language(db, language_id)
    if not db_language:
        return False
    
    # Don't allow deleting the default language
    if db_language.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default language. Set another language as default first.")
    
    db.delete(db_language)
    db.commit()
    
    return True


# --- Translation Group CRUD operations ---

def get_translation_group(db: Session, group_id: int) -> Optional[TranslationGroup]:
    """Get a translation group by ID."""
    return db.query(TranslationGroup).filter(TranslationGroup.id == group_id).first()


def get_translation_group_by_name(db: Session, name: str) -> Optional[TranslationGroup]:
    """Get a translation group by name."""
    return db.query(TranslationGroup).filter(TranslationGroup.name == name).first()


def get_translation_groups(db: Session, skip: int = 0, limit: int = 100) -> List[TranslationGroup]:
    """Get all translation groups."""
    return db.query(TranslationGroup).order_by(TranslationGroup.name).offset(skip).limit(limit).all()


def create_translation_group(db: Session, name: str, description: Optional[str] = None) -> TranslationGroup:
    """Create a new translation group."""
    db_group = TranslationGroup(name=name, description=description)
    
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    
    return db_group


def update_translation_group(db: Session, group_id: int, name: Optional[str] = None, description: Optional[str] = None) -> Optional[TranslationGroup]:
    """Update an existing translation group."""
    db_group = get_translation_group(db, group_id)
    if not db_group:
        return None
    
    if name is not None:
        db_group.name = name
    
    if description is not None:
        db_group.description = description
    
    db.commit()
    db.refresh(db_group)
    
    return db_group


def delete_translation_group(db: Session, group_id: int) -> bool:
    """Delete a translation group."""
    db_group = get_translation_group(db, group_id)
    if not db_group:
        return False
    
    db.delete(db_group)
    db.commit()
    
    return True


# --- Translation CRUD operations ---

def get_translation(db: Session, translation_id: int) -> Optional[Translation]:
    """Get a translation by ID."""
    return db.query(Translation).filter(Translation.id == translation_id).first()


def get_translation_by_key(db: Session, language_id: int, group_id: int, key: str) -> Optional[Translation]:
    """Get a translation by language, group, and key."""
    return db.query(Translation).filter(
        Translation.language_id == language_id,
        Translation.group_id == group_id,
        Translation.key == key
    ).first()


def get_translations(
    db: Session, 
    language_code: Optional[str] = None,
    group_name: Optional[str] = None,
    key_prefix: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100,
    needs_review: Optional[bool] = None
) -> List[Translation]:
    """
    Get translations with optional filtering.
    
    Args:
        db: Database session
        language_code: Optional language code to filter by
        group_name: Optional group name to filter by
        key_prefix: Optional key prefix to filter by
        skip: Number of records to skip
        limit: Maximum number of records to return
        needs_review: Filter translations that need review
        
    Returns:
        List of translations matching the criteria
    """
    query = db.query(Translation)
    
    # Apply filters
    if language_code:
        language = get_language_by_code(db, language_code)
        if language:
            query = query.filter(Translation.language_id == language.id)
    
    if group_name:
        group = get_translation_group_by_name(db, group_name)
        if group:
            query = query.filter(Translation.group_id == group.id)
    
    if key_prefix:
        query = query.filter(Translation.key.like(f"{key_prefix}%"))
    
    if needs_review is not None:
        query = query.filter(Translation.needs_review == needs_review)
    
    return query.offset(skip).limit(limit).all()


def create_translation(db: Session, translation_data: TranslationCreate) -> Translation:
    """
    Create a new translation.
    
    Args:
        db: Database session
        translation_data: Data for the new translation
        
    Returns:
        The created translation
        
    Raises:
        HTTPException: If the language or group doesn't exist
    """
    # Get language and group
    language = get_language_by_code(db, translation_data.language_code)
    if not language:
        raise HTTPException(status_code=404, detail=f"Language with code {translation_data.language_code} not found")
    
    group = get_translation_group_by_name(db, translation_data.group_name)
    if not group:
        # Create the group if it doesn't exist
        group = create_translation_group(db, translation_data.group_name)
    
    # Check if the translation already exists
    existing_translation = get_translation_by_key(db, language.id, group.id, translation_data.key)
    if existing_translation:
        raise HTTPException(status_code=400, detail=f"Translation with key {translation_data.key} already exists for language {translation_data.language_code} and group {translation_data.group_name}")
    
    # Create the translation
    db_translation = Translation(
        language_id=language.id,
        group_id=group.id,
        key=translation_data.key,
        value=translation_data.value,
        context=translation_data.context,
        plural_forms=[pf.dict() for pf in translation_data.plural_forms] if translation_data.plural_forms else None,
        is_machine_translated=translation_data.is_machine_translated,
        needs_review=translation_data.needs_review
    )
    
    db.add(db_translation)
    db.commit()
    db.refresh(db_translation)
    
    # Add history record
    add_translation_history(db, db_translation, None, db_translation.value)
    
    return db_translation


def update_translation(db: Session, translation_id: int, translation_data: TranslationUpdate) -> Optional[Translation]:
    """
    Update an existing translation.
    
    Args:
        db: Database session
        translation_id: ID of the translation to update
        translation_data: New data for the translation
        
    Returns:
        The updated translation or None if not found
    """
    db_translation = get_translation(db, translation_id)
    if not db_translation:
        return None
    
    # Store old value for history
    old_value = db_translation.value
    
    # Update fields if provided
    update_data = translation_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_translation, key, value)
    
    db.commit()
    db.refresh(db_translation)
    
    # Add history record if value changed
    if 'value' in update_data and update_data['value'] != old_value:
        add_translation_history(db, db_translation, old_value, update_data['value'])
    
    return db_translation


def delete_translation(db: Session, translation_id: int) -> bool:
    """Delete a translation."""
    db_translation = get_translation(db, translation_id)
    if not db_translation:
        return False
    
    db.delete(db_translation)
    db.commit()
    
    return True


def add_translation_history(db: Session, translation: Translation, old_value: Optional[str], new_value: str, user_id: Optional[int] = None) -> TranslationHistory:
    """Add a record to translation history."""
    language = get_language(db, translation.language_id)
    
    history = TranslationHistory(
        translation_id=translation.id,
        language_code=language.code if language else "unknown",
        key=translation.key,
        old_value=old_value,
        new_value=new_value,
        user_id=user_id
    )
    
    db.add(history)
    db.commit()
    db.refresh(history)
    
    return history


def get_translation_history(db: Session, translation_id: int, skip: int = 0, limit: int = 100) -> List[TranslationHistory]:
    """Get history for a specific translation."""
    return db.query(TranslationHistory).filter(
        TranslationHistory.translation_id == translation_id
    ).order_by(TranslationHistory.created_at.desc()).offset(skip).limit(limit).all()


def get_translation_stats(db: Session) -> List[TranslationStatistics]:
    """
    Get translation statistics by language.
    
    Returns statistics including total keys, translated keys, and completion percentage.
    """
    stats = []
    languages = get_languages(db)
    
    # Get total number of unique keys
    total_keys_count = db.query(func.count(func.distinct(Translation.key))).scalar() or 0
    
    for lang in languages:
        # Count translated keys for this language
        translated_count = db.query(func.count(func.distinct(Translation.key))).filter(
            Translation.language_id == lang.id
        ).scalar() or 0
        
        # Count keys that need review
        needs_review_count = db.query(func.count(func.distinct(Translation.key))).filter(
            Translation.language_id == lang.id,
            Translation.needs_review == True
        ).scalar() or 0
        
        # Calculate missing keys
        missing_count = total_keys_count - translated_count
        
        # Calculate completion percentage
        completion_percentage = (translated_count / total_keys_count * 100) if total_keys_count > 0 else 100.0
        
        stats.append(TranslationStatistics(
            language_code=lang.code,
            language_name=lang.name,
            total_keys=total_keys_count,
            translated_keys=translated_count,
            missing_keys=missing_count,
            needs_review=needs_review_count,
            completion_percentage=round(completion_percentage, 2)
        ))
    
    return stats


async def import_translations(db: Session, language_code: str, file: UploadFile) -> Dict[str, Any]:
    """
    Import translations from a file.
    
    Args:
        db: Database session
        language_code: Language code for the translations
        file: Uploaded file with translations
        
    Returns:
        Statistics about the import operation
    """
    language = get_language_by_code(db, language_code)
    if not language:
        raise HTTPException(status_code=404, detail=f"Language with code {language_code} not found")
    
    result = {
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "errors": []
    }
    
    # Read file content
    content = await file.read()
    
    # Process based on file type
    if file.filename.endswith(".csv"):
        # Process CSV file
        csv_content = content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        for row in csv_reader:
            try:
                # Extract data from CSV row
                key = row.get("key")
                group_name = row.get("group", "default")
                value = row.get("value")
                context = row.get("context")
                
                if not key or not value:
                    result["skipped"] += 1
                    continue
                
                # Get or create group
                group = get_translation_group_by_name(db, group_name)
                if not group:
                    group = create_translation_group(db, group_name)
                
                # Check if translation exists
                existing_translation = get_translation_by_key(db, language.id, group.id, key)
                
                if existing_translation:
                    # Update existing translation
                    update_translation(db, existing_translation.id, TranslationUpdate(
                        value=value,
                        context=context,
                        is_machine_translated=False,
                        needs_review=False
                    ))
                    result["updated"] += 1
                else:
                    # Create new translation
                    create_translation(db, TranslationCreate(
                        language_code=language_code,
                        group_name=group_name,
                        key=key,
                        value=value,
                        context=context,
                        is_machine_translated=False,
                        needs_review=False
                    ))
                    result["added"] += 1
            
            except Exception as e:
                result["errors"].append(str(e))
                result["skipped"] += 1
    
    elif file.filename.endswith(".json"):
        # Process JSON file
        try:
            json_data = json.loads(content)
            
            if isinstance(json_data, dict):
                for group_name, translations in json_data.items():
                    # Get or create group
                    group = get_translation_group_by_name(db, group_name)
                    if not group:
                        group = create_translation_group(db, group_name)
                    
                    if isinstance(translations, dict):
                        for key, value in translations.items():
                            try:
                                # Handle different value formats
                                translation_value = value
                                context = None
                                plural_forms = None
                                
                                if isinstance(value, dict):
                                    # Extract more complex structure
                                    translation_value = value.get("value", "")
                                    context = value.get("context")
                                    plural_forms = value.get("plural_forms")
                                
                                # Check if translation exists
                                existing_translation = get_translation_by_key(db, language.id, group.id, key)
                                
                                if existing_translation:
                                    # Update existing translation
                                    update_translation(db, existing_translation.id, TranslationUpdate(
                                        value=translation_value,
                                        context=context,
                                        plural_forms=plural_forms,
                                        is_machine_translated=False,
                                        needs_review=False
                                    ))
                                    result["updated"] += 1
                                else:
                                    # Create new translation
                                    create_translation(db, TranslationCreate(
                                        language_code=language_code,
                                        group_name=group_name,
                                        key=key,
                                        value=translation_value,
                                        context=context,
                                        plural_forms=plural_forms,
                                        is_machine_translated=False,
                                        needs_review=False
                                    ))
                                    result["added"] += 1
                            
                            except Exception as e:
                                result["errors"].append(f"Error processing key {key}: {str(e)}")
                                result["skipped"] += 1
            else:
                result["errors"].append("Invalid JSON format. Expected a dictionary.")
        
        except json.JSONDecodeError:
            result["errors"].append("Invalid JSON file.")
    
    else:
        result["errors"].append(f"Unsupported file format: {file.filename}")
    
    return result


def export_translations_to_dict(db: Session, language_code: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Export translations to a nested dictionary format.
    
    Args:
        db: Database session
        language_code: Optional language code to filter by
        
    Returns:
        Dictionary of translations grouped by translation group
    """
    result = {}
    
    # Get translations
    translations = get_translations(db, language_code=language_code, limit=10000)
    
    for translation in translations:
        group_name = translation.group.name
        
        # Initialize group if it doesn't exist
        if group_name not in result:
            result[group_name] = {}
        
        # Add translation to group
        value_dict = {
            "value": translation.value,
        }
        
        if translation.context:
            value_dict["context"] = translation.context
        
        if translation.plural_forms:
            value_dict["plural_forms"] = translation.plural_forms
        
        # If it's a simple translation, just store the value string
        if len(value_dict) == 1:
            result[group_name][translation.key] = translation.value
        else:
            # Otherwise store the full object
            result[group_name][translation.key] = value_dict
    
    return result
