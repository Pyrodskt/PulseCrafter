# importer.py
# Script pour importer les données de music_data.json et grouped_music.json
# dans une base de données SQLite normalisée et hiérarchique.

import json
import re
from tqdm import tqdm
from sqlalchemy.orm import Session
import os

# Importation des modèles et de la configuration de la base de données
from database_models import (
    Base,
    engine,
    SessionLocal,
    Musique,
    Artiste,
    GenreMusical,
    CleMusicale,
    TypeDeBasse,
    Group,
)

def _get_or_create_batch(session: Session, cache: dict, model, **kwargs):
    """
    Récupère une instance depuis le cache ou la DB. Si elle n'existe nulle part,
    la crée et l'ajoute à la session (sans commit).
    """
    cache_key = f"{model.__name__}-{kwargs['nom']}"
    if cache_key in cache:
        return cache[cache_key]

    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        cache[cache_key] = instance
        return instance
    
    instance = model(**kwargs)
    session.add(instance)
    cache[cache_key] = instance
    return instance

def _clean_filename(filename):
    """Supprime le préfixe numérique du nom de fichier."""
    return re.sub(r'^\d+\.\s*', '', filename)

def get_bass_type_from_punchiness(punchiness):
    """Détermine le type de basse à partir de la valeur de punchiness."""
    if punchiness < 0.8: return "Basse Douce"
    if 0.8 <= punchiness < 1.5: return "Basse Rythmée"
    return "Basse Agressive"

def importer_donnees_de_base(session: Session, fichier_json='music_data.json'):
    """
    Importe les données de base (Musiques, Artistes, Genres, etc.) depuis music_data.json.
    """
    print(f"\n--- Étape 1: Importation des données de base depuis '{fichier_json}' ---")
    try:
        with open(fichier_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[ERREUR] Impossible de lire '{fichier_json}': {e}")
        return

    musiques_ajoutees = 0
    processed_files = set(row[0] for row in session.query(Musique.nom_fichier).all())
    local_cache = {}

    for morceau_data in tqdm(data, desc="Préparation des musiques"):
        cleaned_filename = _clean_filename(morceau_data['file'])
        
        if cleaned_filename in processed_files:
            continue
        
        processed_files.add(cleaned_filename)

        artiste = _get_or_create_batch(session, local_cache, Artiste, nom=morceau_data.get('artist', 'Unknown').strip())
        genre = _get_or_create_batch(session, local_cache, GenreMusical, nom=morceau_data.get('genre', 'Unknown').strip())
        cle_musicale = _get_or_create_batch(session, local_cache, CleMusicale, nom=morceau_data.get('key', 'Unknown').strip())
        
        punch = morceau_data.get('punchiness', 0.0)
        bass_type_name = get_bass_type_from_punchiness(punch)
        type_de_basse = _get_or_create_batch(session, local_cache, TypeDeBasse, nom=bass_type_name)

        nouveau_morceau = Musique(
            nom_fichier=cleaned_filename,
            bpm=morceau_data.get('bpm'),
            punchiness=punch,
            sub_bass_db=morceau_data.get('sub_bass_db'),
            mid_bass_db=morceau_data.get('mid_bass_db'),
            artiste=artiste,
            genre=genre,
            cle_musicale=cle_musicale,
            type_de_basse=type_de_basse,
        )
        session.add(nouveau_morceau)
        musiques_ajoutees += 1

    print("Commit des nouvelles musiques...")
    session.commit()
    print(f"[INFO] {musiques_ajoutees} nouvelle(s) musique(s) ajoutée(s).")

def importer_groupes_hierarchiques(session: Session, fichier_json='grouped_music.json'):
    """
    Construit la hiérarchie de groupes et lie les musiques depuis grouped_music.json.
    """
    print(f"\n--- Étape 2: Importation de la structure des groupes depuis '{fichier_json}' ---")
    try:
        with open(fichier_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[ERREUR] Impossible de lire '{fichier_json}': {e}")
        return

    music_cache = {m.nom_fichier: m for m in session.query(Musique).all()}
    group_cache = {}

    def process_node(node_data, parent_group, level_type):
        for name, children in node_data.items():
            parent_id = parent_group.id if parent_group else None
            current_group = _get_or_create_batch(
                session,
                group_cache,
                Group,
                nom=name,
                type=level_type,
                parent_id=parent_id
            )
            # Le commit ici est nécessaire pour que l'ID soit généré pour les enfants
            session.commit()

            if isinstance(children, list):
                for music_filename in children:
                    cleaned_name = _clean_filename(music_filename)
                    if cleaned_name in music_cache:
                        music_obj = music_cache[cleaned_name]
                        if music_obj not in current_group.musiques:
                            current_group.musiques.append(music_obj)
            elif isinstance(children, dict):
                first_child_key = next(iter(children), None)
                if first_child_key:
                    if 'Basse' in first_child_key:
                        next_level_type = 'bass_type'
                    elif 'Groupe de Clés' in first_child_key:
                        next_level_type = 'key_group'
                    elif 'Groupe BPM' in first_child_key:
                        next_level_type = 'bpm_group'
                    else:
                        next_level_type = 'unknown_group'
                    process_node(children, current_group, next_level_type)

    with tqdm(total=len(data), desc="Création des groupes") as pbar:
        for genre_name, bass_types in data.items():
            genre_group = _get_or_create_batch(session, group_cache, Group, nom=genre_name, type='genre', parent_id=None)
            session.commit() # Commit pour s'assurer que le groupe racine a un ID
            process_node(bass_types, genre_group, 'bass_type')
            pbar.update(1)

    print("Commit final des associations de groupes...")
    session.commit()
    print("[INFO] Importation des groupes terminée.")


if __name__ == "__main__":
    print("Démarrage du script d'importation complet...")
    
    if os.path.exists("music_library.db"):
        os.remove("music_library.db")
        print("Ancienne base de données supprimée pour une reconstruction propre.")

    print("Création de toutes les tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables prêtes.")
    
    db = SessionLocal()
    
    try:
        importer_donnees_de_base(db)
        importer_groupes_hierarchiques(db)
    finally:
        db.close()

    print("\nScript d'importation terminé.")
