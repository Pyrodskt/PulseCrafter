# check_db.py
import sys
import os

# Add project root to Python path to allow module imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from DB.database_models import SessionLocal, Group as GroupDB

def check_groups():
    print("Connecting to the database to check for groups...")
    db = SessionLocal()
    try:
        all_groups = db.query(GroupDB).all()
        if not all_groups:
            print("[ERROR] The 'groups' table is empty.")
            return

        print(f"Found {len(all_groups)} groups in total.")
        
        group_names = {group.nom for group in all_groups}
        
        print("\nAll root group names found in the database:")
        root_groups = [g.nom for g in all_groups if g.parent_id is None]
        print(root_groups)

        # Specifically check for 'techno'
        print("\n--- Verification ---")
        if 'techno' in group_names:
            print("[SUCCESS] The 'techno' group exists in the database.")
            techno_group = db.query(GroupDB).filter_by(nom='techno').first()
            if techno_group:
                print(f"  - ID: {techno_group.id}")
                print(f"  - Type: {techno_group.type}")
                print(f"  - Parent ID: {techno_group.parent_id}")
                
                # Check for children
                children_count = db.query(GroupDB).filter_by(parent_id=techno_group.id).count()
                print(f"  - Found {children_count} child groups for 'techno'.")

        else:
            print("[FAILURE] The 'techno' group does NOT exist in the database.")
            print("This indicates an issue with the import script or the source data file.")

finally:
        db.close()
        print("\nDatabase check complete. Connection closed.")

if __name__ == "__main__":
    check_groups()
