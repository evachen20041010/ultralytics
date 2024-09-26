import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

cred = credentials.Certificate("code/firebase/key.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'parking-test-f9490.appspot.com'
})

db = firestore.client()

doc_ref = db.collection("parking_1").document("area_1")
doc_ref.set({"total_space": 10, "occupied_space": 6, "empty_space": 4})