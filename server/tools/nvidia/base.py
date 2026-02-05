#!/usr/bin/env python3
"""
Base class for NVIDIA Health API clients.
Provides common functionality for RFdiffusion, AlphaFold, and other NVIDIA Health API integrations.
"""

import os
import logging
from typing import Dict, Any, Optional
import aiohttp
import ssl

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

logger = logging.getLogger(__name__)


class NVIDIAHealthClient:
    """Base class for NVIDIA Health API clients"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize base client with API key and base URL
        
        Args:
            api_key: NVIDIA API key (defaults to NVCF_RUN_KEY env var)
            base_url: Base API URL (subclasses should provide default)
        """
        self.api_key = api_key or os.getenv("NVCF_RUN_KEY")
        if not self.api_key:
            raise ValueError("NVCF_RUN_KEY environment variable or api_key parameter required")
        
        self.base_url = base_url
        if not self.base_url:
            raise ValueError("base_url must be provided by subclass or constructor")
        
        self.headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        # Common timeout and retry configuration
        self.request_timeout = int(os.getenv("NIMS_REQUEST_TIMEOUT", "180"))  # seconds
        self.post_retries = int(os.getenv("NIMS_POST_RETRIES", "3"))  # transient 5xx retries
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        return self.headers.copy()
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for aiohttp requests"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Try to load certifi bundle if available
        if certifi is not None:
            try:
                ssl_context.load_verify_locations(certifi.where())
            except Exception as exc:
                logger.warning(f"Failed to load certifi bundle: {exc}")
        
        return ssl_context
    
    def _create_session(self) -> aiohttp.ClientSession:
        """Create aiohttp session with SSL context"""
        ssl_context = self._create_ssl_context()
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        return aiohttp.ClientSession(connector=connector, timeout=timeout)
    
    def _handle_error(self, response: aiohttp.ClientResponse, error_text: str) -> Dict[str, Any]:
        """
        Handle API error responses with user-friendly messages
        
        Args:
            response: aiohttp response object
            error_text: Error text from response
            
        Returns:
            Dictionary with error information
        """
        status = response.status
        
        # Try to extract detailed error message from JSON response
        try:
            # Note: response.json() may have already been consumed, so we use error_text
            import json
            if error_text.strip().startswith('{'):
                error_json = json.loads(error_text)
                if isinstance(error_json, dict):
                    detail = error_json.get("detail", error_text)
                    error_text = detail
        except:
            pass
        
        # Map HTTP status codes to user-friendly messages
        if status == 401:
            return {
                "error": "Authentication failed. Please check your NVIDIA API key configuration.",
                "status": "auth_error",
                "http_status": status
            }
        elif status == 403:
            return {
                "error": "Access forbidden. Please verify your API key has the required permissions.",
                "status": "auth_error",
                "http_status": status
            }
        elif status == 429:
            return {
                "error": "Rate limit exceeded. Please try again later.",
                "status": "rate_limit",
                "http_status": status
            }
        elif status == 422:
            return {
                "error": f"Validation error: {error_text}",
                "status": "validation_error",
                "http_status": status
            }
        elif status in (502, 503, 504):
            return {
                "error": "Service temporarily unavailable. Please try again later.",
                "status": "service_unavailable",
                "http_status": status
            }
        else:
            return {
                "error": f"API request failed: HTTP {status}: {error_text}",
                "status": "request_failed",
                "http_status": status
            }
