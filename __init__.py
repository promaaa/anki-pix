# -*- coding: utf-8 -*-
"""
Anki-Pix: Add-on pour ajouter des images Pixabay aux notes Anki.

Ce module s'intègre dans le menu 'Édition' du Browser Anki
pour permettre l'ajout automatique d'images aux notes sélectionnées.
"""

import json
import os
import re
from typing import Optional, Dict, Any, List

from aqt import mw
from aqt.browser import Browser
from aqt.qt import (
    QAction, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QComboBox, QPushButton, QProgressDialog,
    QGroupBox, QTextEdit, QFrame, QSizePolicy, QGridLayout,
    QPixmap, QByteArray, QCursor, QScrollArea, QWidget,
    Qt
)
from aqt.utils import showInfo, showWarning

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
        "source_field": "Front",
        "image_type": "photo",
        "image_position": "after"
    }
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
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
# Advanced Configuration Dialog
# ============================================================================

POSITION_OPTIONS = {
    "after": "Après le texte",
    "before": "Avant le texte",
    "replace": "Remplacer le texte"
}


class ClickableImageLabel(QLabel):
    """A QLabel that displays an image and is clickable."""
    
    def __init__(self, image_data: dict, index: int, parent=None):
        super().__init__(parent)
        self.image_data = image_data
        self.index = index
        self.selected = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(150, 150)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 3px solid #ddd;
                border-radius: 8px;
                background-color: #f9f9f9;
            }
            QLabel:hover {
                border-color: #4a90d9;
            }
        """)
    
    def set_selected(self, selected: bool):
        self.selected = selected
        if selected:
            self.setStyleSheet("""
                QLabel {
                    border: 3px solid #4CAF50;
                    border-radius: 8px;
                    background-color: #e8f5e9;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    border: 3px solid #ddd;
                    border-radius: 8px;
                    background-color: #f9f9f9;
                }
                QLabel:hover {
                    border-color: #4a90d9;
                }
            """)
    
    def mousePressEvent(self, event):
        if self.parent() and hasattr(self.parent(), 'parent'):
            dialog = self.parent().parent().parent().parent()
            if hasattr(dialog, 'select_image'):
                dialog.select_image(self.index)


class ImagePreviewDialog(QDialog):
    """Dialog showing multiple image thumbnails for selection."""
    
    def __init__(self, keyword: str, images: list, parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.images = images
        self.selected_index = 0
        self.image_labels: List[ClickableImageLabel] = []
        self.selected_url: Optional[str] = None
        
        self._setup_ui()
        self._load_thumbnails()
    
    def _setup_ui(self):
        self.setWindowTitle(f"Résultats pour \"{self.keyword}\"")
        self.setMinimumWidth(550)
        self.setMinimumHeight(300)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info = QLabel(f"Cliquez sur une image pour la sélectionner:")
        info.setStyleSheet("font-weight: bold; color: #333;")
        layout.addWidget(info)
        
        # Scroll area for images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        self.grid_layout = QHBoxLayout(container)
        self.grid_layout.setSpacing(10)
        
        # Create image placeholders
        for i, img_data in enumerate(self.images):
            label = ClickableImageLabel(img_data, i, container)
            label.setText("⏳")
            self.image_labels.append(label)
            self.grid_layout.addWidget(label)
        
        self.grid_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        # Tags label
        self.tags_label = QLabel("")
        self.tags_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.tags_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.use_btn = QPushButton("✓ Utiliser cette image")
        self.use_btn.setDefault(True)
        self.use_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.use_btn)
        
        layout.addLayout(btn_layout)
        
        # Select first image by default
        if self.image_labels:
            self.select_image(0)
    
    def select_image(self, index: int):
        """Select an image by index."""
        self.selected_index = index
        self.selected_url = self.images[index]["url"] if index < len(self.images) else None
        
        # Update visual selection
        for i, label in enumerate(self.image_labels):
            label.set_selected(i == index)
        
        # Update tags
        if index < len(self.images):
            tags = self.images[index].get("tags", "")
            self.tags_label.setText(f"Tags: {tags}")
    
    def _load_thumbnails(self):
        """Load thumbnail images from URLs."""
        try:
            import requests
        except ImportError:
            return
        
        for i, img_data in enumerate(self.images):
            try:
                response = requests.get(img_data["preview"], timeout=5)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(QByteArray(response.content))
                    scaled = pixmap.scaled(
                        140, 140, 
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.image_labels[i].setPixmap(scaled)
            except Exception as e:
                self.image_labels[i].setText("❌")
                print(f"Anki-Pix: Thumbnail load error - {e}")
            
            mw.app.processEvents()
    
    def get_selected_url(self) -> Optional[str]:
        """Return the URL of the selected image."""
        return self.selected_url


class AnkiPixDialog(QDialog):
    """Advanced dialog for configuring and running Anki-Pix."""
    
    def __init__(self, browser: Browser, selected_nids: List[int]):
        super().__init__(browser)
        self.browser = browser
        self.selected_nids = selected_nids
        self.config = get_config()
        self.available_fields: List[str] = []
        self.sample_note = None
        self.notes_to_process: List[tuple] = []
        
        self._detect_fields()
        self._setup_ui()
        self._update_preview()
    
    def _detect_fields(self) -> None:
        """Detect available fields from selected notes."""
        if not self.selected_nids:
            return
        
        # Get first note to detect fields
        self.sample_note = mw.col.get_note(self.selected_nids[0])
        self.available_fields = [f["name"] for f in self.sample_note.note_type()["flds"]]
    
    def _setup_ui(self) -> None:
        self.setWindowTitle("Anki-Pix")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)
        
        layout = QVBoxLayout(self)
        
        # === API Configuration ===
        api_group = QGroupBox("Configuration API")
        api_layout = QHBoxLayout(api_group)
        api_layout.addWidget(QLabel("Clé API Pixabay:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.config.get("pixabay_api_key", ""))
        self.api_key_input.setPlaceholderText("Entrez votre clé API...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addWidget(self.api_key_input)
        layout.addWidget(api_group)
        
        # === Search Parameters ===
        params_group = QGroupBox("Paramètres de recherche")
        params_layout = QVBoxLayout(params_group)
        
        # Source field
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Champ source:"))
        self.source_combo = QComboBox()
        if self.available_fields:
            self.source_combo.addItems(self.available_fields)
            # Try to select saved field
            saved = self.config.get("source_field", "Front")
            idx = self.source_combo.findText(saved)
            if idx >= 0:
                self.source_combo.setCurrentIndex(idx)
        else:
            self.source_combo.addItems(["Front", "Back", "Source"])
        self.source_combo.currentTextChanged.connect(self._update_preview)
        row1.addWidget(self.source_combo)
        params_layout.addLayout(row1)
        
        # Image type
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Type d'image:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["illustration", "photo", "vector", "all"])
        saved_type = self.config.get("image_type", "photo")
        idx = self.type_combo.findText(saved_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        row2.addWidget(self.type_combo)
        params_layout.addLayout(row2)
        
        # Position
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Position image:"))
        self.position_combo = QComboBox()
        for key, label in POSITION_OPTIONS.items():
            self.position_combo.addItem(label, key)
        saved_pos = self.config.get("image_position", "after")
        for i in range(self.position_combo.count()):
            if self.position_combo.itemData(i) == saved_pos:
                self.position_combo.setCurrentIndex(i)
                break
        self.position_combo.currentIndexChanged.connect(self._update_preview)
        row3.addWidget(self.position_combo)
        params_layout.addLayout(row3)
        
        layout.addWidget(params_group)
        
        # === Preview ===
        preview_group = QGroupBox("Prévisualisation")
        preview_layout = QVBoxLayout(preview_group)
        
        # Current content
        self.current_label = QLabel("Contenu actuel:")
        preview_layout.addWidget(self.current_label)
        
        self.current_text = QTextEdit()
        self.current_text.setReadOnly(True)
        self.current_text.setMaximumHeight(60)
        self.current_text.setStyleSheet("background-color: #f5f5f5; color: #333333;")
        preview_layout.addWidget(self.current_text)
        
        # Arrow
        arrow_label = QLabel("⬇️ Résultat prévu:")
        preview_layout.addWidget(arrow_label)
        
        # Preview result
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(80)
        self.preview_text.setStyleSheet("background-color: #e8f5e9; color: #333333;")
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
        
        # === Status ===
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        self._update_status()
        
        # === Buttons ===
        btn_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("🔍 Prévisualiser")
        self.test_btn.clicked.connect(self._test_search)
        btn_layout.addWidget(self.test_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.apply_btn = QPushButton("✓ Appliquer")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self._apply)
        btn_layout.addWidget(self.apply_btn)
        
        layout.addLayout(btn_layout)
    
    def _get_field_content(self, field_name: str) -> str:
        """Get content of a field from sample note."""
        if not self.sample_note:
            return ""
        try:
            idx = self.available_fields.index(field_name)
            return self.sample_note.fields[idx]
        except (ValueError, IndexError):
            return ""
    
    def _extract_keyword(self, html: str) -> str:
        """Extract plain text from HTML."""
        return re.sub(r'<[^>]+>', '', html).strip()
    
    def _update_preview(self) -> None:
        """Update the preview based on current settings."""
        field_name = self.source_combo.currentText()
        content = self._get_field_content(field_name)
        keyword = self._extract_keyword(content)
        position = self.position_combo.currentData()
        
        # Current content
        if content:
            self.current_text.setPlainText(content)
        else:
            self.current_text.setPlainText("(champ vide)")
        
        # Generate preview
        if not keyword:
            self.preview_text.setHtml("<i>(pas de mot-clé à rechercher)</i>")
            return
        
        img_tag = f'<img src="[📷 {keyword}]">'
        
        if position == "after":
            preview = f'{content}<br>{img_tag}'
        elif position == "before":
            preview = f'{img_tag}<br>{content}'
        else:  # replace
            preview = img_tag
        
        self.preview_text.setHtml(preview)
    
    def _update_status(self) -> None:
        """Update the status label with count of notes to process."""
        field_name = self.source_combo.currentText()
        
        total = len(self.selected_nids)
        to_process = 0
        
        for nid in self.selected_nids:
            note = mw.col.get_note(nid)
            field_names = [f["name"] for f in note.note_type()["flds"]]
            
            try:
                idx = field_names.index(field_name)
                content = note.fields[idx]
                keyword = self._extract_keyword(content)
                
                # Has keyword and no image yet
                if keyword and "<img" not in content.lower():
                    to_process += 1
            except ValueError:
                pass
        
        self.status_label.setText(
            f"📊 {to_process} note(s) à traiter sur {total} sélectionnée(s)"
        )
        self.notes_to_process_count = to_process
    
    def _test_search(self) -> None:
        """Test Pixabay search with current keyword and show image preview."""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            showWarning("Veuillez entrer votre clé API Pixabay.")
            return
        
        field_name = self.source_combo.currentText()
        content = self._get_field_content(field_name)
        keyword = self._extract_keyword(content)
        
        if not keyword:
            showWarning("Aucun mot-clé à rechercher.")
            return
        
        image_type = self.type_combo.currentText()
        
        self.test_btn.setText("🔄 Recherche...")
        self.test_btn.setEnabled(False)
        mw.app.processEvents()
        
        # Get multiple images
        images = pixabay.search_images(keyword, api_key, image_type, count=5)
        
        self.test_btn.setText("🔍 Prévisualiser")
        self.test_btn.setEnabled(True)
        
        if not images:
            showWarning(f"❌ Aucune image trouvée pour '{keyword}'")
            return
        
        # Open preview dialog
        preview_dialog = ImagePreviewDialog(keyword, images, self)
        if preview_dialog.exec():
            selected_url = preview_dialog.get_selected_url()
            if selected_url:
                showInfo(f"✅ Image sélectionnée!\n\nCette image sera utilisée lors de l'application.")
    
    def _apply(self) -> None:
        """Apply images to selected notes."""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            showWarning("Veuillez entrer votre clé API Pixabay.")
            return
        
        # Save config
        self.config["pixabay_api_key"] = api_key
        self.config["source_field"] = self.source_combo.currentText()
        self.config["image_type"] = self.type_combo.currentText()
        self.config["image_position"] = self.position_combo.currentData()
        save_config(self.config)
        
        field_name = self.config["source_field"]
        image_type = self.config["image_type"]
        position = self.config["image_position"]
        
        # Collect notes to process
        notes_to_process = []
        for nid in self.selected_nids:
            note = mw.col.get_note(nid)
            field_names = [f["name"] for f in note.note_type()["flds"]]
            
            try:
                idx = field_names.index(field_name)
                content = note.fields[idx]
                keyword = self._extract_keyword(content)
                
                if keyword and "<img" not in content.lower():
                    notes_to_process.append((note, idx, keyword, content))
            except ValueError:
                pass
        
        if not notes_to_process:
            showInfo("Aucune note à traiter.")
            return
        
        # Progress dialog
        progress = QProgressDialog(
            "Traitement...", "Annuler", 0, len(notes_to_process), self
        )
        progress.setWindowTitle("Anki-Pix")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        processed = 0
        failed = 0
        
        for i, (note, idx, keyword, original) in enumerate(notes_to_process):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"Recherche: {keyword}...")
            mw.app.processEvents()
            
            url = pixabay.search_image(keyword, api_key, image_type)
            if not url:
                failed += 1
                continue
            
            filename = pixabay.download_to_anki(url, keyword, mw.col)
            if not filename:
                failed += 1
                continue
            
            img_tag = f'<img src="{filename}">'
            
            if position == "after":
                note.fields[idx] = f'{original}<br>{img_tag}'
            elif position == "before":
                note.fields[idx] = f'{img_tag}<br>{original}'
            else:  # replace
                note.fields[idx] = img_tag
            
            mw.col.update_note(note)
            processed += 1
        
        progress.setValue(len(notes_to_process))
        progress.close()
        
        self.browser.model.reset()
        
        showInfo(
            f"Traitement terminé!\n\n"
            f"✓ Images ajoutées: {processed}\n"
            f"✗ Échecs: {failed}"
        )
        
        self.accept()


# ============================================================================
# Browser Menu Actions
# ============================================================================

def open_anki_pix_dialog(browser: Browser) -> None:
    """Open the Anki-Pix dialog."""
    selected_nids = browser.selectedNotes()
    
    if not selected_nids:
        showInfo("Veuillez sélectionner au moins une note.")
        return
    
    dialog = AnkiPixDialog(browser, selected_nids)
    dialog.exec()


def setup_browser_menu(browser: Browser) -> None:
    """Configure the menu in Anki Browser."""
    action = QAction("Anki-Pix: Ajouter Images...", browser)
    action.setShortcut("Ctrl+Shift+P")
    action.triggered.connect(lambda: open_anki_pix_dialog(browser))
    
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(action)


def on_browser_setup_menus(browser: Browser) -> None:
    """Hook called when Browser is initialized."""
    setup_browser_menu(browser)


# ============================================================================
# Add-on Initialization
# ============================================================================

from aqt import gui_hooks
gui_hooks.browser_menus_did_init.append(on_browser_setup_menus)

print("Anki-Pix: Add-on chargé avec succès!")
