# api.py
# Une API FastAPI pour gérer une bibliothèque musicale avec une structure hiérarchique.

import sys
import os

# Ajoute la racine du projet au PYTHONPATH pour permettre les imports inter-modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from typing import List, Optional
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, ConfigDict, Field

# Importation des modèles et de la configuration de la base de données
from DB.database_models import (
    Base,
    engine,
    SessionLocal,
    Musique as MusiqueDB,
    Artiste as ArtisteDB,
    GenreMusical as GenreDB,
    CleMusicale as CleDB,
    TypeDeBasse as TypeDeBasseDB,
    Group as GroupDB,
)

# ==============================================================================
# Application et Endpoints API
# ==============================================================================

app = FastAPI(
    title="PulseCrafter API",
    description="API pour gérer et explorer une bibliothèque musicale hiérarchique.",
    version="2.0.0",
)

# --- Configuration CORS ---
origins = [
    "http://localhost:5000",
    "http://127.0.0.1:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Modèles Pydantic pour l'API
# ==============================================================================

# --- Modèles de base ---
class Artiste(BaseModel):
    id: int
    nom: str
    model_config = ConfigDict(from_attributes=True)

class GenreMusical(BaseModel):
    id: int
    nom: str
    model_config = ConfigDict(from_attributes=True)

class CleMusicale(BaseModel):
    id: int
    nom: str
    model_config = ConfigDict(from_attributes=True)

class TypeDeBasse(BaseModel):
    id: int
    nom: str
    model_config = ConfigDict(from_attributes=True)

# --- Modèles pour Musique ---
class Musique(BaseModel):
    id: int
    nom_fichier: str
    bpm: Optional[int] = None
    punchiness: Optional[float] = None
    artiste: Artiste
    genre: GenreMusical
    cle_musicale: CleMusicale
    type_de_basse: TypeDeBasse
    model_config = ConfigDict(from_attributes=True)
    
# --- Modèles pour Groupes (Hiérarchique) ---
class Group(BaseModel):
    id: int
    nom: str
    type: str
    parent_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class GroupTree(Group):
    children: List['GroupTree'] = []

class GroupDetail(Group):
    children: List['GroupDetail'] = []
    musiques: List[Musique] = []

# ==============================================================================
# Fonctions CRUD (Logique métier)
# ==============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_music(db: Session, music_id: int) -> Optional[MusiqueDB]:
    return (
        db.query(MusiqueDB)
        .options(
            joinedload(MusiqueDB.artiste),
            joinedload(MusiqueDB.genre),
            joinedload(MusiqueDB.cle_musicale),
            joinedload(MusiqueDB.type_de_basse),
        )
        .filter(MusiqueDB.id == music_id)
        .first()
    )

def get_musics(db: Session, skip: int = 0, limit: int = 100) -> List[MusiqueDB]:
    return (
        db.query(MusiqueDB)
        .options(
            joinedload(MusiqueDB.artiste),
            joinedload(MusiqueDB.genre),
            joinedload(MusiqueDB.cle_musicale),
            joinedload(MusiqueDB.type_de_basse),
        )
        .order_by(MusiqueDB.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_groups(db: Session, parent_id: Optional[int] = None) -> List[GroupDB]:
    """Récupère les groupes, soit à la racine (parent_id=None), soit les enfants d'un groupe."""
    return db.query(GroupDB).filter(GroupDB.parent_id == parent_id).all()

def get_all_groups(db: Session) -> List[GroupDB]:
    """Récupère tous les groupes de la base de données."""
    return db.query(GroupDB).order_by(GroupDB.id).all()
    
def get_groups_as_tree(db: Session) -> List[GroupDB]:
    """Récupère tous les groupes et les organise en une arborescence."""
    all_groups = db.query(GroupDB).options(joinedload(GroupDB.children)).all()
    map = {g.id: g for g in all_groups}
    roots = []
    for group in all_groups:
        if group.parent_id:
            parent = map.get(group.parent_id)
            if parent:
                # This check avoids adding a child twice if it's already loaded by the relationship
                if group not in parent.children:
                    parent.children.append(group)
            else:
                roots.append(group)
        else:
            roots.append(group)
    return roots

def get_group_details(db: Session, group_id: int) -> Optional[GroupDB]:
    """Récupère un groupe avec ses enfants et musiques."""
    return (
        db.query(GroupDB)
        .options(
            joinedload(GroupDB.children),
            joinedload(GroupDB.musiques).subqueryload(MusiqueDB.artiste),
            joinedload(GroupDB.musiques).subqueryload(MusiqueDB.genre),
            joinedload(GroupDB.musiques).subqueryload(MusiqueDB.cle_musicale),
            joinedload(GroupDB.musiques).subqueryload(MusiqueDB.type_de_basse),
        )
        .filter(GroupDB.id == group_id)
        .first()
    )

# ==============================================================================
# Application et Endpoints API
# ==============================================================================



@app.on_event("startup")
def on_startup():
    print("Vérification et création des tables de la base de données...")
    Base.metadata.create_all(bind=engine)
    print("Tables prêtes.")

@app.get("/musics/", response_model=List[Musique], tags=["Musiques"])
def read_musics_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Liste toutes les musiques de la base de données."""
    return get_musics(db, skip=skip, limit=limit)

@app.get("/musics/{music_id}", response_model=Musique, tags=["Musiques"])
def read_music_endpoint(music_id: int, db: Session = Depends(get_db)):
    """Récupère les détails d'une musique spécifique par son ID."""
    db_music = get_music(db, music_id=music_id)
    if db_music is None:
        raise HTTPException(status_code=404, detail="Musique non trouvée")
    return db_music

@app.get("/groups/", response_model=List[Group], tags=["Groupes"])
def read_groups_endpoint(parent_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Liste les groupes. Fournir un 'parent_id' pour lister les sous-groupes.
    Par défaut (sans parent_id), liste les groupes racines (les genres).
    """
    return get_groups(db, parent_id=parent_id)

@app.get("/groups/all", response_model=List[Group], tags=["Groupes"])
def read_all_groups_endpoint(db: Session = Depends(get_db)):
    """Liste tous les groupes de la base de données en une seule fois (liste à plat)."""
    return get_all_groups(db)

@app.get("/groups/tree", response_model=List[GroupTree], tags=["Groupes"])
def read_groups_tree_endpoint(db: Session = Depends(get_db)):
    """Liste tous les groupes sous forme d'arborescence hiérarchique."""
    return get_groups_as_tree(db)

@app.get("/groups/{group_id}", response_model=GroupDetail, tags=["Groupes"])
def read_group_details_endpoint(group_id: int, db: Session = Depends(get_db)):
    """
    Récupère les détails complets d'un groupe, y compris ses sous-groupes et les musiques qu'il contient.
    """
    db_group = get_group_details(db, group_id=group_id)
    if db_group is None:
        raise HTTPException(status_code=404, detail="Groupe non trouvé")
    return db_group

# ==============================================================================
# Point d'entrée pour lancer le serveur
# ==============================================================================

if __name__ == "__main__":
    print("Démarrage du serveur API FastAPI sur http://127.0.0.1:8000")
    print("Documentation de l'API disponible sur http://127.0.0.1:8000/docs")
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
