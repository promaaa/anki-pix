# -*- coding: utf-8 -*-
"""
Pixabay API module for Anki-Pix.

Provides functions to search and download images from Pixabay,
optimized for integration with Anki's media system.
"""

import os
import uuid
from typing import Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # Will be handled at runtime


PIXABAY_API_URL = "https://pixabay.com/api/"


def search_image(
    keyword: str,
    api_key: str,
    image_type: str = "illustration"
) -> Optional[str]:
    """
    Search for an image on Pixabay.
    
    Args:
        keyword: The search term.
        api_key: Pixabay API key.
        image_type: Type of image ("illustration", "photo", "vector", "all").
        
    Returns:
        URL of the found image, or None if not found.
    """
    if not requests:
        print("Anki-Pix: requests module not available")
        return None
    
    if not api_key:
        print("Anki-Pix: API key not configured")
        return None
    
    params = {
        "key": api_key,
        "q": keyword,
        "image_type": image_type,
        "lang": "fr",
        "safesearch": "true",
        "per_page": 3,
    }
    
    try:
        response = requests.get(PIXABAY_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Fallback to photo if no illustrations found
        if data.get("totalHits", 0) == 0 and image_type == "illustration":
            params["image_type"] = "photo"
            response = requests.get(PIXABAY_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        
        if data.get("totalHits", 0) > 0:
            return data["hits"][0]["webformatURL"]
        
        return None
        
    except Exception as e:
        print(f"Anki-Pix: Search error - {e}")
        return None


def download_image(url: str, keyword: str) -> Optional[Tuple[bytes, str]]:
    """
    Download an image from URL.
    
    Args:
        url: The image URL.
        keyword: The keyword (for filename generation).
        
    Returns:
        Tuple of (image_bytes, filename) or None on error.
    """
    if not requests:
        return None
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Determine extension from Content-Type
        content_type = response.headers.get("Content-Type", "")
        if "png" in content_type:
            ext = ".png"
        elif "gif" in content_type:
            ext = ".gif"
        else:
            ext = ".jpg"
        
        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        safe_keyword = "".join(c if c.isalnum() else "_" for c in keyword)
        filename = f"anki_pix_{safe_keyword}_{unique_id}{ext}"
        
        return (response.content, filename)
        
    except Exception as e:
        print(f"Anki-Pix: Download error - {e}")
        return None


def download_to_anki(url: str, keyword: str, col) -> Optional[str]:
    """
    Download an image and add it to Anki's media folder.
    
    Args:
        url: The image URL.
        keyword: The keyword (for filename generation).
        col: Anki collection object (mw.col).
        
    Returns:
        The filename in Anki's media folder, or None on error.
    """
    result = download_image(url, keyword)
    if not result:
        return None
    
    image_bytes, filename = result
    
    try:
        # Add to Anki's media folder
        # col.media.write_data() returns the actual filename used
        actual_filename = col.media.write_data(filename, image_bytes)
        return actual_filename
    except Exception as e:
        print(f"Anki-Pix: Media write error - {e}")
        return None
