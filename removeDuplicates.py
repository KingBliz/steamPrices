import firebase_admin
from firebase_admin import credentials, firestore
import json

cred = credentials.Certificate("key.json")
firebase_admin.initialize_app(cred)

db = firestore.client()
collection_name = "your_collection_name"

def remove_duplicates():
  
    collection_ref = db.collection(collection_name)
    docs = collection_ref.stream()

    unique_items = set()  
    duplicates = []  

    for doc in docs:
        doc_id = doc.id
        data = doc.to_dict()

        data_serialized = json.dumps(data, sort_keys=True)

        if data_serialized in unique_items:
            duplicates.append(doc_id)
        else:
            unique_items.add(data_serialized)

    for duplicate_id in duplicates:
        collection_ref.document(duplicate_id).delete()

    print(f"Removed {len(duplicates)} duplicates.")

remove_duplicates()
