import random
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("certifcate.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

csgo_item_names = [
    "AK-47 | Redline",
    "AWP | Dragon Lore",
    "M4A4 | Howl",
    "Desert Eagle | Blaze",
    "Glock-18 | Fade",
    "P90 | Asiimov",
    "USP-S | Kill Confirmed",
    "Karambit | Doppler",
    "Butterfly Knife | Tiger Tooth",
    "Bayonet | Slaughter"
]

dota2_item_names = [
    "Dragonclaw Hook",
    "Manifold Paradox",
    "Golden Basher of Mage Skulls",
    "Ethereal Flame",
    "The Alpine Stalker Set",
    "Dreaded Frost Set",
    "Blade of Tears",
    "Fiery Soul of the Slayer",
    "Genuine Monarch Bow",
    "Dark Artistry"
]

qualities = [
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred"
]

rarities = [
    "Common",
    "Uncommon",
    "Rare",
    "Mythical",
    "Immortal",
    "Arcana"
]

def generate_dummy_data(item_names, attributes, num_items):
    dummy_data = []

    for _ in range(num_items):
        item = {
            "name": random.choice(item_names),
            "rarity": random.choice(attributes),
            "price": round(random.uniform(0.5, 2000.0), 2),  
            "other_fields": None 
        }
        dummy_data.append(item)

    return dummy_data

def store_to_firebase(collection_name, data):
    for item in data:
        db.collection(collection_name).add(item)

csgo_dummy_data = generate_dummy_data(csgo_item_names, qualities, 20)
dota2_dummy_data = generate_dummy_data(dota2_item_names, rarities, 20)

store_to_firebase("csgo_store", csgo_dummy_data)
store_to_firebase("dota2_store", dota2_dummy_data)

print("Dummy data for CSGO and Dota 2 has been stored in Firebase.")
