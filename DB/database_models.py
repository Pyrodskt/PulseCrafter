# database_models.py
# Fichier central pour les modèles de base de données SQLAlchemy de PulseCrafter.

import os
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Table,
    UniqueConstraint
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

# ==============================================================================
# Configuration de la Base de Données
# ==============================================================================

# Construit le chemin absolu vers la base de données pour éviter les problèmes de CWD
db_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(db_dir, 'music_library.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==============================================================================
# Table d'Association (Many-to-Many entre Musiques et Groupes)
# ==============================================================================

group_music_association = Table(
    'group_music_association', Base.metadata,
    Column('group_id', Integer, ForeignKey('groups.id'), primary_key=True),
    Column('music_id', Integer, ForeignKey('musiques.id'), primary_key=True)
)

# ==============================================================================
# Modèles de Données de Base
# ==============================================================================

class Artiste(Base):
    __tablename__ = 'artistes'
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True, nullable=False)
    musiques = relationship("Musique", back_populates="artiste")

class GenreMusical(Base):
    __tablename__ = 'genres'
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True, nullable=False)
    musiques = relationship("Musique", back_populates="genre")

class CleMusicale(Base):
    __tablename__ = 'cles_musicales'
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True, nullable=False)
    musiques = relationship("Musique", back_populates="cle_musicale")

class TypeDeBasse(Base):
    __tablename__ = 'types_de_basse'
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True, nullable=False)
    musiques = relationship("Musique", back_populates="type_de_basse")

# ==============================================================================
# Modèle Principal : Musique
# ==============================================================================

class Musique(Base):
    __tablename__ = 'musiques'
    id = Column(Integer, primary_key=True)
    nom_fichier = Column(String, unique=True, nullable=False)
    bpm = Column(Integer)
    sub_bass_db = Column(Float)
    mid_bass_db = Column(Float)
    punchiness = Column(Float)
    
    artiste_id = Column(Integer, ForeignKey('artistes.id'))
    genre_id = Column(Integer, ForeignKey('genres.id'))
    cle_musicale_id = Column(Integer, ForeignKey('cles_musicales.id'))
    type_de_basse_id = Column(Integer, ForeignKey('types_de_basse.id'))
    
    artiste = relationship("Artiste", back_populates="musiques")
    genre = relationship("GenreMusical", back_populates="musiques")
    cle_musicale = relationship("CleMusicale", back_populates="musiques")
    type_de_basse = relationship("TypeDeBasse", back_populates="musiques")
    
    groups = relationship(
        "Group",
        secondary=group_music_association,
        back_populates="musiques"
    )

# ==============================================================================
# Modèle Hiérarchique : Group
# ==============================================================================

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    nom = Column(String, nullable=False)
    type = Column(String, nullable=False) # 'genre', 'bass_type', 'key_group', 'bpm_group'
    
    parent_id = Column(Integer, ForeignKey('groups.id'))
    
    # Relations pour la hiérarchie
    parent = relationship("Group", remote_side=[id], back_populates="children")
    children = relationship("Group", back_populates="parent", cascade="all, delete-orphan")

    musiques = relationship(
        "Musique",
        secondary=group_music_association,
        back_populates="groups"
    )

    __table_args__ = (UniqueConstraint('nom', 'parent_id', 'type', name='_nom_parent_type_uc'),)