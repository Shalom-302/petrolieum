"""
Main router for the Advanced Internationalization plugin.

This module provides the API endpoints for managing languages and translations.
"""

from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
import json
from starlette.responses import FileResponse, StreamingResponse, Response

from app.core.db import get_db
from app.plugins.advanced_i18n import crud, schemas, models
from app.plugins.advanced_i18n.utils import export_translations_to_csv


router = APIRouter()


@router.get("/languages", response_model=List[schemas.Language])
def get_languages(
    skip: int = 0, 
    limit: int = 100, 
    only_enabled: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get all languages.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        only_enabled: Whether to only include enabled languages
        db: Database session
        
    Returns:
        List of languages
    """
    return crud.get_languages(db, skip=skip, limit=limit, only_enabled=only_enabled)


@router.get("/languages/default", response_model=schemas.Language)
def get_default_language(db: Session = Depends(get_db)):
    """
    Get the default language.
    
    Args:
        db: Database session
        
    Returns:
        The default language
    """
    language = crud.get_default_language(db)
    if not language:
        raise HTTPException(status_code=404, detail="No default language found")
    return language


@router.get("/languages/{language_id}", response_model=schemas.Language)
def get_language(language_id: int, db: Session = Depends(get_db)):
    """
    Get a language by ID.
    
    Args:
        language_id: ID of the language
        db: Database session
        
    Returns:
        The language
    """
    language = crud.get_language(db, language_id)
    if not language:
        raise HTTPException(status_code=404, detail=f"Language with ID {language_id} not found")
    return language


@router.post("/languages", response_model=schemas.Language)
def create_language(language: schemas.LanguageCreate, db: Session = Depends(get_db)):
    """
    Create a new language.
    
    Args:
        language: Language data
        db: Database session
        
    Returns:
        The created language
    """
    return crud.create_language(db, language)


@router.put("/languages/{language_id}", response_model=schemas.Language)
def update_language(language_id: int, language: schemas.LanguageUpdate, db: Session = Depends(get_db)):
    """
    Update a language.
    
    Args:
        language_id: ID of the language to update
        language: New language data
        db: Database session
        
    Returns:
        The updated language
    """
    updated_language = crud.update_language(db, language_id, language)
    if not updated_language:
        raise HTTPException(status_code=404, detail=f"Language with ID {language_id} not found")
    return updated_language


@router.delete("/languages/{language_id}", response_model=dict)
def delete_language(language_id: int, db: Session = Depends(get_db)):
    """
    Delete a language.
    
    Args:
        language_id: ID of the language to delete
        db: Database session
        
    Returns:
        Success message
    """
    success = crud.delete_language(db, language_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Language with ID {language_id} not found")
    return {"message": "Language deleted successfully"}


@router.get("/groups", response_model=List[schemas.TranslationGroup])
def get_translation_groups(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get all translation groups.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of translation groups
    """
    return crud.get_translation_groups(db, skip=skip, limit=limit)


@router.get("/groups/{group_id}", response_model=schemas.TranslationGroup)
def get_translation_group(group_id: int, db: Session = Depends(get_db)):
    """
    Get a translation group by ID.
    
    Args:
        group_id: ID of the translation group
        db: Database session
        
    Returns:
        The translation group
    """
    group = crud.get_translation_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail=f"Translation group with ID {group_id} not found")
    return group


@router.post("/groups", response_model=schemas.TranslationGroup)
def create_translation_group(group: schemas.TranslationGroupCreate, db: Session = Depends(get_db)):
    """
    Create a new translation group.
    
    Args:
        group: Translation group data
        db: Database session
        
    Returns:
        The created translation group
    """
    return crud.create_translation_group(db, group.name, group.description)


@router.put("/groups/{group_id}", response_model=schemas.TranslationGroup)
def update_translation_group(
    group_id: int, 
    group: schemas.TranslationGroupUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update a translation group.
    
    Args:
        group_id: ID of the translation group to update
        group: New translation group data
        db: Database session
        
    Returns:
        The updated translation group
    """
    updated_group = crud.update_translation_group(
        db, 
        group_id, 
        name=group.name, 
        description=group.description
    )
    if not updated_group:
        raise HTTPException(status_code=404, detail=f"Translation group with ID {group_id} not found")
    return updated_group


@router.delete("/groups/{group_id}", response_model=dict)
def delete_translation_group(group_id: int, db: Session = Depends(get_db)):
    """
    Delete a translation group.
    
    Args:
        group_id: ID of the translation group to delete
        db: Database session
        
    Returns:
        Success message
    """
    success = crud.delete_translation_group(db, group_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Translation group with ID {group_id} not found")
    return {"message": "Translation group deleted successfully"}


@router.get("/translations", response_model=List[schemas.Translation])
def get_translations(
    language_code: Optional[str] = None,
    group_name: Optional[str] = None,
    key_prefix: Optional[str] = None,
    needs_review: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get translations with optional filtering.
    
    Args:
        language_code: Optional language code to filter by
        group_name: Optional group name to filter by
        key_prefix: Optional key prefix to filter by
        needs_review: Filter translations that need review
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of translations matching the criteria
    """
    return crud.get_translations(
        db, 
        language_code=language_code,
        group_name=group_name,
        key_prefix=key_prefix,
        skip=skip,
        limit=limit,
        needs_review=needs_review
    )


@router.get("/translations/{translation_id}", response_model=schemas.Translation)
def get_translation(translation_id: int, db: Session = Depends(get_db)):
    """
    Get a translation by ID.
    
    Args:
        translation_id: ID of the translation
        db: Database session
        
    Returns:
        The translation
    """
    translation = crud.get_translation(db, translation_id)
    if not translation:
        raise HTTPException(status_code=404, detail=f"Translation with ID {translation_id} not found")
    return translation


@router.post("/translations", response_model=schemas.Translation)
def create_translation(translation: schemas.TranslationCreate, db: Session = Depends(get_db)):
    """
    Create a new translation.
    
    Args:
        translation: Translation data
        db: Database session
        
    Returns:
        The created translation
    """
    return crud.create_translation(db, translation)


@router.put("/translations/{translation_id}", response_model=schemas.Translation)
def update_translation(
    translation_id: int, 
    translation: schemas.TranslationUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update a translation.
    
    Args:
        translation_id: ID of the translation to update
        translation: New translation data
        db: Database session
        
    Returns:
        The updated translation
    """
    updated_translation = crud.update_translation(db, translation_id, translation)
    if not updated_translation:
        raise HTTPException(status_code=404, detail=f"Translation with ID {translation_id} not found")
    return updated_translation


@router.delete("/translations/{translation_id}", response_model=dict)
def delete_translation(translation_id: int, db: Session = Depends(get_db)):
    """
    Delete a translation.
    
    Args:
        translation_id: ID of the translation to delete
        db: Database session
        
    Returns:
        Success message
    """
    success = crud.delete_translation(db, translation_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Translation with ID {translation_id} not found")
    return {"message": "Translation deleted successfully"}


@router.get("/translations/{translation_id}/history", response_model=List[schemas.TranslationHistory])
def get_translation_history(
    translation_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Get history for a specific translation.
    
    Args:
        translation_id: ID of the translation
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        List of translation history records
    """
    return crud.get_translation_history(db, translation_id, skip=skip, limit=limit)


@router.get("/stats", response_model=List[schemas.TranslationStatistics])
def get_translation_stats(db: Session = Depends(get_db)):
    """
    Get translation statistics by language.
    
    Args:
        db: Database session
        
    Returns:
        List of translation statistics by language
    """
    return crud.get_translation_stats(db)


@router.get("/export", response_class=StreamingResponse)
def export_translations(
    language_code: Optional[str] = None,
    format: str = Query("csv", regex="^(csv|json)$"),
    db: Session = Depends(get_db)
):
    """
    Export translations.
    
    Args:
        language_code: Optional language code to filter by
        format: Export format (csv or json)
        db: Database session
        
    Returns:
        Exported translations in the specified format
    """
    if format == "csv":
        return export_translations_to_csv(db, language_code)
    elif format == "json":
        translations_dict = crud.export_translations_to_dict(db, language_code)
        return Response(
            content=json.dumps(translations_dict, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=translations_{language_code or 'all'}.json"}
        )


@router.post("/import", response_model=schemas.ImportResult)
async def import_translations(
    language_code: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Import translations from a file.
    
    Args:
        language_code: Language code for the translations
        file: Uploaded file with translations
        db: Database session
        
    Returns:
        Statistics about the import operation
    """
    result = await crud.import_translations(db, language_code, file)
    return schemas.ImportResult(
        added=result["added"],
        updated=result["updated"],
        skipped=result["skipped"],
        errors=result["errors"]
    )


@router.get("/js/{language_code}")
def get_js_translations(language_code: str, db: Session = Depends(get_db)):
    """
    Get translations as a JavaScript file.
    
    Args:
        language_code: Language code
        db: Database session
        
    Returns:
        JavaScript file with translations
    """
    from app.plugins.advanced_i18n.utils import generate_js_translations
    
    js_content = generate_js_translations(db, language_code)
    
    return Response(
        content=js_content,
        media_type="application/javascript",
        headers={"Content-Disposition": f"inline; filename=translations_{language_code}.js"}
    )
