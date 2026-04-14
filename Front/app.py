import sys
import os
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from sqlalchemy.orm import joinedload
from sqlalchemy import and_
import json
import zipfile
import io
import threading
import subprocess
from datetime import datetime
from pathlib import Path

# Ajoute la racine du projet au PYTHONPATH pour permettre les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importe les modèles et la session de la base de données
from DB.database_models import (
    SessionLocal, 
    Group as GroupDB, 
    Musique as MusiqueDB, 
    GenreMusical as GenreDB, 
    CleMusicale as CleDB,
    TypeDeBasse as TypeDeBasseDB,
    Artiste as ArtisteDB
)

# Basic Flask setup
app = Flask(__name__)

# Pipeline status and logs
pipeline_logs = []  # Liste persistente pour stocker tous les logs
pipeline_logs_lock = threading.Lock()  # Lock pour thread-safety
pipeline_status = {
    'running': False,
    'download_done': False,
    'analyze_done': False,
    'import_done': False,
    'error': None
}

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
    """Rend la page d'accueil principale avec les données musicales."""
    # Ne plus passer les données au template, elles seront chargées via AJAX
    return render_template('index.html')

@app.route('/api/musics')
def api_musics():
    """API endpoint pour récupérer toutes les musiques au format JSON."""
    from pathlib import Path
    
    db_session = SessionLocal()
    try:
        musics_query = db_session.query(MusiqueDB).options(
            joinedload(MusiqueDB.artiste),
            joinedload(MusiqueDB.genre),
            joinedload(MusiqueDB.cle_musicale),
            joinedload(MusiqueDB.type_de_basse)
        ).order_by(MusiqueDB.id).all()

        # Cache des fichiers dans Core/musics pour optimiser
        core_musics_path = Path(__file__).parent.parent / 'Core' / 'musics'
        file_cache = {}
        if core_musics_path.exists():
            for audio_file in core_musics_path.rglob('*'):
                if audio_file.is_file():
                    file_cache[audio_file.name] = str(audio_file.absolute())

        music_data = []
        for m in musics_query:
            # Chercher le chemin du fichier audio
            audio_path = file_cache.get(m.nom_fichier, "")
            
            music_data.append({
                "id": m.id,
                "nom_fichier": m.nom_fichier,
                "nom": m.nom_fichier,  # Alias pour compatibilité
                "bpm": m.bpm,
                "punchiness": m.punchiness,
                "artiste": {"nom": m.artiste.nom if m.artiste else 'N/A'},
                "nom_artiste": m.artiste.nom if m.artiste else 'N/A',  # Pour simplifier
                "genre": {"nom": m.genre.nom if m.genre else 'N/A'},
                "cle_musicale": {"nom": m.cle_musicale.nom if m.cle_musicale else 'N/A'},
                "type_de_basse": {"nom": m.type_de_basse.nom if m.type_de_basse else 'N/A'},
                "path": audio_path,  # ✅ NOUVEAU: Le chemin absolu du fichier audio
                "duration": m.duration if hasattr(m, 'duration') else -1
            })
    finally:
        db_session.close()
    
    return jsonify(music_data)

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

@app.route('/musics/update/<int:music_id>', methods=['POST'])
def update_music(music_id):
    data = request.json
    db_session = SessionLocal()
    try:
        music = db_session.query(MusiqueDB).filter(MusiqueDB.id == music_id).first()
        if not music:
            return jsonify({"error": "Musique non trouvée"}), 404

        if 'bpm' in data and data['bpm'] is not None:
            music.bpm = int(data['bpm'])
        if 'punchiness' in data and data['punchiness'] is not None:
            music.punchiness = float(data['punchiness'])
        
        if 'genre' in data:
            genre = db_session.query(GenreDB).filter(GenreDB.nom == data['genre']).first()
            if not genre:
                genre = GenreDB(nom=data['genre'])
                db_session.add(genre)
            music.genre = genre
        
        if 'cle_musicale' in data:
            key = db_session.query(CleDB).filter(CleDB.nom == data['cle_musicale']).first()
            if not key:
                key = CleDB(nom=data['cle_musicale'])
                db_session.add(key)
            music.cle_musicale = key

        db_session.commit()
        db_session.refresh(music)
        
        updated_music_data = {
            "id": music.id, "nom_fichier": music.nom_fichier, "bpm": music.bpm,
            "punchiness": music.punchiness,
            "artiste": {"nom": music.artiste.nom if music.artiste else 'N/A'},
            "genre": {"nom": music.genre.nom if music.genre else 'N/A'},
            "cle_musicale": {"nom": music.cle_musicale.nom if music.cle_musicale else 'N/A'},
            "type_de_basse": {"nom": music.type_de_basse.nom if music.type_de_basse else 'N/A'}
        }
        return jsonify(updated_music_data)

    except Exception as e:
        db_session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db_session.close()

@app.route('/static/music/<filename>')
def serve_music(filename):
    return send_from_directory(os.path.join(app.root_path, '..', 'Core', 'musics'), filename)

@app.route('/download_playlist', methods=['POST'])
def download_playlist():
    try:
        data = request.get_json()
        filenames = data.get('playlist', [])
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename in filenames:
                file_path = os.path.join(app.root_path, '..', 'Core', 'musics', filename)
                if os.path.exists(file_path):
                    zip_file.write(file_path, filename)
        
        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name='playlist.zip', mimetype='application/zip')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== PULSECRAFTER ROUTES =====
def add_log(message, level="INFO"):
    """Ajoute un message aux logs du pipeline."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {level}: {message}"
    with pipeline_logs_lock:
        pipeline_logs.append(log_msg)
    print(log_msg)

def run_pulsecrafter_step(step):
    """Exécute une étape de PulseCrafter."""
    try:
        core_dir = os.path.join(os.path.dirname(__file__), '..', 'Core')
        script_path = os.path.join(core_dir, 'PulseCrafter.py')
        
        add_log(f"Démarrage de l'étape: {step}")
        
        result = subprocess.run(
            [sys.executable, script_path, '--steps', step],
            cwd=core_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    add_log(line)
        
        if result.returncode != 0:
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if line.strip():
                        add_log(line, "ERROR")
            return False
        
        return True
    except Exception as e:
        add_log(f"Erreur lors de l'exécution de {step}: {str(e)}", "ERROR")
        return False

def run_pipeline_thread():
    """Exécute le pipeline complet dans un thread."""
    try:
        pipeline_status['running'] = True
        pipeline_status['download_done'] = False
        pipeline_status['analyze_done'] = False
        pipeline_status['import_done'] = False
        pipeline_status['error'] = None
        
        add_log("=== Démarrage du Pipeline PulseCrafter ===")
        
        # Étape 1: Téléchargement
        add_log("ÉTAPE 1: Téléchargement des playlists...")
        if run_pulsecrafter_step('download'):
            pipeline_status['download_done'] = True
            add_log("[OK] Telecharement termine")
        else:
            add_log("[FAIL] Telecharement echoue", "ERROR")
            pipeline_status['error'] = "Téléchargement échoué"
            pipeline_status['running'] = False
            return
        
        # Étape 2: Analyse
        add_log("ÉTAPE 2: Analyse des fichiers...")
        if run_pulsecrafter_step('analyze'):
            pipeline_status['analyze_done'] = True
            add_log("[OK] Analyse termine")
        else:
            add_log("[FAIL] Analyse echouee", "ERROR")
            pipeline_status['error'] = "Analyse échouée"
            pipeline_status['running'] = False
            return
        
        # Étape 3: Importation
        add_log("ÉTAPE 3: Importation en base de données...")
        if run_pulsecrafter_step('import'):
            pipeline_status['import_done'] = True
            add_log("[OK] Importation terminee")
        else:
            add_log("[FAIL] Importation echouee", "ERROR")
            pipeline_status['error'] = "Importation échouée"
            pipeline_status['running'] = False
            return
        
        add_log("=== Pipeline termine avec succes! ===")
        pipeline_status['running'] = False
        
    except Exception as e:
        add_log(f"Erreur fatale: {str(e)}", "ERROR")
        pipeline_status['error'] = str(e)
        pipeline_status['running'] = False

@app.route('/api/pipeline/start', methods=['POST'])
def start_pipeline():
    """Démarre le pipeline PulseCrafter dans un thread séparé."""
    if pipeline_status['running']:
        return jsonify({"error": "Pipeline déjà en cours"}), 400
    
    # Vide la liste de logs
    with pipeline_logs_lock:
        pipeline_logs.clear()
    
    # Réinitialise le statut
    pipeline_status['download_done'] = False
    pipeline_status['analyze_done'] = False
    pipeline_status['import_done'] = False
    pipeline_status['error'] = None
    
    # Lance le pipeline dans un thread
    thread = threading.Thread(target=run_pipeline_thread, daemon=True)
    thread.start()
    
    return jsonify({"message": "Pipeline démarré"}), 200

@app.route('/api/pipeline/logs', methods=['GET'])
def get_pipeline_logs():
    """Récupère tous les logs disponibles depuis un index donné."""
    from_index = request.args.get('from_index', 0, type=int)
    
    with pipeline_logs_lock:
        # Retourner seulement les logs depuis l'index demandé
        new_logs = pipeline_logs[from_index:]
        total_logs = len(pipeline_logs)
    
    return jsonify({
        "logs": new_logs,
        "total_logs": total_logs,
        "from_index": from_index,
        "status": pipeline_status,
        "running": pipeline_status['running']
    }), 200

@app.route('/api/pipeline/status', methods=['GET'])
def get_pipeline_status():
    """Récupère le statut du pipeline."""
    return jsonify(pipeline_status), 200

@app.route('/api/pipeline/download-single', methods=['POST'])
def download_single_playlist():
    """Télécharge une seule playlist."""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "URL non fournie"}), 400
        
        # Utiliser scdl pour télécharger la playlist
        downloads_dir = os.path.join(os.path.dirname(__file__), '..', 'Core', 'musics')
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Exécuter scdl
        try:
            result = subprocess.run(
                ['scdl', '-l', url, '-d', downloads_dir],
                capture_output=True,
                text=True,
                timeout=300,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                return jsonify({"message": f"Playlist téléchargée avec succès"}), 200
            else:
                error_msg = result.stderr if result.stderr else "Erreur inconnue scdl"
                return jsonify({"error": f"Erreur scdl: {error_msg}"}), 400
        except subprocess.TimeoutExpired:
            return jsonify({"error": "Téléchargement trop long"}), 408
        except FileNotFoundError:
            return jsonify({"error": "scdl non installé"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlists/add-urls', methods=['POST'])
def add_playlists_urls():
    """Ajoute les URLs de playlists au fichier playlist.txt."""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({"error": "Aucune URL fournie"}), 400
        
        playlist_file = os.path.join(os.path.dirname(__file__), '..', 'Core', 'playlist.txt')
        
        with open(playlist_file, 'a', encoding='utf-8') as f:
            for url in urls:
                if url.strip():
                    f.write(url.strip() + '\n')
        
        return jsonify({
            "message": f"{len(urls)} URL(s) ajoutée(s)",
            "urls_added": len(urls)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlists/get-urls', methods=['GET'])
def get_playlists_urls():
    """Récupère les URLs de playlists du fichier playlist.txt."""
    try:
        playlist_file = os.path.join(os.path.dirname(__file__), '..', 'Core', 'playlist.txt')
        urls = []
        
        if os.path.exists(playlist_file):
            with open(playlist_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        
        return jsonify({"urls": urls}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlists/delete-url', methods=['POST'])
def delete_playlist_url():
    """Supprime une URL spécifique de playlist.txt."""
    try:
        data = request.get_json()
        url_to_delete = data.get('url', '').strip()
        
        if not url_to_delete:
            return jsonify({"error": "Aucune URL fournie"}), 400
        
        playlist_file = os.path.join(os.path.dirname(__file__), '..', 'Core', 'playlist.txt')
        
        # Lire toutes les lignes sauf celle à supprimer
        urls = []
        if os.path.exists(playlist_file):
            with open(playlist_file, 'r', encoding='utf-8') as f:
                urls = [line.rstrip('\n') for line in f if line.strip() and line.strip() != url_to_delete]
        
        # Réécrire le fichier
        with open(playlist_file, 'w', encoding='utf-8') as f:
            for url in urls:
                if url.strip():
                    f.write(url + '\n')
        
        return jsonify({"message": "URL supprimée avec succès"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlists/clear-all', methods=['POST'])
def clear_all_playlists():
    """Supprime toutes les URLs du fichier playlist.txt."""
    try:
        playlist_file = os.path.join(os.path.dirname(__file__), '..', 'Core', 'playlist.txt')
        
        # Créer un fichier vide
        with open(playlist_file, 'w', encoding='utf-8') as f:
            pass  # Fichier vide
        
        return jsonify({"message": "Toutes les playlists ont été supprimées"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlists/download-zip', methods=['POST'])
def download_playlist_zip():
    """Crée et télécharge une playlist en format ZIP avec les fichiers audio."""
    try:
        import zipfile
        import tempfile
        from pathlib import Path
        
        data = request.get_json()
        playlist_name = data.get('name', 'playlist')
        tracks = data.get('tracks', [])
        is_download = data.get('download', True)
        
        if not tracks:
            print(f"❌ Aucune piste fournie")
            return jsonify({"error": "Aucune piste dans la playlist"}), 400
        
        print(f"📝 Playlist: {playlist_name}, {len(tracks)} piste(s)")
        
        # === ÉTAPE 1: Créer un cache des fichiers audio ===
        core_musics_path = Path(__file__).parent.parent / 'Core' / 'musics'
        file_cache = {}
        if core_musics_path.exists():
            print(f"🔍 Scan de {core_musics_path}...")
            for audio_file in core_musics_path.rglob('*'):
                if audio_file.is_file():
                    file_cache[audio_file.name] = str(audio_file.absolute())
            print(f"✓ {len(file_cache)} fichier(s) indexé(s)")
        
        # === ÉTAPE 2: Enrichir les pistes avec les chemins manquants ===
        for track in tracks:
            if not track.get('path') and track.get('nom_fichier'):
                # Chercher le fichier par son nom
                filename = track['nom_fichier']
                if filename in file_cache:
                    track['path'] = file_cache[filename]
                    print(f"  ✓ Trouvé par nom: {filename}")
                else:
                    print(f"  ❌ Fichier non trouvé: {filename}")
        
        # === ÉTAPE 3: Créer le ZIP ===
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_zip.close()
        
        files_added = 0
        missing_files = 0
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Ajouter un fichier M3U dans le ZIP
            m3u_content = '#EXTM3U\n'
            for track in tracks:
                dur = track.get('duration', -1)
                artist = track.get('artiste', {}).get('nom', 'Artiste inconnu') if isinstance(track.get('artiste'), dict) else track.get('nom_artiste', 'Artiste inconnu')
                title = track.get('nom', track.get('nom_fichier', 'Sans titre'))
                m3u_content += f"#EXTINF:{dur},{artist} - {title}\n"
                
                file_path = track.get('path', '')
                if file_path:
                    # Le titre contient déjà l'extension
                    m3u_content += f"{title}\n"
                else:
                    m3u_content += "\n"
            
            zipf.writestr('playlist.m3u', m3u_content)
            print(f"  ✓ playlist.m3u ajouté au ZIP")
            
            # Ajouter les fichiers audio
            for track in tracks:
                file_path = track.get('path', '')
                
                # Si pas de chemin, ignorer
                if not file_path:
                    print(f"  ⚠️ Pas de chemin pour: {track.get('nom_fichier', 'unknown')}")
                    missing_files += 1
                    continue
                
                # Vérifier que le chemin existe (c'est déjà un chemin absolu)
                if not os.path.exists(file_path):
                    print(f"  ❌ Fichier non trouvé: {file_path}")
                    missing_files += 1
                    continue
                
                try:
                    # Créer un nom d'archive à la RACINE du ZIP
                    title = track.get('nom', track.get('nom_fichier', 'track'))
                    
                    # Nettoyer les noms de fichiers invalides
                    title = "".join(c for c in title if c not in '<>:"/\\|?*')
                    
                    # Le titre contient déjà l'extension
                    archive_name = title
                    
                    zipf.write(file_path, archive_name)
                    files_added += 1
                    print(f"  ✓ Ajouté: {title}")
                    
                except Exception as e:
                    print(f"  ❌ Erreur lors de l'ajout du fichier {file_path}: {e}")
                    import traceback
                    traceback.print_exc()
                    missing_files += 1
                    continue
            
            print(f"📦 ZIP finalisé: {files_added} fichier(s) - {missing_files} fichier(s) manquant(s)")
        
        if is_download:
            # Envoyer le fichier ZIP
            print(f"📥 Envoi du fichier ZIP au client...")
            return send_file(
                temp_zip.name,
                as_attachment=True,
                download_name=f"{playlist_name.replace(' ', '_')}.zip",
                mimetype='application/zip'
            ), 200
        else:
            # Juste retourner les infos
            result = {
                "files_added": files_added,
                "missing_files": missing_files,
                "total_tracks": len(tracks)
            }
            print(f"📊 Retour des infos: {result}")
            return jsonify(result), 200
        
    except Exception as e:
        print(f"❌ ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500

if __name__ == '__main__':
    # S'assure que la base de données et les tables existent
    from DB.database_models import Base, engine
    print("Création des tables si elles n'existent pas...")
    Base.metadata.create_all(bind=engine)
    
    app.run(debug=True, port=5000)
