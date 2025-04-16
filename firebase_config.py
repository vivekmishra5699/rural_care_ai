import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
import json

load_dotenv()

def initialize_firebase():
    """Initialize Firebase connection"""
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # Use the rural-care-ai.json file provided
        service_account_path = os.path.join(os.path.dirname(__file__), 'rural-care-ai.json')
        
        # Check if file exists
        if not os.path.exists(service_account_path):
            raise FileNotFoundError(f"Service account file not found at {service_account_path}")
            
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
    
    # Return Firestore client
    return firestore.client()

# Initialize db connection
db = initialize_firebase()