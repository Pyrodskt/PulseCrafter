# PulseCrafter: Your Intelligent DJ Playlist Assistant

**PulseCrafter** is a sophisticated music library management tool designed for DJs and electronic music enthusiasts. It transforms your local music library into a powerful, interactive database, analyzes each track's musical properties, and provides intelligent tools to help you build perfectly compatible and harmonically mixed playlists.

At its core, PulseCrafter features a dynamic, single-page web interface that allows you to explore your music, create multiple playlists, and leverage an advanced compatibility scoring engine to craft the perfect set.

*(Placeholder for a screenshot of the application's two-column interface)*

---

## ✨ Key Features

- **Dynamic Single-Page Interface**: Navigate seamlessly between your music library and a hierarchical group explorer without page reloads. The persistent two-column layout keeps your currently selected playlist always in view.

- **Advanced Playlist Manager**:
    - **Multi-Playlist Support**: Create and switch between multiple named playlists. All playlists are saved in your browser's local storage.
    - **Drag & Drop Reordering**: Easily change the order of tracks within a playlist by dragging and dropping them.
    - **Live Compatibility Analysis**: Get instant feedback on your track sequencing. PulseCrafter analyzes each transition in your playlist in real-time.

- **Intelligent Compatibility Scoring**:
    - **Global & Transition Scores**: See a "Global Compatibility Score" for your entire playlist and individual scores for each transition, color-coded for clarity (Green > 75%, Yellow > 50%, Red <= 50%).
    - **Weighted Analysis**: The scoring engine uses a weighted algorithm that prioritizes what's most important for a good mix:
        - **Key Compatibility (50%)**: Based on the Circle of Fifths (Camelot system) to ensure harmonic mixes.
        - **BPM Progression (30%)**: Rewards smooth, slight increases in tempo to maintain energy.
        - **Genre Similarity (10%)**: Uses a compatibility map to allow for smooth transitions between related genres (e.g., Techno -> Tech House).
        - **Punchiness/Energy (10%)**: Analyzes the track's energy to ensure a consistent flow.
    - **Detailed Tooltips**: Hover over a transition score to see a full breakdown of why tracks are or aren't compatible.

- **"Autocraft" Playlist Generator**:
    - Automatically build a compatible playlist based on your criteria.
    - Select one or more genres, a start/end BPM, and a desired number of tracks.
    - The Autocraft engine uses the advanced scoring system to intelligently select the best possible sequence of tracks from your library.

---

## 🚀 Getting Started

### 1. Setup & Music Analysis

Before running the web application, you must first analyze your music library.

1.  **Clone the repository** and navigate into the project folder.
2.  **Place your music files** (MP3, WAV, etc.) into the `Core/musics` directory.
3.  **(Optional but recommended)** Create and activate a Python virtual environment.
4.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
5.  **Run the analysis pipeline**: This script analyzes your music files, extracts their properties (BPM, key, genre, etc.), and populates the local database.
    ```bash
    python Core/PulseCrafter.py
    ```
    *Note: This script can also be used for downloading from SoundCloud and organizing files. See "Backend Data Processing" for more details.*

### 2. Run the Web Application

Once your music has been analyzed and the database is populated, you can launch the interactive web interface.

```bash
python Front/app.py
```

Navigate to **http://127.0.0.1:5000** in your browser to start using PulseCrafter.

---

## ⚙️ Backend Data Processing (`PulseCrafter.py`)

The `Core/PulseCrafter.py` script is the orchestrator for all backend data processing. While running it without arguments is sufficient for most use cases, you can also execute specific steps.

**Arguments for `--steps`:**
*   `download`: Downloads playlists from SoundCloud URLs listed in `playlist.txt`.
*   `analyze`: Analyzes audio files in `Core/musics` to create `music_data.json`.
*   `group`: Creates the hierarchical group structure `grouped_music.json`.
*   `organize`: Physically copies audio files into a structured directory tree based on the groups.

**Example:** To re-analyze and re-organize existing files without downloading:
```bash
python Core/PulseCrafter.py --steps analyze group organize
```

---

## 🗃️ Database Structure

The application uses a normalized, hierarchical SQLite database (`DB/music_library.db`) to store all music data and relationships.

*   **Tables**: `artistes`, `genres`, `cles_musicales`, `types_de_basse` store reference data. `musiques` is the central table for track information. `groups` stores the hierarchical nodes, and `group_music_association` links tracks to groups.
*   **Diagram**:
![Database Diagram](DB/drawSQL-image-export-2025-12-14.png?raw=true)
