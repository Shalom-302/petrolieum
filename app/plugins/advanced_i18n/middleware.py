"""
Middleware for the Advanced Internationalization plugin.

This middleware detects the preferred language from HTTP headers and handles
language switching in the application.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import re
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.plugins.advanced_i18n.utils import get_default_language_code


class LanguageDetectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that detects the preferred language from HTTP headers and cookies.
    
    It sets the detected language in the request state and adds a Content-Language
    header to the response.
    """
    
    def __init__(
        self, 
        app: ASGIApp,
        cookie_name: str = "preferred_language",
        header_name: str = "Accept-Language",
        available_languages: List[str] = None,
        default_language: str = "en"
    ):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.available_languages = available_languages or []
        self.default_language = default_language
    
    async def dispatch(self, request: Request, call_next):
        """Process the request through the middleware."""
        # Try to get language from cookie first
        language = self._get_language_from_cookie(request)
        
        # If no cookie, try Accept-Language header
        if not language:
            language = self._get_language_from_header(request)
        
        # If still no language, use default
        if not language:
            language = self._get_default_language()
        
        # Set language in request state for easy access in route handlers
        request.state.language = language
        
        # Process the request
        response = await call_next(request)
        
        # Add Content-Language header to response
        response.headers["Content-Language"] = language
        
        return response
    
    def _get_language_from_cookie(self, request: Request) -> Optional[str]:
        """Get preferred language from cookie."""
        if self.cookie_name in request.cookies:
            language = request.cookies[self.cookie_name]
            if language in self.available_languages:
                return language
        return None
    
    def _get_language_from_header(self, request: Request) -> Optional[str]:
        """Get preferred language from Accept-Language header."""
        accept_language = request.headers.get(self.header_name)
        if accept_language:
            # Parse Accept-Language header using regex
            # Format: "en-US,en;q=0.9,fr;q=0.8"
            matches = re.findall(r'([a-zA-Z\-]+)(?:;q=([0-9\.]+))?', accept_language)
            
            # Sort by quality value, defaulting to 1.0 if not specified
            languages = [(lang, float(quality or '1.0')) for lang, quality in matches]
            languages.sort(key=lambda x: x[1], reverse=True)
            
            # Find the first language that is in our available languages
            for lang_code, _ in languages:
                # Extract primary language code (e.g., "en" from "en-US")
                primary_code = lang_code.split('-')[0].lower()
                
                # Check if full or primary code is in available languages
                if lang_code in self.available_languages:
                    return lang_code
                if primary_code in self.available_languages:
                    return primary_code
        
        return None
    
    def _get_default_language(self) -> str:
        """Get the default language."""
        # Try to get default language from available languages
        if self.available_languages:
            # Try to get a database connection to fetch the default language
            try:
                # This is a bit of a hack to get a database connection
                # In a real implementation, you might want to inject the session
                db = next(get_db())
                default_lang = get_default_language_code(db)
                if default_lang:
                    return default_lang
            except:
                # If database access fails, fall back to first available language
                return self.available_languages[0]
        
        # Fallback to hardcoded default
        return self.default_language
