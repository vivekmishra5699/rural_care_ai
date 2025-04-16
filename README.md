# 🏥 DocAI Assistant

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-brightgreen.svg)
![Flask](https://img.shields.io/badge/flask-2.3.0-red.svg)
![Firebase](https://img.shields.io/badge/firebase-firestore-orange.svg)

## Overview

DocAI Assistant is a powerful medical practice management system with integrated AI capabilities. It helps doctors manage patients, track visits, and get AI-assisted diagnosis and treatment recommendations using Google's Gemini AI.

![DocAI Dashboard](https://github.com/user-attachments/assets/37a32a1f-cef7-4f8a-9061-2bcc61d6fb13)

## ✨ Key Features

- **Dual User System**: Separate portals for doctors and patients
- **Patient Management**: Track patient records, medical history, and visits
- **AI-Powered Assistance**: Integrated with Google's Gemini AI for diagnostic suggestions
- **Visit Tracking**: Complete workflow from initial symptoms to diagnosis and treatment
- **Search & Filter**: Advanced patient search and filtering capabilities
- **Cloud Database**: Firebase Firestore for reliable data storage

## 🛠️ Tech Stack

- **Backend**: Flask (Python)
- **Database**: Firebase Firestore
- **Authentication**: Flask-Login
- **AI Integration**: Google Generative AI (Gemini 1.5 Pro)
- **Frontend**: HTML, CSS, JavaScript
- **Environment**: dotenv for configuration

## 📋 Installation

### Prerequisites

- Python 3.9+
- Firebase Project
- Gemini API Key

### Setup Steps

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/docai-assistant.git
cd docai-assistant
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Create a `.env` file with your credentials**

```
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=your_secret_key_here
FIREBASE_PROJECT_ID=your_firebase_project_id
```

5. **Configure Firebase**

Set up your Firebase configuration in `firebase_config.py`:

```python
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate('path/to/your/firebase-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()
```

6. **Run the application**

```bash
python app.py
```

Your app should now be running at http://localhost:5000

## 💻 Usage

### Doctor Portal

1. Register as a doctor or use the default admin account:
   - Username: `admin`
   - Password: `password`

2. Add patients to your practice

3. Record visits and get AI-assisted diagnosis suggestions

4. Review patient history and manage medical records

### Patient Portal

1. Patients can login with credentials provided by their doctor

2. View personal medical history, visit reports, and treatment plans

3. Update personal information and contact details

## 📝 Project Structure

```
docai-assistant/
├── app.py              # Main application file
├── firebase_config.py  # Firebase configuration
├── models.py           # Database models
├── requirements.txt    # Python dependencies
├── static/             # Static assets (CSS, JS, images)
├── templates/          # HTML templates
└── README.md           # This file
```

## 🔒 Security Considerations

- All passwords are hashed before storage
- User sessions are secured with Flask-Login
- Firebase Firestore security rules should be configured
- This application is for demonstration purposes and needs additional security hardening before production use

## 📊 Screenshots

<div style="display: flex; flex-wrap: wrap; gap: 15px; justify-content: center;">
  <img src="https://via.placeholder.com/400x250?text=Doctor+Dashboard" alt="Doctor Dashboard" width="400">
  <img src="https://via.placeholder.com/400x250?text=Patient+Portal" alt="Patient Portal" width="400">
  <img src="https://via.placeholder.com/400x250?text=AI+Analysis" alt="AI Analysis" width="400">
  <img src="https://via.placeholder.com/400x250?text=Patient+Records" alt="Patient Records" width="400">
</div>

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgements

- Google Generative AI for the Gemini API
- Flask and its extension authors
- Firebase team for Firestore
- All open-source contributors

---

Developed with ❤️ by [Vivek,Nikhil]
