#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anki-Pix Engine CLI

Outil en ligne de commande pour simuler le flux de travail complet
de l'add-on Anki-Pix sans dépendre de l'application Anki.

Usage:
    export PIXABAY_API_KEY="votre_clé_api"
    python engine.py
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional, List, Dict

import requests
from dotenv import load_dotenv


# Charger les variables d'environnement depuis .env si présent
load_dotenv()

# Configuration des chemins
SCRIPT_DIR = Path(__file__).parent
MOCK_DB_PATH = SCRIPT_DIR / "mock_db.json"
MEDIA_DIR = SCRIPT_DIR / "test_media"

# Configuration de l'API Pixabay
PIXABAY_API_URL = "https://pixabay.com/api/"
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def search_pixabay(keyword: str) -> Optional[str]:
    """
    Recherche une image sur Pixabay pour un mot-clé donné.
    
    Priorité aux illustrations vectorielles pour un rendu plus propre.
    
    Args:
        keyword: Le mot-clé à rechercher.
        
    Returns:
        L'URL de l'image trouvée, ou None si aucune image disponible.
    """
    if not PIXABAY_API_KEY:
        logger.error("Clé API Pixabay non configurée! Définissez PIXABAY_API_KEY.")
        return None
    
    logger.info(f"Recherche de '{keyword}'...")
    
    # Paramètres de recherche - priorité aux illustrations
    params = {
        "key": PIXABAY_API_KEY,
        "q": keyword,
        "image_type": "illustration",  # Priorité illustrations
        "lang": "fr",
        "safesearch": "true",
        "per_page": 3,
    }
    
    try:
        response = requests.get(PIXABAY_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Si pas d'illustrations, essayer avec tous les types
        if data.get("totalHits", 0) == 0:
            logger.info(f"Aucune illustration trouvée, recherche d'images photo...")
            params["image_type"] = "photo"
            response = requests.get(PIXABAY_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        
        if data.get("totalHits", 0) > 0:
            # Prendre la première image (la plus pertinente)
            image_url = data["hits"][0]["webformatURL"]
            logger.info(f"Image trouvée: {image_url}")
            return image_url
        else:
            logger.warning(f"Aucune image trouvée pour '{keyword}'")
            return None
            
    except requests.RequestException as e:
        logger.error(f"Erreur lors de la recherche: {e}")
        return None


def download_image(url: str, keyword: str) -> Optional[str]:
    """
    Télécharge une image et la sauvegarde avec un nom unique.
    
    Args:
        url: L'URL de l'image à télécharger.
        keyword: Le mot-clé associé (pour le nom du fichier).
        
    Returns:
        Le nom du fichier sauvegardé, ou None en cas d'erreur.
    """
    # Créer le dossier media s'il n'existe pas
    MEDIA_DIR.mkdir(exist_ok=True)
    
    logger.info("Téléchargement en cours...")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Déterminer l'extension depuis le Content-Type ou l'URL
        content_type = response.headers.get("Content-Type", "")
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        elif "gif" in content_type:
            ext = ".gif"
        else:
            # Fallback: extraire de l'URL
            ext = Path(url.split("?")[0]).suffix or ".jpg"
        
        # Générer un nom unique
        unique_id = uuid.uuid4().hex[:8]
        # Nettoyer le keyword pour le nom de fichier
        safe_keyword = "".join(c if c.isalnum() else "_" for c in keyword)
        filename = f"{safe_keyword}_{unique_id}{ext}"
        
        # Sauvegarder l'image
        filepath = MEDIA_DIR / filename
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        logger.info(f"Fichier sauvegardé sous: test_media/{filename}")
        return filename
        
    except requests.RequestException as e:
        logger.error(f"Erreur lors du téléchargement: {e}")
        return None
    except IOError as e:
        logger.error(f"Erreur lors de la sauvegarde: {e}")
        return None


def load_mock_db() -> List[Dict]:
    """
    Charge les notes depuis le fichier JSON mock.
    
    Returns:
        Liste des notes, ou liste vide si erreur.
    """
    logger.info("Chargement de la base de données...")
    
    try:
        with open(MOCK_DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            notes = data.get("notes", [])
            logger.info(f"{len(notes)} notes trouvées dans la base")
            return notes
    except FileNotFoundError:
        logger.error(f"Fichier non trouvé: {MOCK_DB_PATH}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Erreur de parsing JSON: {e}")
        return []


def save_mock_db(notes: List[Dict]) -> bool:
    """
    Sauvegarde les notes dans le fichier JSON mock.
    
    Args:
        notes: Liste des notes à sauvegarder.
        
    Returns:
        True si succès, False sinon.
    """
    try:
        with open(MOCK_DB_PATH, "w", encoding="utf-8") as f:
            json.dump({"notes": notes}, f, ensure_ascii=False, indent=2)
        logger.info("Base de données sauvegardée")
        return True
    except IOError as e:
        logger.error(f"Erreur lors de la sauvegarde: {e}")
        return False


def process_notes() -> None:
    """
    Traite les notes de la base mock.
    
    Filtre les notes sans image, recherche sur Pixabay,
    télécharge et met à jour la base.
    """
    notes = load_mock_db()
    if not notes:
        return
    
    # Filtrer les notes sans image
    notes_to_process = [n for n in notes if not n.get("Image")]
    logger.info(f"{len(notes_to_process)} notes à traiter (sans image)")
    
    if not notes_to_process:
        logger.info("Toutes les notes ont déjà une image!")
        return
    
    print("-" * 50)
    
    processed = 0
    failed = 0
    
    for note in notes_to_process:
        note_id = note.get("id", "?")
        keyword = note.get("Source", "")
        
        if not keyword:
            logger.warning(f"Note ID {note_id}: champ 'Source' vide, ignorée")
            continue
        
        print()  # Ligne vide pour lisibilité
        
        # Rechercher l'image
        image_url = search_pixabay(keyword)
        if not image_url:
            failed += 1
            continue
        
        # Télécharger l'image
        filename = download_image(image_url, keyword)
        if not filename:
            failed += 1
            continue
        
        # Mettre à jour la note
        note["Image"] = filename
        logger.info(f"Note ID {note_id} mise à jour")
        processed += 1
    
    print()
    print("-" * 50)
    
    # Sauvegarder les modifications
    if processed > 0:
        save_mock_db(notes)
    
    # Résumé
    print()
    logger.info(f"=== Résumé ===")
    logger.info(f"Notes traitées avec succès: {processed}")
    logger.info(f"Notes en échec: {failed}")
    logger.info(f"Notes ignorées (déjà avec image): {len(notes) - len(notes_to_process)}")


def main() -> None:
    """Point d'entrée principal du CLI."""
    print("=" * 50)
    print("  Anki-Pix Engine CLI")
    print("  Moteur de test autonome")
    print("=" * 50)
    print()
    
    if not PIXABAY_API_KEY:
        logger.error("ERREUR: Variable PIXABAY_API_KEY non définie!")
        logger.error("Définissez-la avec: export PIXABAY_API_KEY=\"votre_clé\"")
        logger.error("Ou créez un fichier .env avec: PIXABAY_API_KEY=votre_clé")
        sys.exit(1)
    
    process_notes()
    
    print()
    print("=" * 50)
    print("  Traitement terminé")
    print("=" * 50)


if __name__ == "__main__":
    main()
