# api.py
# Une API FastAPI pour gérer une bibliothèque musicale avec une structure hiérarchique.

from typing import List, Optional
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, ConfigDict, Field

# Importation des modèles et de la configuration de la base de données
from database_models import (
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

app = FastAPI(
    title="PulseCrafter API",
    description="API pour gérer et explorer une bibliothèque musicale hiérarchique.",
    version="2.0.0",
)

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
