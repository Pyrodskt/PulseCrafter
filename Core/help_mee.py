import json

def comparer_json(chemin_file1, chemin_file2):
    try:
        # Chargement des données
        with open(chemin_file1, 'r', encoding='utf-8') as f1, \
             open(chemin_file2, 'r', encoding='utf-8') as f2:
            data1 = json.load(f1)
            data2 = json.load(f2)

        # Extraction des noms de fichiers du fichier 2 pour une recherche rapide
        fichiers_dans_2 = {obj.get("file") for obj in data2 if "file" in obj}

        # Identification des objets de data1 absents de data2
        manquants = [obj for obj in data1 if obj.get("file") not in fichiers_dans_2]

        return manquants

    except FileNotFoundError as e:
        return f"Erreur : Un des fichiers est introuvable. {e}"
    except json.JSONDecodeError:
        return "Erreur : Format JSON invalide dans l'un des fichiers."

# --- Utilisation ---
fichier1 = 'music_data copy.json'
fichier2 = 'music_data.json'

resultat = comparer_json(fichier1, fichier2)

if isinstance(resultat, list):
    print(f"Nombre d'objets trouvés uniquement dans {fichier1} : {len(resultat)}")
    # Affichage du résultat ou sauvegarde dans un nouveau fichier
    with open('differences.json', 'w', encoding='utf-8') as f_out:
        json.dump(resultat, f_out, indent=4, ensure_ascii=False)
    print("La liste a été sauvegardée dans 'differences.json'.")
else:
    print(resultat)