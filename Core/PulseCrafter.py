# PulseCrafter.py
# Une application complète pour télécharger, analyser, grouper et organiser votre musique.

import os
import sys
import json
import re
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from urllib.parse import urlparse, unquote
from collections import defaultdict
from tqdm import tqdm
import librosa
import numpy as np
from mutagen.easyid3 import EasyID3
from mutagen import File
import concurrent.futures

# Ajoute la racine du projet au PYTHONPATH pour permettre les imports inter-modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from DB.database_models import (
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

# ==============================================================================
# CLASSE 1: Downloader
# ==============================================================================
class Downloader:
    """
    Télécharge les playlists depuis une liste d'URLs en utilisant 'scdl'.
    """
    def __init__(self, playlist_file="playlist.txt", download_dir="musics"):
        self.playlist_file = playlist_file
        self.download_dir = download_dir

    def _extract_playlist_name_from_url(self, url):
        """Construit un nom de playlist lisible à partir de l'URL."""
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        if not path_parts:
            return url

        raw_name = path_parts[-1]
        cleaned_name = unquote(raw_name).replace('-', ' ').replace('_', ' ').strip()
        return cleaned_name or url

    def _get_playlist_metadata(self, url):
        """Récupère le nom et le nombre de titres d'une playlist sans télécharger les fichiers."""
        playlist_name = self._extract_playlist_name_from_url(url)
        track_count = None

        try:
            from yt_dlp import YoutubeDL

            with YoutubeDL({
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True,
                'ignoreerrors': True,
            }) as ydl:
                info = ydl.extract_info(url, download=False)

            if info:
                playlist_name = info.get('title') or info.get('playlist_title') or playlist_name

                entries = info.get('entries')
                if isinstance(entries, list):
                    track_count = len([entry for entry in entries if entry])
                elif info.get('playlist_count') is not None:
                    track_count = int(info['playlist_count'])
        except Exception:
            pass

        return playlist_name, track_count

    def _rename_files(self):
        """Renomme les fichiers en supprimant le préfixe numérique (ex: '01. ') et supprime les doublons."""
        download_path = Path(self.download_dir)
        if not download_path.exists():
            return

        renamed_count = 0

        # First, rename all files, overwriting if necessary
        for file_path in download_path.glob("*.mp3"):
            original_name = file_path.name
            new_name = re.sub(r'^\d+\.\s*', '', original_name)
            if new_name != original_name:
                new_path = file_path.with_name(new_name)
                try:
                    if new_path.exists():
                        new_path.unlink()  # Overwrite existing file
                    file_path.rename(new_path)
                    renamed_count += 1
                except Exception as e:
                    print(f"[AVERTISSEMENT] Échec du renommage de {original_name}: {e}")
        
        # Then, remove duplicates
        name_to_paths = {}
        for file_path in download_path.glob("*.mp3"):
            name = file_path.name
            if name not in name_to_paths:
                name_to_paths[name] = []
            name_to_paths[name].append(file_path)
        
        duplicates_removed = 0
        for name, paths in name_to_paths.items():
            if len(paths) > 1:
                # Keep the first, delete the rest
                for path in paths[1:]:
                    try:
                        path.unlink()
                        duplicates_removed += 1
                    except Exception as e:
                        print(f"[AVERTISSEMENT] Échec de suppression du doublon {name}: {e}")
        
        if renamed_count > 0:
            print(f"[INFO] {renamed_count} fichier(s) renommé(s).")
        if duplicates_removed > 0:
            print(f"[INFO] {duplicates_removed} doublon(s) supprimé(s).")

    def run(self):
        print("\n--- Étape 1: Téléchargement des Playlists ---", flush=True)
        playlist_path = Path(self.playlist_file)
        download_path = Path(self.download_dir)
        download_path.mkdir(exist_ok=True)

        if not playlist_path.exists():
            print(f"[AVERTISSEMENT] Fichier de playlists '{self.playlist_file}' introuvable. Étape de téléchargement ignorée.", flush=True)
            return False

        with playlist_path.open("r", encoding="utf-8") as f:
            playlists = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        if not playlists:
            print("[INFO] Aucune playlist à télécharger.", flush=True)
            return False

        total_playlists = len(playlists)
        succes_count = 0

        print(f"[INFO] {total_playlists} playlist(s) à télécharger dans '{self.download_dir}'.", flush=True)
        for idx, url in enumerate(playlists, start=1):
            playlist_name, track_count = self._get_playlist_metadata(url)
            if track_count is not None:
                print(
                    f"[INFO] Playlist {idx}/{total_playlists} en cours : {playlist_name} - {track_count} musique(s) à télécharger.",
                    flush=True
                )
            else:
                print(
                    f"[INFO] Playlist {idx}/{total_playlists} en cours : {playlist_name} - nombre de musiques indisponible.",
                    flush=True
                )

            files_before = len(list(download_path.glob("*.mp3")))
            try:
                subprocess.run(
                    [
                        "scdl", "-l", url, "--path", str(download_path), "--onlymp3",
                        "--no-playlist-folder", "--original-name",
                        "--hidewarnings", "--no-original"
                    ],
                    text=True,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                files_after = len(list(download_path.glob("*.mp3")))
                nouveaux_fichiers = max(files_after - files_before, 0)
                succes_count += 1
                print(
                    f"[INFO] Playlist {idx}/{total_playlists} terminée : {playlist_name} - {nouveaux_fichiers} nouveau(x) fichier(s).",
                    flush=True
                )
            except subprocess.CalledProcessError as e:
                print(f"[ERREUR] Playlist {idx}/{total_playlists} échouée : {playlist_name} (code {e.returncode}).", flush=True)
            except FileNotFoundError:
                print("[ERREUR FATALE] La commande 'scdl' est introuvable. Assurez-vous qu'elle est installée et dans le PATH.", flush=True)
                return False

        self._rename_files()
        print(f"[INFO] Téléchargement terminé. {succes_count}/{total_playlists} playlist(s) traitée(s) avec succès.", flush=True)
        return succes_count > 0

# ==============================================================================
# CLASSE 2: MusicAnalyzer
# ==============================================================================
class MusicAnalyzer:
    """
    Analyse les fichiers audio pour en extraire les métadonnées (BPM, clé, genre, etc.).
    """
    def __init__(self, source_dir="musics", output_file="music_data.json", error_log="error_log.txt"):
        self.source_dir = source_dir
        self.output_file = output_file
        self.error_log = error_log

    def _analyze_file(self, file_path):
        try:
            artist, genre = "Unknown", "Unknown"
            try:
                audio_meta = EasyID3(file_path)
                if 'artist' in audio_meta: artist = audio_meta['artist'][0]
                if 'genre' in audio_meta: genre = audio_meta['genre'][0].lower()
            except Exception:
                try:
                    audio_meta = File(file_path, easy=True)
                    if 'artist' in audio_meta: artist = audio_meta['artist'][0]
                    if 'genre' in audio_meta: genre = audio_meta['genre'][0].lower()
                except Exception:
                    pass

            y, sr = librosa.load(file_path)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)
            bpm = round(tempo[0])

            chromagram = librosa.feature.chroma_stft(y=y, sr=sr)
            chroma_sum = np.sum(chromagram, axis=1)
            pitch_classes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            key_index = np.argmax(chroma_sum)
            major_third = (key_index + 4) % 12
            minor_third = (key_index + 3) % 12
            mode = " Major" if chroma_sum[major_third] > chroma_sum[minor_third] else " Minor"
            estimated_key = pitch_classes[key_index] + mode

            from scipy import signal
            S_power = np.abs(librosa.stft(y))**2
            db_spec = librosa.power_to_db(S_power, ref=np.max)
            freqs = librosa.fft_frequencies(sr=sr)
            sub_bass_db = np.mean(db_spec[freqs < 60, :]) if np.any(freqs < 60) else -80.0
            mid_bass_db = np.mean(db_spec[(freqs >= 60) & (freqs < 250), :]) if np.any((freqs >= 60) & (freqs < 250)) else -80.0

            punchiness = 0.0
            try:
                b, a = signal.butter(4, 250, 'low', fs=sr)
                y_bass = signal.filtfilt(b, a, y)
                onset_env_bass = librosa.onset.onset_strength(y=y_bass, sr=sr)
                duration = librosa.get_duration(y=y, sr=sr)
                if duration > 0:
                    punchiness = len(librosa.onset.onset_detect(onset_envelope=onset_env_bass, sr=sr)) / duration
            except Exception:
                pass

            return {
                "file": os.path.basename(file_path), "artist": artist, "genre": genre, "bpm": bpm,
                "key": estimated_key, "sub_bass_db": float(sub_bass_db),
                "mid_bass_db": float(mid_bass_db), "punchiness": float(punchiness),
            }
        except Exception:
            logging.error(f"Échec du traitement de {os.path.basename(file_path)}", exc_info=True)
            return None

    def run(self):
        print("\n--- Étape 2: Analyse des Fichiers Musicaux ---")
        logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(message)s', filename=self.error_log, filemode='w')

        if not os.path.isdir(self.source_dir):
            print(f"[ERREUR] Le dossier source '{self.source_dir}' est introuvable.")
            return False

        supported_ext = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
        music_files = [os.path.join(root, file) for root, _, files in os.walk(self.source_dir) for file in files if any(file.lower().endswith(ext) for ext in supported_ext)]

        if not music_files:
            print(f"[AVERTISSEMENT] Aucun fichier musical trouvé dans '{self.source_dir}'.")
            return False
            
        print(f"{len(music_files)} fichier(s) trouvé(s). Début de l'analyse... (erreurs dans '{self.error_log}')")
        
        valid_results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {executor.submit(self._analyze_file, f): f for f in music_files}
            for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(music_files), desc="Analyse en cours"):
                result = future.result()
                if result:
                    valid_results.append(result)

        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(valid_results, f, indent=4, ensure_ascii=False)

        print(f"[INFO] Analyse terminée. Données exportées dans '{self.output_file}'.")
        return True


# ==============================================================================
# CLASSE 3: Importer
# ==============================================================================
class Importer:
    """
    Importe les données de music_data.json dans la base de données.
    """
    def __init__(self, music_data_file="music_data.json"):
        self.music_data_file = music_data_file

    def _get_or_create_batch(self, session: Session, cache: dict, model, **kwargs):
        """
        Récupère une instance depuis le cache ou la DB. Si elle n'existe nulle part,
        la crée et l'ajoute à la session (sans commit).
        """
        # Clé de cache spécifique pour le modèle Group pour éviter les collisions
        if model.__name__ == 'Group':
            cache_key = f"Group-{kwargs['nom']}-{kwargs.get('type')}-{kwargs.get('parent_id')}"
        else:
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

    def _clean_filename(self, filename):
        """Supprime le préfixe numérique du nom de fichier."""
        return re.sub(r'^\d+\.\s*', '', filename)

    def get_bass_type_from_punchiness(self, punchiness):
        """Détermine le type de basse à partir de la valeur de punchiness."""
        if punchiness < 0.8: return "Basse Douce"
        if 0.8 <= punchiness < 1.5: return "Basse Rythmée"
        return "Basse Agressive"

    def importer_donnees_de_base(self, session: Session):
        """
        Importe les données de base (Musiques, Artistes, Genres, etc.) depuis music_data.json.
        """
        print(f"\n--- Étape 1: Importation des données de base depuis '{self.music_data_file}' ---")
        try:
            with open(self.music_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[ERREUR] Impossible de lire '{self.music_data_file}': {e}")
            return False

        musiques_ajoutees = 0
        processed_files = set(row[0] for row in session.query(Musique.nom_fichier).all())
        local_cache = {}

        for morceau_data in tqdm(data, desc="Préparation des musiques"):
            cleaned_filename = self._clean_filename(morceau_data['file'])
            
            if cleaned_filename in processed_files:
                continue
            
            processed_files.add(cleaned_filename)

            artiste = self._get_or_create_batch(session, local_cache, Artiste, nom=morceau_data.get('artist', 'Unknown').strip())
            genre = self._get_or_create_batch(session, local_cache, GenreMusical, nom=morceau_data.get('genre', 'Unknown').strip())
            cle_musicale = self._get_or_create_batch(session, local_cache, CleMusicale, nom=morceau_data.get('key', 'Unknown').strip())
            
            punch = morceau_data.get('punchiness', 0.0)
            bass_type_name = self.get_bass_type_from_punchiness(punch)
            type_de_basse = self._get_or_create_batch(session, local_cache, TypeDeBasse, nom=bass_type_name)

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
        return True

    
    def run(self):
        print("\n--- Étape 3: Injection des données dans la base de données ---")
        
        # Construit le chemin vers la DB relative au script
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'DB', 'music_library.db'))
        
        if os.path.exists(db_path):
            # Fermer toutes les connexions à la base de données
            print("Fermeture des connexions existantes...")
            engine.dispose()
            
            # Attendre un moment pour que les connexions se ferment
            import time
            time.sleep(0.1)
            
            # Supprimer l'ancienne base de données
            try:
                os.remove(db_path)
                print(f"Ancienne base de données '{db_path}' supprimée pour une reconstruction propre.")
            except PermissionError as e:
                print(f"[ERREUR] Impossible de supprimer la base de données: {e}")
                print("[INFO] Tentative de réinitialisation sans suppression...")
                # Au lieu de supprimer, on réinitialise les tables
                Base.metadata.drop_all(bind=engine)
                print("Tables précédentes supprimées.")

        print("Création de toutes les tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables prêtes.")
        
        db = SessionLocal()
        
        try:
            if not self.importer_donnees_de_base(db):
                return False
        finally:
            db.close()

        print("[INFO] Injection des données terminée.")
        return True

# ==============================================================================
# SCRIPT PRINCIPAL
# ==============================================================================
def main():
    """
    Fonction principale pour orchestrer le pipeline PulseCrafter.
    """
    parser = argparse.ArgumentParser(
        description="PulseCrafter: Outil de gestion de bibliothèque musicale.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--steps', 
        nargs='+', 
        choices=['download', 'analyze', 'import', 'all'],
        default=['all'],
        help='''Spécifiez les étapes à exécuter:
  - download: Télécharge les playlists depuis playlist.txt.
  - analyze: Analyse les fichiers audio pour créer music_data.json.
  - import: Importe les données dans la base de données.
  - all: Exécute toutes les étapes (par défaut).'''
    )
    args = parser.parse_args()
    steps_to_run = args.steps
    
    if 'all' in steps_to_run:
        steps_to_run = ['download', 'analyze', 'import']

    print(">>> Demarrage de PulseCrafter >>")
    
    if 'download' in steps_to_run:
        downloader = Downloader()
        if not downloader.run():
            if not _confirm_continue(): sys.exit(1)
            
    if 'analyze' in steps_to_run:
        analyzer = MusicAnalyzer()
        if not analyzer.run():
            if not _confirm_continue(): sys.exit(1)

    if 'import' in steps_to_run:
        importer = Importer()
        if not importer.run():
            if not _confirm_continue(): sys.exit(1)
        
    print("\n[SUCCESS] PulseCrafter a termine son travail!")

def _confirm_continue():
    """Demande à l'utilisateur s'il veut continuer malgré une erreur."""
    choice = input("[QUESTION] Une étape a échoué. Continuer quand même? (o/N): ").lower().strip()
    return choice == 'o'

if __name__ == "__main__":
    main()
