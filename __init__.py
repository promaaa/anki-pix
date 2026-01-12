# -*- coding: utf-8 -*-
"""
Anki-Pix: Add-on pour ajouter des images Pixabay aux notes Anki.

Ce module s'intègre dans le menu 'Outils' du Browser Anki
pour permettre l'ajout automatique d'images aux notes sélectionnées.
"""

from aqt import mw
from aqt.browser import Browser
from aqt.qt import QAction
from aqt.utils import showInfo


def on_test_selected_notes(browser: Browser) -> None:
    """
    Fonction de test : affiche les informations des notes sélectionnées.
    
    Cette fonction récupère les notes sélectionnées dans le Browser
    et affiche leurs informations dans la console Anki (debug).
    
    Args:
        browser: Instance du Browser Anki.
    """
    # Récupérer les IDs des notes sélectionnées
    selected_nids = browser.selectedNotes()
    
    if not selected_nids:
        showInfo("Aucune note sélectionnée. Veuillez sélectionner au moins une note.")
        return
    
    print(f"\n{'='*50}")
    print(f"Anki-Pix: Test des notes sélectionnées")
    print(f"Nombre de notes sélectionnées: {len(selected_nids)}")
    print(f"{'='*50}")
    
    # Parcourir les notes sélectionnées
    for nid in selected_nids:
        note = mw.col.get_note(nid)
        
        # Récupérer le nom du modèle (type de note)
        model_name = note.note_type()["name"]
        
        # Récupérer les champs de la note
        fields = note.fields
        field_names = [f["name"] for f in note.note_type()["flds"]]
        
        print(f"\n--- Note ID: {nid} ---")
        print(f"Type de note: {model_name}")
        print("Champs:")
        for name, value in zip(field_names, fields):
            # Tronquer les valeurs longues pour la lisibilité
            display_value = value[:100] + "..." if len(value) > 100 else value
            # Nettoyer le HTML pour l'affichage console
            display_value = display_value.replace("\n", " ").strip()
            print(f"  - {name}: {display_value}")
    
    print(f"\n{'='*50}")
    print(f"Fin du test. Consultez la console pour les détails.")
    print(f"{'='*50}\n")
    
    # Afficher un message de confirmation à l'utilisateur
    showInfo(
        f"Test terminé!\n\n"
        f"Nombre de notes analysées: {len(selected_nids)}\n\n"
        f"Consultez la console Anki (Debug Console) pour voir les détails."
    )


def setup_browser_menu(browser: Browser) -> None:
    """
    Configure le menu dans le Browser Anki.
    
    Ajoute une entrée 'Anki-Pix: Test Notes' dans le menu 'Outils'
    du Browser pour tester la sélection des notes.
    
    Args:
        browser: Instance du Browser Anki.
    """
    # Créer l'action pour le menu
    action = QAction("Anki-Pix: Test Notes Sélectionnées", browser)
    action.triggered.connect(lambda: on_test_selected_notes(browser))
    
    # Ajouter au menu 'Outils' (Edit menu dans le Browser)
    # Note: Dans le Browser, le menu s'appelle 'menuEdit' mais on utilise
    # form.menuEdit pour accéder au menu Édition
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(action)


def on_browser_setup_menus(browser: Browser) -> None:
    """
    Hook appelé quand le Browser est initialisé.
    
    Args:
        browser: Instance du Browser Anki.
    """
    setup_browser_menu(browser)


# Enregistrer le hook pour le Browser
from aqt import gui_hooks
gui_hooks.browser_menus_did_init.append(on_browser_setup_menus)

# Message de chargement (visible dans la console)
print("Anki-Pix: Add-on chargé avec succès!")
