from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import logging
from dotenv import load_dotenv
from google.generativeai import GenerativeModel
import google.generativeai as genai
from google.cloud import firestore

# Import Firestore models
from models import Doctor, Patient, Visit
from firebase_config import db

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Initialize login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Unauthorized handler for login manager
@login_manager.unauthorized_handler
def unauthorized():
    flash('You must be logged in to access this page')
    return redirect(url_for('login'))

# User loader for Flask-Login using Doctor model
@login_manager.user_loader
def load_user(user_id):
    return Doctor.get_by_id(user_id)

# Error handler for unhandled exceptions
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    flash(f"An error occurred: {str(e)}")
    return redirect(url_for('login'))

# Medical Q&A system class
class MedicalQASystem:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        genai.configure(api_key=self.api_key)
        self.model = GenerativeModel('gemini-1.5-pro')
        
    def setup(self):
        try:
            self.model.count_tokens("Test connection")
            logger.info("Gemini API initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Gemini API initialization failed: {e}")
            return False
            
    def _construct_disease_question(self, visit):
        prompt = f"""Act as a medical expert. Given these patient details:

VITAL SIGNS:
- Temperature: {visit.temperature}°C
- Blood Pressure: {visit.blood_pressure_systolic}/{visit.blood_pressure_diastolic} mmHg
- Heart Rate: {visit.heart_rate} bpm
- Respiratory Rate: {visit.respiratory_rate} /min
- O2 Saturation: {visit.oxygen_saturation}%

SYMPTOMS:
- Chief Complaint: {visit.chief_complaint}
- Symptoms: {visit.symptoms}
- Duration: {visit.duration_of_symptoms}
- Severity: {visit.severity}

Provide a structured differential diagnosis with:
1. Most likely conditions (list 3-5)
2. Supporting evidence from vitals/symptoms
3. Recommended diagnostic tests if needed
"""
        return prompt

    def _construct_treatment_question(self, visit):
        prompt = f"""Based on these patient symptoms:

- Chief Complaint: {visit.chief_complaint}
- Present Symptoms: {visit.symptoms}
- Duration: {visit.duration_of_symptoms}
- Severity Level: {visit.severity}

Provide a structured treatment plan including:
1. First-line treatment options
2. Medication recommendations if applicable
3. Lifestyle/home care advice
4. Follow-up recommendations
"""
        return prompt

    def generate_answer(self, question_type, question):
        try:
            response = self.model.generate_content(
                question,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 1024,
                }
            )
            
            if not response.text or len(response.text.strip()) < 50:
                return self._get_fallback_analysis()
                
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Generation error: {str(e)}")
            return self._get_fallback_analysis()

    def _get_fallback_analysis(self):
        return ("Unable to generate analysis. Please rely on clinical judgment.",
                "Please proceed with standard clinical protocols.")

# Routes for Doctor login/dashboard and patient management routes
@app.route('/')
@login_required
def index():
    # Get query parameters
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name_asc')
    
    # Get only current doctor's patients
    my_patients = Patient.filter_by(doctor_id=current_user.id)
    all_patients = my_patients
    
    # Perform search if query exists
    if search_query:
        filtered_patients = []
        search_query = search_query.lower()
        for patient in all_patients:
            if (search_query in (patient.first_name or '').lower() or 
                search_query in (patient.last_name or '').lower() or 
                (patient.contact_number and search_query in patient.contact_number.lower()) or
                (patient.email and search_query in patient.email.lower()) or
                (patient.id and search_query in str(patient.id).lower())):
                filtered_patients.append(patient)
        all_patients = filtered_patients
    
    # Sort the results
    if sort_by == 'name_asc':
        all_patients.sort(key=lambda p: f"{p.first_name or ''} {p.last_name or ''}")
    elif sort_by == 'name_desc':
        all_patients.sort(key=lambda p: f"{p.first_name or ''} {p.last_name or ''}", reverse=True)
    elif sort_by == 'date_updated':
        all_patients.sort(key=lambda p: p.last_updated if p.last_updated else '', reverse=True)
    elif sort_by == 'date_of_birth':
        all_patients.sort(key=lambda p: p.date_of_birth if p.date_of_birth else '')
    
    # Log the number of patients found for debugging
    logger.info(f"Found {len(all_patients)} patients matching criteria (search: {search_query})")
    
    # Calculate total visits - Fixed for Firestore
    total_visits = 0
    try:
        # Get all visits from Firestore
        visits_ref = db.collection(Visit.collection_name)
        visits_docs = visits_ref.stream()
        total_visits = sum(1 for _ in visits_docs)
    except Exception as e:
        logger.error(f"Error counting visits: {str(e)}")
    
    # Calculate visits per patient
    for patient in all_patients:
        try:
            # Count visits for this patient
            visits_query = db.collection(Visit.collection_name).where('patient_id', '==', patient.id).stream()
            patient.visit_count = sum(1 for _ in visits_query)
        except Exception as e:
            logger.error(f"Error counting patient visits: {str(e)}")
            patient.visit_count = 0
    
    return render_template('index.html', 
                          patients=all_patients, 
                          today=datetime.now(),
                          total_visits=total_visits)

@app.route('/search')
@login_required
def search_patients():
    """Dedicated search page for finding patients across the system"""
    # Get query parameters
    search_query = request.args.get('query', '')
    sort_by = request.args.get('sort', 'name_asc')
    
    if not search_query:
        return render_template('search.html', patients=[], search_query='')
    
    # Get all patients
    all_patients = []
    
    # Get patients based on doctor ownership
    # First get my patients
    my_patients = Patient.filter_by(doctor_id=current_user.id)
    for patient in my_patients:
        patient.is_my_patient = True
        all_patients.append(patient)
    
    # Get all other patients, including those with no doctor and those with other doctors
    # This query gets all patients not belonging to the current doctor
    other_patients_query = db.collection(Patient.collection_name).stream()
    
    for doc in other_patients_query:
        data = doc.to_dict()
        doctor_id = data.get('doctor_id')
        
        # Skip if this is my patient (already added)
        if doctor_id == current_user.id:
            continue
            
        # Create patient object
        patient_data = {**data, 'id': doc.id}
        patient = Patient.from_dict(patient_data)
        patient.convert_dates()
        patient.is_my_patient = False
        all_patients.append(patient)
    
    # Apply search filter
    if search_query:
        filtered_patients = []
        search_query_lower = search_query.lower()
        
        for patient in all_patients:
            # Check if any field matches search query
            if (search_query_lower in (patient.first_name or '').lower() or
                search_query_lower in (patient.last_name or '').lower() or
                search_query_lower in f"{patient.first_name or ''} {patient.last_name or ''}".lower() or
                (patient.contact_number and search_query_lower in patient.contact_number.lower()) or
                (patient.email and search_query_lower in patient.email.lower()) or
                (patient.id and search_query_lower in patient.id.lower())):
                filtered_patients.append(patient)
        
        all_patients = filtered_patients
    
    # Sort results
    if sort_by == 'name_asc':
        all_patients.sort(key=lambda p: f"{p.first_name or ''} {p.last_name or ''}")
    elif sort_by == 'name_desc':
        all_patients.sort(key=lambda p: f"{p.first_name or ''} {p.last_name or ''}", reverse=True)
    elif sort_by == 'date_updated':
        all_patients.sort(key=lambda p: p.last_updated if p.last_updated else '', reverse=True)
    elif sort_by == 'date_of_birth':
        all_patients.sort(key=lambda p: p.date_of_birth if p.date_of_birth else '')
        
    # Log search results
    logger.info(f"Search found {len(all_patients)} patients matching '{search_query}'")
    
    return render_template('search.html', 
                          patients=all_patients, 
                          search_query=search_query,
                          sort=sort_by)

@app.route('/patient/new', methods=['GET', 'POST'])
@login_required
def new_patient():
    if request.method == 'POST':
        # Get username and password from the form
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Make sure they are not None or empty
        if not username or not password:
            flash("Username and password are required", "error")
            return render_template('patient_form.html')
        
        # Convert date string to datetime
        dob_str = request.form['date_of_birth']
        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d')
            dob_iso = dob.isoformat()  # Store as ISO format string
        except ValueError:
            flash("Invalid date format", "error")
            return render_template('patient_form.html')
            
        # Process height and weight
        height = None
        if request.form.get('height'):
            try:
                height = float(request.form['height'])
            except ValueError:
                flash("Invalid height value", "error")
                return render_template('patient_form.html')
                
        weight = None
        if request.form.get('weight'):
            try:
                weight = float(request.form['weight'])
            except ValueError:
                flash("Invalid weight value", "error")
                return render_template('patient_form.html')
        
        patient = Patient(
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            date_of_birth=dob_iso,
            gender=request.form['gender'],
            blood_type=request.form.get('blood_type'),
            contact_number=request.form.get('contact_number'),
            email=request.form.get('email'),
            height=height,
            weight=weight,
            allergies=request.form.get('allergies'),
            chronic_conditions=request.form.get('chronic_conditions'),
            current_medications=request.form.get('current_medications'),
            family_history=request.form.get('family_history'),
            doctor_id=current_user.id,
            doctor_name=f"{current_user.first_name} {current_user.last_name}",  # Include doctor's name
            username=username,
            password=password,
            last_updated=datetime.utcnow().isoformat()
        )
        
        try:
            patient.save()
            flash("Patient added successfully", "success")
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error adding patient: {str(e)}")
            flash(f"Error adding patient: {str(e)}", "error")
            return render_template('patient_form.html')
            
    return render_template('patient_form.html')

@app.route('/patient/<string:id>')
@login_required
def view_patient(id):
    patient = Patient.get_by_id(id)
    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('index'))
    
    # Determine if patient belongs to current doctor
    is_my_patient = patient.doctor_id == current_user.id
    # Determine if patient is self-registered (no doctor)
    is_self_registered = patient.doctor_id is None
    # Is from another doctor
    is_other_doctor = not is_my_patient and not is_self_registered
    
    # Get ALL patient visits regardless of which doctor created them
    visits = Visit.get_visits_for_patient(id)
    
    return render_template('patient_detail.html', 
                          patient=patient, 
                          visits=visits,
                          is_my_patient=is_my_patient,
                          is_self_registered=is_self_registered,
                          is_other_doctor=is_other_doctor)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Add debug logging
        logger.info(f"Login attempt for username: {username}")
        
        doctor = Doctor.query_by_username(username)
        
        if doctor:
            logger.info(f"Doctor found with ID: {doctor.id}")
            if doctor.check_password(password):
                login_user(doctor)
                logger.info(f"Login successful for doctor: {username}")
                return redirect(url_for('index'))
            else:
                logger.warning(f"Password check failed for doctor: {username}")
        else:
            logger.warning(f"No doctor found with username: {username}")
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Extract form data
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate password match
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template('doctor_register.html')
        
        # Check if username already exists
        existing_doctor = Doctor.query_by_username(username)
        if existing_doctor:
            flash("Username already exists. Please choose another one.", "error")
            return render_template('doctor_register.html')
        
        # Check if license number already exists
        license_number = request.form.get('license_number')
        existing_license = Doctor.query_by_license(license_number)
        if existing_license:
            flash("This medical license is already registered.", "error")
            return render_template('doctor_register.html')
        
        # Create new doctor object
        doctor = Doctor(
            username=username,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            license_number=license_number,
            specialization=request.form.get('specialization'),
            years_experience=int(request.form.get('years_experience')),
            hospital_affiliation=request.form.get('hospital_affiliation'),
            registration_date=datetime.utcnow().isoformat(),
            verification_status='pending'
        )
        
        # Set password (hashed)
        doctor.set_password(password)
        
        try:
            # Save doctor to database
            doctor_id = doctor.save()
            flash("Registration successful! Your account is pending verification.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            logger.error(f"Error registering doctor: {str(e)}")
            flash(f"Registration failed: {str(e)}", "error")
    
    return render_template('doctor_register.html')

@app.route('/patient/<string:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_patient(id):
    patient = Patient.get_by_id(id)
    if not patient or patient.doctor_id != current_user.id:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Update patient data
        patient.first_name = request.form['first_name']
        patient.last_name = request.form['last_name']
        patient.date_of_birth = datetime.strptime(request.form['date_of_birth'], '%Y-%m-%d').isoformat()
        patient.gender = request.form['gender'] 
        patient.blood_type = request.form.get('blood_type')
        patient.contact_number = request.form.get('contact_number')
        patient.email = request.form.get('email')
        patient.height = float(request.form['height']) if request.form.get('height') else None
        patient.weight = float(request.form['weight']) if request.form.get('weight') else None
        patient.allergies = request.form.get('allergies')
        patient.chronic_conditions = request.form.get('chronic_conditions')
        patient.current_medications = request.form.get('current_medications')
        patient.family_history = request.form.get('family_history')
        patient.last_updated = datetime.utcnow().isoformat()
        
        # Update username and password
        patient.username = request.form.get('username')
        new_password = request.form.get('password')
        if new_password and new_password.strip():
            patient.password = new_password
        
        patient.save()
        flash("Patient updated successfully", "success")
        return redirect(url_for('index'))
        
    return render_template('patient_form.html', patient=patient)

@app.route('/patient/<string:id>/delete')
@login_required
def delete_patient(id):
    try:
        patient = Patient.get_by_id(id)
        if not patient or patient.doctor_id != current_user.id:
            flash('Unauthorized access', 'error')
            return redirect(url_for('index'))
            
        # Delete associated visits first
        Visit.delete_visits_for_patient(id)
        
        # Then delete patient
        patient.delete()
        flash('Patient deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Error deleting patient: {str(e)}")
        flash('Error deleting patient', 'error')
    return redirect(url_for('index'))

@app.route('/patient/<string:id>/visit/new', methods=['GET', 'POST'])
@login_required
def new_visit(id):
    patient = Patient.get_by_id(id)
    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('index'))
    
    # Any doctor can add a visit - no permission check needed
    
    if request.method == 'POST':
        # Process form data with proper type conversion
        visit = Visit(
            patient_id=id,
            doctor_id=current_user.id,  # Current doctor becomes the visit creator
            doctor_name=f"{current_user.first_name} {current_user.last_name}",  # Add doctor name
            temperature=float(request.form['temperature']) if request.form.get('temperature') else None,
            blood_pressure_systolic=int(request.form['blood_pressure_systolic']) if request.form.get('blood_pressure_systolic') else None,
            blood_pressure_diastolic=int(request.form['blood_pressure_diastolic']) if request.form.get('blood_pressure_diastolic') else None,
            heart_rate=int(request.form['heart_rate']) if request.form.get('heart_rate') else None,
            respiratory_rate=int(request.form['respiratory_rate']) if request.form.get('respiratory_rate') else None,
            oxygen_saturation=float(request.form['oxygen_saturation']) if request.form.get('oxygen_saturation') else None,
            chief_complaint=request.form['chief_complaint'],
            symptoms=request.form['symptoms'],
            duration_of_symptoms=request.form['duration_of_symptoms'],
            severity=request.form['severity'],
            status='initial',
            date=datetime.utcnow().isoformat()
        )
        
        # Save visit to get ID
        visit_id = visit.save()
        return redirect(url_for('generative_visit', visit_id=visit_id))
        
    return render_template('visit_form_initial.html', patient=patient)

@app.route('/visit/<string:visit_id>/generative', methods=['GET'])
@login_required
def generative_visit(visit_id):
    try:
        visit = Visit.get_by_id(visit_id)
        if not visit:
            flash("Visit not found", "error")
            return redirect(url_for('index'))
            
        # Get patient to check if it exists
        patient = Patient.get_by_id(visit.patient_id)
        if not patient:
            flash("Patient not found", "error")
            return redirect(url_for('index'))
        
        # Any doctor can add visits, so no doctor_id check here
        
        # Generate AI analysis
        qa_system = MedicalQASystem()
        qa_system.setup()
        
        diseases = qa_system.generate_answer("diagnosis", qa_system._construct_disease_question(visit))
        treatments = qa_system.generate_answer("treatment", qa_system._construct_treatment_question(visit))
        
        # Update visit with AI suggestions
        visit.ai_suggested_diseases = diseases
        visit.ai_suggested_treatments = treatments
        visit.analysis_timestamp = datetime.now().isoformat()
        visit.save()
        
        return redirect(url_for('complete_visit', visit_id=visit_id))
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        flash("Error generating analysis", "error")
        return redirect(url_for('index'))

@app.route('/visit/<string:visit_id>/complete', methods=['GET', 'POST'])
@login_required
def complete_visit(visit_id):
    visit = Visit.get_by_id(visit_id)
    if not visit:
        flash("Visit not found", "error")
        return redirect(url_for('index'))
        
    # Get the patient
    patient = Patient.get_by_id(visit.patient_id)
    if not patient:
        flash("Patient not found", "error")
        return redirect(url_for('index'))
    
    # Check if this visit was created by the current doctor
    if visit.doctor_id != current_user.id:
        flash("You can only complete visits that you created", "error")
        return redirect(url_for('view_patient', id=patient.id))
    
    if request.method == 'POST':
        # Update visit with doctor's assessment
        visit.diagnosis = request.form['diagnosis']
        visit.treatment_plan = request.form['treatment_plan']
        visit.prescribed_medications = request.form['prescribed_medications']
        visit.notes = request.form['notes']
        visit.status = 'completed'
        visit.save()
        
        return redirect(url_for('view_patient', id=patient.id))
    
    return render_template('visit_form_complete.html', visit=visit, patient=patient)

# Patient login/dashboard routes (separate from doctor login)
@app.route('/patient/login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        patient = Patient.query_by_username(username)
        
        if patient and patient.password == password:  # Direct comparison
            session['patient_id'] = patient.id
            flash('Login successful!')
            return redirect(url_for('patient_dashboard'))
        else:
            flash('Invalid username or password. Please try again.')
    
    return render_template('patient_login.html')

@app.route('/patient/dashboard')
def patient_dashboard():
    if 'patient_id' not in session:
        flash('Please login to access your dashboard.')
        return redirect(url_for('patient_login'))
    
    patient_id = session['patient_id']
    patient = Patient.get_by_id(patient_id)
    if not patient:
        flash('Patient not found.')
        return redirect(url_for('patient_login'))
    
    # Get recent visits
    visits = Visit.get_visits_for_patient(patient_id, limit=5)
    
    # Get latest visit for vital signs
    latest_visit = Visit.get_latest_visit_for_patient(patient_id)
    
    return render_template('patient_dashboard.html', 
                          patient=patient, 
                          visits=visits,
                          latest_visit=latest_visit)

@app.route('/patient/logout')
def patient_logout():
    session.pop('patient_id', None)
    flash('You have been logged out.')
    return redirect(url_for('patient_login'))

@app.route('/patient/profile/edit', methods=['GET', 'POST'])
def edit_patient_profile():
    if 'patient_id' not in session:
        flash('Please login to access your profile.')
        return redirect(url_for('patient_login'))
    
    patient_id = session['patient_id']
    patient = Patient.get_by_id(patient_id)
    if not patient:
        flash('Patient not found.')
        return redirect(url_for('patient_login'))
    
    if request.method == 'POST':
        # Update patient information
        patient.first_name = request.form.get('first_name')
        patient.last_name = request.form.get('last_name')
        patient.contact_number = request.form.get('contact_number')
        patient.email = request.form.get('email')
        patient.height = float(request.form.get('height')) if request.form.get('height') else None
        patient.weight = float(request.form.get('weight')) if request.form.get('weight') else None
        patient.allergies = request.form.get('allergies')
        patient.chronic_conditions = request.form.get('chronic_conditions')
        patient.current_medications = request.form.get('current_medications')
        patient.family_history = request.form.get('family_history')
        
        # Handle password update if provided
        new_password = request.form.get('password')
        if new_password and new_password.strip():
            patient.password = new_password
        
        try:
            patient.save()
            flash("Your profile has been updated successfully!", "success")
            return redirect(url_for('patient_dashboard'))
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
    
    return render_template('patient_edit_profile.html', patient=patient)

@app.route('/patient/visits')
def patient_visits():
    """Show all visits for the logged-in patient"""
    if 'patient_id' not in session:
        flash('Please login to access your visits.')
        return redirect(url_for('patient_login'))
    
    patient_id = session['patient_id']
    patient = Patient.get_by_id(patient_id)
    if not patient:
        flash('Patient not found.')
        return redirect(url_for('patient_login'))
        
    visits = Visit.get_visits_for_patient(patient_id)
    
    return render_template('patient_visits.html', 
                          patient=patient,
                          visits=visits)

# Add this diagnostic route to help debug data issues

@app.route('/debug_patient/<string:id>')
@login_required
def debug_patient(id):
    """Debug route to inspect patient data"""
    patient = Patient.get_by_id(id)
    if not patient:
        return {"error": "Patient not found"}, 404
    
    # Convert patient to dictionary for inspection
    patient_dict = {}
    for key, value in patient.__dict__.items():
        if not key.startswith('_'):
            patient_dict[key] = f"{value} (type: {type(value).__name__})"
    
    return patient_dict

# Add this route to handle patient claiming

@app.route('/patient/<string:id>/claim')
@login_required
def claim_patient(id):
    try:
        patient = Patient.get_by_id(id)
        
        # Check if patient exists and currently doesn't have a doctor
        if not patient:
            flash('Patient not found.', 'error')
            return redirect(url_for('index'))
            
        # Assign patient to the current doctor
        patient.doctor_id = current_user.id
        patient.last_updated = datetime.utcnow().isoformat()
        patient.save()
        
        flash(f'You have successfully claimed {patient.first_name} {patient.last_name} as your patient.', 'success')
        return redirect(url_for('view_patient', id=patient.id))
    except Exception as e:
        logger.error(f"Error claiming patient: {str(e)}")
        flash('Error claiming patient', 'error')
        return redirect(url_for('index'))

@app.route('/debug/search_patients')
@login_required
def debug_search_patients():
    """Debug route to examine patient search results"""
    # Get query parameters
    search_query = request.args.get('search', '')
    filter_source = request.args.get('filter', 'all')
    
    # Get results with detailed info
    results = {}
    
    # My patients
    if filter_source in ['my', 'all']:
        my_patients = Patient.filter_by(doctor_id=current_user.id)
        results['my_patients'] = [{
            'id': p.id,
            'name': f"{p.first_name} {p.last_name}",
            'doctor_id': p.doctor_id,
            'matches_search': search_query.lower() in (p.first_name or '').lower() or 
                             search_query.lower() in (p.last_name or '').lower()
        } for p in my_patients]
    
    # Self-registered patients
    if filter_source in ['self', 'all']:
        self_patients = Patient.filter_by(doctor_id=None)
        results['self_registered'] = [{
            'id': p.id,
            'name': f"{p.first_name} {p.last_name}",
            'doctor_id': p.doctor_id,
            'matches_search': search_query.lower() in (p.first_name or '').lower() or 
                             search_query.lower() in (p.last_name or '').lower()
        } for p in self_patients]
    
    results['search_query'] = search_query
    results['filter'] = filter_source
    
    return results

# Add these route handlers for the navigation menu

@app.route('/my-visits')
@login_required
def my_visits():
    """Show all visits created by the current doctor across all patients"""
    visits_by_patient = {}
    
    # Query visits collection for visits where doctor_id = current_user.id
    visits_query = db.collection(Visit.collection_name).where('doctor_id', '==', current_user.id).order_by('date', direction=firestore.Query.DESCENDING).stream()
    
    for doc in visits_query:
        visit_data = doc.to_dict()
        visit_data['id'] = doc.id
        
        # Get patient ID
        patient_id = visit_data.get('patient_id')
        
        # If this is the first visit for this patient, get patient info
        if patient_id not in visits_by_patient:
            patient = Patient.get_by_id(patient_id)
            
            if patient:
                # Initialize patient info
                visits_by_patient[patient_id] = {
                    'first_name': patient.first_name,
                    'last_name': patient.last_name,
                    'is_my_patient': patient.doctor_id == current_user.id,
                    'doctor_name': patient.doctor_name if hasattr(patient, 'doctor_name') else "Unknown",
                    'visits': []
                }
            else:
                # Handle case where patient might have been deleted
                visits_by_patient[patient_id] = {
                    'first_name': "Unknown",
                    'last_name': "Patient",
                    'is_my_patient': False,
                    'doctor_name': "Unknown",
                    'visits': []
                }
        
        # Create visit object and add to patient's visits
        visit = Visit.from_dict(visit_data)
        visit.convert_dates()
        visits_by_patient[patient_id]['visits'].append(visit)
    
    # Sort each patient's visits by date (newest first)
    for patient_id in visits_by_patient:
        visits_by_patient[patient_id]['visits'].sort(key=lambda v: v.date, reverse=True)
    
    return render_template('doctor_visits.html', visits_by_patient=visits_by_patient)

@app.route('/alerts')
@login_required
def alerts():
    """Show alerts for the current doctor"""
    # For demonstration, we'll create some example alerts
    # In a real application, these would come from a database
    alerts = [
        {
            'id': '1',
            'type': 'critical',
            'message': 'Patient John Doe has missed their follow-up appointment',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'read': False
        },
        {
            'id': '2',
            'type': 'warning',
            'message': 'Lab results for patient Sarah Smith need review',
            'timestamp': (datetime.now() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M'),
            'read': False
        },
        {
            'id': '3',
            'type': 'info',
            'message': 'New treatment guidelines available for diabetes management',
            'timestamp': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M'),
            'read': False
        }
    ]
    
    return render_template('alerts.html', alerts=alerts)

# Initialize the database with an admin user
if __name__ == '__main__':
    # Initialize admin user
    try:
        # Check if admin user exists
        admin = Doctor.query_by_username('admin')
        if not admin:
            # Create admin user
            admin = Doctor(username='admin')
            admin.set_password('password')
            admin.save()
            logger.info("Admin user created successfully")
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        
    app.run(debug=True)