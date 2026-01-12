# -*- coding: utf-8 -*-
"""
Anki-Pix: Add-on pour ajouter des images Pixabay aux notes Anki.

Ce module s'intègre dans le menu 'Édition' du Browser Anki
pour permettre l'ajout automatique d'images aux notes sélectionnées.
"""

import json
import os
from typing import Optional, Dict, Any

from aqt import mw
from aqt.browser import Browser
from aqt.qt import (
    QAction, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QComboBox, QPushButton, QProgressDialog,
    Qt
)
from aqt.utils import showInfo, showWarning, askUser

# Import local module
from . import pixabay


# ============================================================================
# Configuration Management
# ============================================================================

def get_config() -> Dict[str, Any]:
    """Load add-on configuration."""
    addon_dir = os.path.dirname(__file__)
    config_path = os.path.join(addon_dir, "config.json")
    
    default_config = {
        "pixabay_api_key": "",
        "source_field": "Source",
        "image_field": "Image",
        "image_type": "illustration"
    }
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Merge with defaults
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception:
        return default_config


def save_config(config: Dict[str, Any]) -> None:
    """Save add-on configuration."""
    addon_dir = os.path.dirname(__file__)
    config_path = os.path.join(addon_dir, "config.json")
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Anki-Pix: Config save error - {e}")


# ============================================================================
# Configuration Dialog
# ============================================================================

class ConfigDialog(QDialog):
    """Dialog for configuring Anki-Pix settings."""
    
    def __init__(self, parent=None, config: Dict[str, Any] = None):
        super().__init__(parent)
        self.config = config or get_config()
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Anki-Pix - Configuration")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # API Key
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("Clé API Pixabay:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config.get("pixabay_api_key", ""))
        self.api_key_input.setPlaceholderText("Entrez votre clé API...")
        api_layout.addWidget(self.api_key_input)
        layout.addLayout(api_layout)
        
        # Source Field
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Champ source (mot-clé):"))
        self.source_field_combo = QComboBox()
        self.source_field_combo.addItems(["Front", "Back", "Source"])
        self.source_field_combo.setEditable(True)  # Allow custom values
        current_source = self.config.get("source_field", "Source")
        index = self.source_field_combo.findText(current_source, Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            self.source_field_combo.setCurrentIndex(index)
        else:
            self.source_field_combo.setCurrentText(current_source)
        source_layout.addWidget(self.source_field_combo)
        layout.addLayout(source_layout)
        
        # Image Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type d'image:"))
        self.image_type_combo = QComboBox()
        self.image_type_combo.addItems(["illustration", "photo", "vector", "all"])
        current_type = self.config.get("image_type", "illustration")
        index = self.image_type_combo.findText(current_type)
        if index >= 0:
            self.image_type_combo.setCurrentIndex(index)
        type_layout.addWidget(self.image_type_combo)
        layout.addLayout(type_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Sauvegarder")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
    
    def get_config(self) -> Dict[str, Any]:
        """Return the configuration from dialog inputs."""
        return {
            "pixabay_api_key": self.api_key_input.text().strip(),
            "source_field": self.source_field_combo.currentText().strip() or "Front",
            "image_type": self.image_type_combo.currentText()
        }


# ============================================================================
# Main Processing
# ============================================================================

def get_field_index(note, field_name: str) -> Optional[int]:
    """Get the index of a field by name, or None if not found."""
    field_names = [f["name"] for f in note.note_type()["flds"]]
    try:
        return field_names.index(field_name)
    except ValueError:
        return None


def process_selected_notes(browser: Browser) -> None:
    """
    Process selected notes: search Pixabay and add images.
    
    The image is appended to the source field (Front/Back) after the text.
    
    Args:
        browser: The Anki browser instance.
    """
    config = get_config()
    
    # Check API key
    if not config.get("pixabay_api_key"):
        dialog = ConfigDialog(browser, config)
        if dialog.exec():
            config = dialog.get_config()
            save_config(config)
        else:
            return
        
        if not config.get("pixabay_api_key"):
            showWarning("Clé API Pixabay requise pour continuer.")
            return
    
    # Get selected notes
    selected_nids = browser.selectedNotes()
    if not selected_nids:
        showInfo("Aucune note sélectionnée.")
        return
    
    source_field = config["source_field"]
    api_key = config["pixabay_api_key"]
    image_type = config.get("image_type", "illustration")
    
    # Filter notes that need processing
    notes_to_process = []
    for nid in selected_nids:
        note = mw.col.get_note(nid)
        
        source_idx = get_field_index(note, source_field)
        
        if source_idx is None:
            continue  # Skip notes without source field
        
        field_content = note.fields[source_idx]
        
        # Check if field already has an image
        if "<img" in field_content.lower():
            continue  # Skip, already has image
        
        # Extract text (keyword) - strip HTML tags for search
        import re
        keyword = re.sub(r'<[^>]+>', '', field_content).strip()
        
        if keyword:
            notes_to_process.append((note, source_idx, keyword, field_content))
    
    if not notes_to_process:
        showInfo("Aucune note à traiter.\n\nToutes les notes sélectionnées ont déjà une image ou le champ source est vide.")
        return
    
    # Confirm processing
    if not askUser(f"Traiter {len(notes_to_process)} note(s) ?\n\nCela va rechercher et télécharger des images depuis Pixabay."):
        return
    
    # Progress dialog
    progress = QProgressDialog(
        "Traitement des images...", 
        "Annuler", 
        0, 
        len(notes_to_process),
        browser
    )
    progress.setWindowTitle("Anki-Pix")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.show()
    
    processed = 0
    failed = 0
    
    for i, (note, source_idx, keyword, original_content) in enumerate(notes_to_process):
        if progress.wasCanceled():
            break
        
        progress.setValue(i)
        progress.setLabelText(f"Recherche: {keyword}...")
        mw.app.processEvents()
        
        # Search for image
        url = pixabay.search_image(keyword, api_key, image_type)
        if not url:
            failed += 1
            continue
        
        # Download and add to Anki media
        filename = pixabay.download_to_anki(url, keyword, mw.col)
        if not filename:
            failed += 1
            continue
        
        # Append image after the text in the same field
        note.fields[source_idx] = f'{original_content}<br><img src="{filename}">'
        mw.col.update_note(note)
        processed += 1
    
    progress.setValue(len(notes_to_process))
    progress.close()
    
    # Refresh browser
    browser.model.reset()
    
    # Show summary
    showInfo(
        f"Traitement terminé !\n\n"
        f"✓ Images ajoutées: {processed}\n"
        f"✗ Échecs: {failed}\n"
        f"○ Ignorées: {len(selected_nids) - len(notes_to_process)}"
    )


def open_config_dialog(browser: Browser) -> None:
    """Open the configuration dialog."""
    config = get_config()
    dialog = ConfigDialog(browser, config)
    if dialog.exec():
        new_config = dialog.get_config()
        save_config(new_config)
        showInfo("Configuration sauvegardée !")


# ============================================================================
# Browser Menu Setup
# ============================================================================

def setup_browser_menu(browser: Browser) -> None:
    """
    Configure the menu in Anki Browser.
    
    Adds Anki-Pix actions to the Edit menu.
    """
    # Main action: Add images
    action_add = QAction("Anki-Pix: Ajouter Images", browser)
    action_add.setShortcut("Ctrl+Shift+P")
    action_add.triggered.connect(lambda: process_selected_notes(browser))
    
    # Config action
    action_config = QAction("Anki-Pix: Configuration...", browser)
    action_config.triggered.connect(lambda: open_config_dialog(browser))
    
    # Add to Edit menu
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(action_add)
    browser.form.menuEdit.addAction(action_config)


def on_browser_setup_menus(browser: Browser) -> None:
    """Hook called when Browser is initialized."""
    setup_browser_menu(browser)


# ============================================================================
# Add-on Initialization
# ============================================================================

from aqt import gui_hooks
gui_hooks.browser_menus_did_init.append(on_browser_setup_menus)

print("Anki-Pix: Add-on chargé avec succès!")
