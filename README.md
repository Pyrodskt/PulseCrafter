# PulseCrafter: Application de Gestion de Bibliothèque Musicale

## Description

**PulseCrafter** est une application Python complète conçue pour gérer une bibliothèque musicale. Elle automatise l'ensemble du processus, du téléchargement de playlists depuis SoundCloud à l'organisation physique des fichiers en passant par une analyse musicale détaillée et un regroupement intelligent. Le projet inclut également une API FastAPI pour interagir avec la base de données de la bibliothèque.

## Fonctionnalités

1.  **Téléchargement :** Télécharge les morceaux à partir d'une liste d'URL de playlists SoundCloud.
2.  **Analyse :** Analyse chaque fichier musical pour en extraire le BPM, la clé, le genre, l'artiste et des métriques de basse détaillées (`punchiness`, `sub_bass_db`, etc.).
3.  **Regroupement :** Crée une structure de données hiérarchique en regroupant les morceaux par genre, type de basse, clé harmonique et BPM.
4.  **Organisation :** Copie physiquement les fichiers musicaux dans une nouvelle arborescence de dossiers qui reflète la structure des groupes créés.
5.  **API :** Expose une API FastAPI pour explorer la base de données, lister les musiques et naviguer dans la hiérarchie des groupes.

## Installation

Ce projet utilise Python. Assurez-vous qu'il est installé sur votre système.

1.  **Clonez le dépôt** et naviguez dans le dossier du projet.
2.  **(Optionnel mais recommandé)** Créez un environnement virtuel :
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sur Windows: venv\Scripts\activate
    ```
3.  **Installez les dépendances** requises :
    ```bash
    pip install -r requirements.txt
    ```
4.  **(Facultatif)** Si vous souhaitez utiliser la fonctionnalité de téléchargement, assurez-vous que `scdl` est installé et accessible dans votre PATH.

## Utilisation de l'Application Principale (`PulseCrafter.py`)

L'application `PulseCrafter.py` est l'orchestrateur principal qui exécute les différentes étapes du processus.

### Exécuter toutes les étapes

Pour exécuter le pipeline complet (téléchargement, analyse, regroupement, organisation), lancez simplement le script sans argument :
```bash
python PulseCrafter.py
```
ou avec l'argument `all` :
```bash
python PulseCrafter.py --steps all
```
Le script vous guidera à travers chaque étape. Si une étape échoue, il vous demandera si vous souhaitez continuer.

### Exécuter des étapes spécifiques

Vous pouvez choisir de n'exécuter que certaines étapes en utilisant le flag `--steps`. C'est utile si vous avez déjà téléchargé les fichiers et que vous voulez seulement relancer l'analyse et l'organisation.

**Arguments possibles pour `--steps` :**
*   `download` : Télécharge les playlists.
*   `analyze` : Analyse les fichiers pour créer `music_data.json`.
*   `group` : Crée la structure hiérarchique `grouped_music.json`.
*   `organize` : Copie les fichiers dans les dossiers de playlists.

**Exemple :** Pour analyser, regrouper et organiser des fichiers déjà présents :
```bash
python PulseCrafter.py --steps analyze group organize
```

---

## Documentation de l'API

Le projet inclut une API FastAPI pour interagir avec la base de données.

### Lancer l'API

```bash
python api.py
```
Le serveur démarrera sur `http://127.0.0.1:8000`. La documentation interactive (Swagger UI) est disponible à l'adresse [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Endpoints de l'API

#### Musiques

*   `GET /musics/`
    *   **Description :** Liste toutes les musiques de la base de données avec une pagination.
    *   **Paramètres de requête :** `skip` (int), `limit` (int).
    *   **Réponse :** Une liste d'objets `Musique`.

*   `GET /musics/{music_id}`
    *   **Description :** Récupère les détails complets d'une musique par son ID.
    *   **Réponse :** Un objet `Musique` complet avec artiste, genre, etc.

#### Groupes

*   `GET /groups/`
    *   **Description :** Liste les groupes. Par défaut, retourne les groupes racines (les genres).
    *   **Paramètres de requête :** `parent_id` (int). Utilisez l'ID d'un groupe pour lister ses sous-groupes.
    *   **Réponse :** Une liste d'objets `Group`.

*   `GET /groups/{group_id}`
    *   **Description :** Récupère les détails d'un groupe, y compris ses sous-groupes (`children`) et les musiques qu'il contient directement (`musiques`).
    *   **Réponse :** Un objet `GroupDetail` complet.

---

## Structure de la Base de Données

La base de données `music_library.db` (SQLite) est structurée de manière normalisée et hiérarchique.

### Diagramme des relations
![rrrrrrrrr](drawSQL-image-export-2025-12-14.png?raw=true)
```
+--------------+       +--------------+       +----------------+
|   Artistes   |       | Genres       |       |  Cles_Musicales|
+--------------+       +--------------+       +----------------+
| id (PK)      |       | id (PK)      |       | id (PK)        |
| nom (Unique) |       | nom (Unique) |       | nom (Unique)   |
+------^-------+       +------^-------+       +--------^-------+
       |                      |                        |
       | 1                    | 1                      | 1
+------|---------+     +------|---------+     +--------|---------+
|    Musiques    |     | Types_De_Basse |     |      Groups      |
+----------------+     +----------------+     +------------------+
| id (PK)        |     | id (PK)        |     | id (PK)          |
| nom_fichier(U) |     | nom (Unique)   |     | nom              |
| bpm, punchiness|     +--------^-------+     | type             |
| artiste_id (FK)|------------+ | 1            | parent_id (FK)---|--+
| genre_id (FK)  |------------+ |              +--------|---------+  |
| cle_id (FK)    |------------+ |                       | M        |
| type_basse_id(FK)-----------+                        |          |
+-------|--------+                                     |          |
        | M                                            | 1        |
        |                                              |          |
+-------V----------------+                             |          |
| group_music_association| <---------------------------+----------+
+------------------------+
| group_id (FK)          |
| music_id (FK)          |
+------------------------+
```

### Description des tables

*   **`artistes`**, **`genres`**, **`cles_musicales`**, **`types_de_basse`**: Tables de référence simples pour éviter la redondance.
*   **`musiques`**: Table centrale contenant les informations de chaque morceau, avec des clés étrangères vers les tables de référence.
*   **`groups`**: Table hiérarchique où chaque entrée est un "nœud" (un genre, un type de basse, un groupe de clés, etc.). La colonne `parent_id` pointe vers l'ID d'un autre groupe, créant ainsi la structure imbriquée.
*   **`group_music_association`**: Table de liaison qui associe les musiques aux groupes (relation Many-to-Many). Une musique peut appartenir à plusieurs groupes et un groupe peut contenir plusieurs musiques.