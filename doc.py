from werkzeug.security import generate_password_hash
from models import Doctor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a doctor account with Firestore
def create_doctor():
    try:
        # Check if doctor already exists
        logger.info("Checking if doctor1 already exists...")
        existing_doctor = Doctor.query_by_username('doctor1')
        
        if not existing_doctor:
            logger.info("Creating new doctor account")
            doctor = Doctor(username='doctor1')
            doctor.set_password('12345')
            doctor_id = doctor.save()
            logger.info(f"Doctor created with ID: {doctor_id}")
            print(f"Doctor created with ID: {doctor_id}")
        else:
            logger.info("Doctor 'doctor1' already exists")
            print("Doctor 'doctor1' already exists")
    except Exception as e:
        logger.error(f"Error creating doctor: {str(e)}")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    create_doctor()