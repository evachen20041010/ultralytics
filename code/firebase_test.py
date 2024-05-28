import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage as firebase_storage
from google.cloud import storage

cred = credentials.Certificate("code/firebase/key.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'parking-test-f9490.appspot.com'
})

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    # Initialize the Google Cloud Storage client with the project ID.
    storage_client = storage.Client.from_service_account_json('code/firebase/key.json')

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Upload the file.
    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

if __name__ == "__main__":
    # Use firebase_admin to get the bucket name.
    bucket_name = firebase_storage.bucket().name

    upload_blob(bucket_name, 'runs/detect/train9/train_batch0.jpg', 'yolov8/train_batch0.jpg')
