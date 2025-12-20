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
from collections import defaultdict
from tqdm import tqdm
import librosa
import numpy as np
from mutagen.easyid3 import EasyID3
from mutagen import File
import concurrent.futures

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

    def run(self):
        print("\n--- Étape 1: Téléchargement des Playlists ---")
        playlist_path = Path(self.playlist_file)
        download_path = Path(self.download_dir)
        download_path.mkdir(exist_ok=True)

        if not playlist_path.exists():
            print(f"[AVERTISSEMENT] Fichier de playlists '{self.playlist_file}' introuvable. Étape de téléchargement ignorée.")
            return False

        with playlist_path.open("r", encoding="utf-8") as f:
            playlists = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        if not playlists:
            print("[INFO] Aucune playlist à télécharger.")
            return False

        print(f"[INFO] {len(playlists)} playlist(s) à télécharger dans '{self.download_dir}'.")
        for idx, url in enumerate(playlists):
            print(f"  -> Téléchargement [{idx + 1}/{len(playlists)}]: {url}")
            try:
                subprocess.run(
                    [
                        "scdl", "-l", url, "--path", str(download_path), "--onlymp3",
                        "--hide-progress", "--no-playlist-folder", "--original-name",
                        "--hidewarnings", "--no-original"
                    ],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
                )
            except subprocess.CalledProcessError as e:
                print(f"    [ERREUR] Échec du téléchargement pour {url}. Stderr: {e.stderr}")
            except FileNotFoundError:
                print("[ERREUR FATALE] La commande 'scdl' est introuvable. Assurez-vous qu'elle est installée et dans le PATH.")
                return False
        print("[INFO] Téléchargement terminé.")
        return True

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
# CLASSE 3: MusicGrouper
# ==============================================================================
class MusicGrouper:
    """
    Regroupe les musiques par genre, type de basse, clé et BPM.
    """
    def __init__(self, input_file="music_data.json", output_file="grouped_music.json"):
        self.input_file = input_file
        self.output_file = output_file
        self.KEY_TO_CAMELOT = {
            'A Major': '11B', 'F# Minor': '11A', 'E Major': '12B', 'C# Minor': '12A',
            'B Major': '1B', 'G# Minor': '1A', 'F# Major': '2B', 'D# Minor': '2A',
            'Gb Major': '2B', 'Eb Minor': '2A', 'C# Major': '3B', 'A# Minor': '3A',
            'Db Major': '3B', 'Bb Minor': '3A', 'G# Major': '4B', 'F Minor': '4A',
            'Ab Major': '4B', 'D# Major': '5B', 'C Minor': '5A', 'Eb Major': '5B',
            'A# Major': '6B', 'G Minor': '6A', 'Bb Major': '6B', 'F Major': '7B',
            'D Minor': '7A', 'C Major': '8B', 'A Minor': '8A', 'G Major': '9B',
            'E Minor': '9A', 'D Major': '10B', 'B Minor': '10A',
        }

    def _are_keys_compatible(self, key1, key2):
        if key1 not in self.KEY_TO_CAMELOT or key2 not in self.KEY_TO_CAMELOT: return False
        code1, code2 = self.KEY_TO_CAMELOT[key1], self.KEY_TO_CAMELOT[key2]
        num1, letter1 = int(code1[:-1]), code1[-1]
        num2, letter2 = int(code2[:-1]), code2[-1]
        if num1 == num2: return True
        if letter1 == letter2 and (abs(num1 - num2) == 1 or {num1, num2} == {1, 12}): return True
        return False

    def _get_bass_type(self, punchiness):
        if punchiness < 0.8: return "Basse Douce"
        if 0.8 <= punchiness < 1.5: return "Basse Rythmée"
        return "Basse Agressive"

    def _get_clean_name(self, filename):
        return re.sub(r'^\d+\.\s*', '', filename)

    def _find_key_clusters(self, track_list):
        key_clusters_dict = {}
        unassigned_tracks = list(track_list)
        cluster_count = 0

        while unassigned_tracks:
            cluster_count += 1
            base_track = unassigned_tracks.pop(0)
            current_key_cluster = [base_track]
            
            remaining_after_check = []
            for other_track in unassigned_tracks:
                if self._are_keys_compatible(base_track['key'], other_track['key']):
                    current_key_cluster.append(other_track)
                else:
                    remaining_after_check.append(other_track)
            unassigned_tracks = remaining_after_check
            
            # Sub-group by BPM
            current_key_cluster.sort(key=lambda t: t['bpm'])
            bpm_groups_list = []
            if current_key_cluster:
                temp_bpm_group = [current_key_cluster[0]]
                for i in range(1, len(current_key_cluster)):
                    if abs(current_key_cluster[i]['bpm'] - temp_bpm_group[0]['bpm']) <= 10:
                        temp_bpm_group.append(current_key_cluster[i])
                    else:
                        bpm_groups_list.append(temp_bpm_group)
                        temp_bpm_group = [current_key_cluster[i]]
                if temp_bpm_group: bpm_groups_list.append(temp_bpm_group)

            bpm_groups_dict = {
                f"Groupe de BPM {i+1}": [t['file'] for t in g]
                for i, g in enumerate(bpm_groups_list) if g
            }
            if bpm_groups_dict:
                key_clusters_dict[f"Groupe de Clés {cluster_count}"] = bpm_groups_dict
        
        return key_clusters_dict
        
    def run(self):
        print("\n--- Étape 3: Regroupement des Morceaux ---")
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                music_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"[ERREUR] Impossible de lire '{self.input_file}'. Exécutez l'analyse d'abord.")
            return False

        temp_groups = defaultdict(lambda: defaultdict(list))
        for track in music_data:
            temp_groups[track.get("genre", "Inconnu")][self._get_bass_type(track.get("punchiness", 0.0))].append(track)

        final_groups = defaultdict(lambda: defaultdict(dict))
        for genre, bass_groups in temp_groups.items():
            for bass_type, tracks in bass_groups.items():
                seen_names = set()
                unique_tracks = [t for t in tracks if self._get_clean_name(t['file']) not in seen_names and not seen_names.add(self._get_clean_name(t['file']))]
                
                if unique_tracks:
                    final_groups[genre][bass_type] = self._find_key_clusters(unique_tracks)

        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(final_groups, f, indent=4, ensure_ascii=False)

        print(f"[INFO] Regroupement terminé. Données exportées dans '{self.output_file}'.")
        return True

# ==============================================================================
# CLASSE 4: PlaylistOrganizer
# ==============================================================================
class PlaylistOrganizer:
    """
    Crée une arborescence de dossiers de playlists et y copie les fichiers musicaux.
    """
    def __init__(self, source_dir="musics", input_file="grouped_music.json", output_dir="PulseCrafter_Playlists"):
        self.source_dir = source_dir
        self.input_file = input_file
        self.output_dir = output_dir

    def _find_source_files(self):
        file_map = {}
        for root, _, files in os.walk(self.source_dir):
            for file in files:
                file_map[file] = os.path.join(root, file)
        return file_map

    def _sanitize_dirname(self, name):
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    def run(self):
        print("\n--- Étape 4: Organisation des Dossiers de Playlists ---")
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                grouped_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"[ERREUR] Impossible de lire '{self.input_file}'. Exécutez le regroupement d'abord.")
            return False

        source_map = self._find_source_files()
        if not source_map:
            print(f"[AVERTISSEMENT] Aucun fichier source trouvé dans '{self.source_dir}'.")
            return False

        copy_ops = []
        def collect_ops(data, path_parts):
            if isinstance(data, dict):
                for key, value in data.items():
                    collect_ops(value, path_parts + [self._sanitize_dirname(key)])
            elif isinstance(data, list):
                dest_dir = os.path.join(self.output_dir, *path_parts)
                for filename in data:
                    if filename in source_map:
                        copy_ops.append((source_map[filename], os.path.join(dest_dir, filename)))
                    else:
                        print(f"  [AVERTISSEMENT] Fichier source introuvable: {filename}")
        
        collect_ops(grouped_data, [])

        if not copy_ops:
            print("[INFO] Aucune copie de fichier à effectuer.")
            return True

        print(f"{len(copy_ops)} fichiers à organiser dans '{self.output_dir}'.")
        for src, dest in tqdm(copy_ops, desc="Copie des fichiers"):
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if not os.path.exists(dest):
                    shutil.copy2(src, dest)
            except Exception as e:
                print(f"\n[ERREUR] Échec de la copie de {src} vers {dest}: {e}")
        
        print("[INFO] Organisation des playlists terminée.")
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
        choices=['download', 'analyze', 'group', 'organize', 'all'],
        default=['all'],
        help='''Spécifiez les étapes à exécuter:
  - download: Télécharge les playlists depuis playlist.txt.
  - analyze: Analyse les fichiers audio pour créer music_data.json.
  - group: Regroupe les musiques depuis music_data.json dans grouped_music.json.
  - organize: Copie les fichiers dans une nouvelle arborescence de dossiers.
  - all: Exécute toutes les étapes (par défaut).'''
    )
    args = parser.parse_args()
    steps_to_run = args.steps
    
    if 'all' in steps_to_run:
        steps_to_run = ['download', 'analyze', 'group', 'organize']

    print("🚀 Démarrage de PulseCrafter 🚀")
    
    if 'download' in steps_to_run:
        downloader = Downloader()
        if not downloader.run():
            if not _confirm_continue(): sys.exit(1)
            
    if 'analyze' in steps_to_run:
        analyzer = MusicAnalyzer()
        if not analyzer.run():
            if not _confirm_continue(): sys.exit(1)

    if 'group' in steps_to_run:
        grouper = MusicGrouper()
        if not grouper.run():
            if not _confirm_continue(): sys.exit(1)

    if 'organize' in steps_to_run:
        organizer = PlaylistOrganizer()
        organizer.run()
        
    print("\n🎉 PulseCrafter a terminé son travail! 🎉")

def _confirm_continue():
    """Demande à l'utilisateur s'il veut continuer malgré une erreur."""
    choice = input("[QUESTION] Une étape a échoué. Continuer quand même? (o/N): ").lower().strip()
    return choice == 'o'

if __name__ == "__main__":
    main()
