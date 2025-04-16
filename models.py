from firebase_admin import firestore
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

# Import the Firestore client
from firebase_config import db

class FirestoreModel:
    """Base model with common Firestore operations"""
    
    collection_name = None
    
    def convert_dates(self):
        """Convert ISO date strings to datetime objects for template rendering"""
        for key, value in self.__dict__.items():
            if isinstance(value, str) and key in ['date', 'date_of_birth', 'last_updated', 'analysis_timestamp']:
                try:
                    # Try to parse the ISO format date
                    setattr(self, key, datetime.fromisoformat(value))
                except (ValueError, TypeError):
                    # If parsing fails, keep the original value
                    pass
        return self
    
    @classmethod
    def get_by_id(cls, doc_id):
        """Get document by ID"""
        doc = db.collection(cls.collection_name).document(doc_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            instance = cls.from_dict(data)
            # Convert date strings to datetime objects
            instance.convert_dates()
            return instance
        return None
    
    @classmethod
    def get_all(cls):
        """Get all documents in collection"""
        docs = db.collection(cls.collection_name).stream()
        return [cls.from_dict({**doc.to_dict(), 'id': doc.id}) for doc in docs]
    
    @classmethod
    def filter_by(cls, **kwargs):
        """Query collection with filters"""
        query = db.collection(cls.collection_name)
        for field, value in kwargs.items():
            query = query.where(field, '==', value)
        docs = query.stream()
        instances = []
        for doc in docs:
            instance = cls.from_dict({**doc.to_dict(), 'id': doc.id})
            # Convert date strings to datetime objects
            instance.convert_dates()
            instances.append(instance)
        return instances
    
    @classmethod
    def from_dict(cls, data):
        """Create instance from dictionary"""
        instance = cls()
        for key, value in data.items():
            setattr(instance, key, value)
        return instance
    
    def to_dict(self):
        """Convert instance to dictionary for Firestore"""
        data = {}
        for key, value in self.__dict__.items():
            if key != 'id' and not key.startswith('_'):
                # Convert datetime objects to isoformat strings
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                else:
                    data[key] = value
        return data
    
    def save(self):
        """Save instance to Firestore"""
        data = self.to_dict()
        if hasattr(self, 'id') and self.id:
            db.collection(self.collection_name).document(self.id).set(data)
        else:
            # Generate new ID if not exists
            doc_ref = db.collection(self.collection_name).document()
            self.id = doc_ref.id
            doc_ref.set(data)
        return self.id
    
    def delete(self):
        """Delete instance from Firestore"""
        if hasattr(self, 'id') and self.id:
            db.collection(self.collection_name).document(self.id).delete()
            return True
        return False

class Doctor(FirestoreModel):
    """Doctor model for Firebase Firestore"""
    collection_name = 'doctors'
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.username = kwargs.get('username')
        self.password_hash = kwargs.get('password_hash')
        self.first_name = kwargs.get('first_name')
        self.last_name = kwargs.get('last_name')
        self.email = kwargs.get('email')
        self.phone = kwargs.get('phone')
        self.license_number = kwargs.get('license_number')
        self.specialization = kwargs.get('specialization')
        self.years_experience = kwargs.get('years_experience')
        self.hospital_affiliation = kwargs.get('hospital_affiliation')
        self.registration_date = kwargs.get('registration_date', datetime.utcnow().isoformat())
        self.is_admin = kwargs.get('is_admin', False)
        self.verification_status = kwargs.get('verification_status', 'pending')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password is correct"""
        return check_password_hash(self.password_hash, password)
    
    # For Flask-Login compatibility
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    @classmethod
    def query_by_username(cls, username):
        """Get doctor by username"""
        doctors = cls.filter_by(username=username)
        return doctors[0] if doctors else None
        
    @classmethod
    def query_by_license(cls, license_number):
        """Get doctor by license number"""
        doctors = cls.filter_by(license_number=license_number)
        return doctors[0] if doctors else None

class Patient(FirestoreModel):
    """Patient model for Firebase Firestore"""
    collection_name = 'patients'
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.first_name = kwargs.get('first_name')
        self.last_name = kwargs.get('last_name')
        self.date_of_birth = kwargs.get('date_of_birth')
        self.gender = kwargs.get('gender')
        self.blood_type = kwargs.get('blood_type')
        self.contact_number = kwargs.get('contact_number')
        self.email = kwargs.get('email')
        self.height = kwargs.get('height')
        self.weight = kwargs.get('weight')
        self.allergies = kwargs.get('allergies')
        self.chronic_conditions = kwargs.get('chronic_conditions')
        self.current_medications = kwargs.get('current_medications')
        self.family_history = kwargs.get('family_history')
        self.doctor_id = kwargs.get('doctor_id')
        self.doctor_name = kwargs.get('doctor_name')  # Added for attribution
        self.last_updated = kwargs.get('last_updated', datetime.utcnow().isoformat())
        self.username = kwargs.get('username')
        self.password = kwargs.get('password')
    
    @classmethod
    def get_patients_for_doctor(cls, doctor_id):
        """Get all patients for a specific doctor"""
        return cls.filter_by(doctor_id=doctor_id)
    
    @classmethod
    def query_by_username(cls, username):
        """Get patient by username"""
        patients = cls.filter_by(username=username)
        return patients[0] if patients else None

class Visit(FirestoreModel):
    """Visit model for Firebase Firestore"""
    collection_name = 'visits'
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.patient_id = kwargs.get('patient_id')
        self.doctor_id = kwargs.get('doctor_id')  # Added doctor ID
        self.doctor_name = kwargs.get('doctor_name')  # Added doctor name
        self.date = kwargs.get('date', datetime.utcnow().isoformat())
        self.temperature = kwargs.get('temperature')
        self.blood_pressure_systolic = kwargs.get('blood_pressure_systolic')
        self.blood_pressure_diastolic = kwargs.get('blood_pressure_diastolic')
        self.heart_rate = kwargs.get('heart_rate')
        self.respiratory_rate = kwargs.get('respiratory_rate')
        self.oxygen_saturation = kwargs.get('oxygen_saturation')
        self.chief_complaint = kwargs.get('chief_complaint')
        self.symptoms = kwargs.get('symptoms')
        self.duration_of_symptoms = kwargs.get('duration_of_symptoms')
        self.severity = kwargs.get('severity')
        self.ai_suggested_diseases = kwargs.get('ai_suggested_diseases')
        self.ai_suggested_treatments = kwargs.get('ai_suggested_treatments')
        self.analysis_timestamp = kwargs.get('analysis_timestamp')
        self.diagnosis = kwargs.get('diagnosis')
        self.treatment_plan = kwargs.get('treatment_plan')
        self.prescribed_medications = kwargs.get('prescribed_medications')
        self.notes = kwargs.get('notes')
        self.status = kwargs.get('status', 'initial')
    
    @classmethod
    def get_visits_for_patient(cls, patient_id, limit=None):
        """Get visits for a specific patient, optionally limited"""
        query = db.collection(cls.collection_name).where('patient_id', '==', patient_id).order_by('date', direction=firestore.Query.DESCENDING)
        
        if limit:
            query = query.limit(limit)
            
        docs = query.stream()
        visits = []
        for doc in docs:
            visit = cls.from_dict({**doc.to_dict(), 'id': doc.id})
            visit.convert_dates()  # Convert date strings to datetime objects
            visits.append(visit)
        return visits
    
    @classmethod
    def get_latest_visit_for_patient(cls, patient_id):
        """Get most recent visit for a patient"""
        visits = cls.get_visits_for_patient(patient_id, limit=1)
        return visits[0] if visits else None
    
    @classmethod
    def delete_visits_for_patient(cls, patient_id):
        """Delete all visits for a patient"""
        docs = db.collection(cls.collection_name).where('patient_id', '==', patient_id).stream()
        for doc in docs:
            doc.reference.delete()