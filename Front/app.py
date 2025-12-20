import sys
import os
from flask import Flask, render_template, request
from sqlalchemy.orm import joinedload, contains_eager
from sqlalchemy import and_

# Ajoute la racine du projet au PYTHONPATH pour permettre les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importe les modèles et la session de la base de données
from DB.database_models import SessionLocal, Group as GroupDB, Musique as MusiqueDB, GenreMusical as GenreDB, CleMusicale as CleDB

# Basic Flask setup
app = Flask(__name__)

def get_filter_data(session):
    """Récupère toutes les options de filtre possibles depuis la DB."""
    genres = [g.nom for g in session.query(GenreDB).order_by(GenreDB.nom).all()]
    keys = [k.nom for k in session.query(CleDB).order_by(CleDB.nom).all()]
    return genres, keys

def get_group_hierarchy(session, filters):
    """
    Construit une structure de données hiérarchique filtrée.
    """
    # Commence par une requête sur les musiques, en appliquant les filtres
    music_query = session.query(MusiqueDB).options(
        joinedload(MusiqueDB.artiste),
        joinedload(MusiqueDB.cle_musicale),
        joinedload(MusiqueDB.genre)
    )

    if filters.get('genre'):
        music_query = music_query.join(GenreDB).filter(GenreDB.nom == filters['genre'])
    if filters.get('key'):
        music_query = music_query.join(CleDB).filter(CleDB.nom == filters['key'])
    if filters.get('bpm_min'):
        music_query = music_query.filter(MusiqueDB.bpm >= int(filters['bpm_min']))
    if filters.get('bpm_max'):
        music_query = music_query.filter(MusiqueDB.bpm <= int(filters['bpm_max']))

    # Récupère tous les IDs des musiques qui correspondent aux filtres
    filtered_music_ids = {m.id for m in music_query.all()}
    if not filtered_music_ids:
        return []

    # Récupère tous les groupes qui contiennent au moins une de ces musiques
    relevant_groups_query = session.query(GroupDB).join(GroupDB.musiques).filter(MusiqueDB.id.in_(filtered_music_ids))
    
    # Eagerly load des parents pour reconstruire l'arbre
    relevant_groups_query = relevant_groups_query.options(joinedload(GroupDB.parent))
    
    relevant_groups = relevant_groups_query.all()
    
    # Créer un set de tous les IDs de groupes pertinents, y compris leurs parents
    full_tree_group_ids = set()
    for group in relevant_groups:
        curr = group
        while curr:
            full_tree_group_ids.add(curr.id)
            curr = curr.parent

    if not full_tree_group_ids:
        return []

    # Re-interroger pour obtenir les objets complets avec leurs enfants et musiques pré-chargés
    final_query = session.query(GroupDB).filter(GroupDB.id.in_(full_tree_group_ids)).options(
        joinedload(GroupDB.children),
        joinedload(GroupDB.musiques).subqueryload('*') # Charger les musiques
    )
    
    all_relevant_groups = final_query.all()
    group_map = {g.id: g for g in all_relevant_groups}
    
    root_groups = [g for g in all_relevant_groups if g.parent_id is None]

    def format_group(group_db_obj):
        # Les musiques de ce groupe qui sont dans la liste filtrée
        filtered_musics = [m for m in group_db_obj.musiques if m.id in filtered_music_ids]
        
        # Les enfants qui sont dans notre set d'IDs pertinents
        valid_children = [child for child in group_db_obj.children if child.id in group_map]
        
        return {
            "nom": group_db_obj.nom,
            "type": group_db_obj.type,
            "children": sorted([format_group(child) for child in valid_children], key=lambda x: x['nom']),
            "musiques": sorted(filtered_musics, key=lambda x: x.bpm)
        }

    return sorted([format_group(root) for root in root_groups], key=lambda x: x['nom'])

@app.route('/')
def index():
    """Rend la page d'accueil principale."""
    return render_template('index.html')

@app.route('/groups')
def groups():
    """
    Rend la page des groupes en injectant les données hiérarchiques,
    potentiellement filtrées par les paramètres de la requête.
    """
    db_session = SessionLocal()
    try:
        # Récupère les paramètres de filtre depuis l'URL
        active_filters = {
            'genre': request.args.get('genre'),
            'key': request.args.get('key'),
            'bpm_min': request.args.get('bpm_min'),
            'bpm_max': request.args.get('bpm_max'),
        }
        
        # Récupère les données pour peupler les menus déroulants des filtres
        all_genres, all_keys = get_filter_data(db_session)
        
        # Construit l'arborescence des groupes en appliquant les filtres
        group_data = get_group_hierarchy(db_session, active_filters)
        
    finally:
        db_session.close()
        
    return render_template('groups.html', 
                           groups=group_data, 
                           all_genres=all_genres, 
                           all_keys=all_keys,
                           filters=active_filters)

if __name__ == '__main__':
    # S'assure que la base de données et les tables existent
    from DB.database_models import Base, engine
    print("Création des tables si elles n'existent pas...")
    Base.metadata.create_all(bind=engine)
    
    app.run(debug=True, port=5000)
