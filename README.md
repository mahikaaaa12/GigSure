# 🛡️ GigSure — Parametric Income Protection Platform for Gig Workers

GigSure is an AI-powered parametric insurance platform designed to protect gig workers (delivery partners, ride-sharing drivers, etc.) from instant income loss caused by real-world disruptions (such as extreme weather, city shutdowns, or platform outages).

Unlike traditional claim-based insurance systems, GigSure uses live environmental telemetry and machine learning risk classification to automatically verify disruptions and trigger payouts.

---

## 📖 Table of Contents
1. [Project Overview](#-project-overview)
2. [Features](#-features)
3. [Tech Stack](#-tech-stack)
4. [Folder Structure](#-folder-structure)
5. [Installation & Setup](#-installation--setup)
6. [Environment Variables](#-environment-variables)
7. [Database Design](#-database-design)
8. [MongoDB Migration Guide](#-mongodb-migration-guide)
9. [MongoDB Atlas Setup](#-mongodb-atlas-setup)
10. [Render Deployment Guide](#-render-deployment-guide)
11. [API Documentation](#-api-documentation)
12. [Future Improvements](#-future-improvements)

---

## 🌍 Project Overview
Gig workers earn on a daily and highly variable basis. Any disruption (such as heavy rainfall, waterlogging, severe storms, extreme heat, or app server outages) halts their ability to work, resulting in an immediate loss of income. 

Traditional insurance products are not designed for gig work. They require manual filing, extensive documentation (like billing slips), and manual review, which can take weeks to resolve.

**GigSure** addresses this problem using **Parametric Insurance**:
* **Automated Telemetry**: A background weather monitor tracks local climate conditions.
* **Risk Probability Classification**: A Random Forest classifier estimates disruption probabilities.
* **Parametric Rules**: Payouts are triggered automatically when predefined thresholds (e.g., rainfall > 5mm) are exceeded.
* **Rapid Approvals & Settlements**: Claims are processed and cleared in real-time.

---

## ✨ Features
* **Role-Based Portals**:
  * **Beneficiary Dashboard**: View active protection coverage, track regional weather conditions, file claims manually, and view payment status histories.
  * **Insurer Portal**: Configure policy thresholds, view system metrics and claims, trigger manual simulations, and review flagged claims.
* **Machine Learning Classification**: Features a Random Forest model trained on weather variables (rainfall, wind speed, temperature, humidity, WMO condition codes) to predict disruption probabilities.
* **Fraud Detection Engine**: A multi-factor check assessing claim frequencies, earnings anomalies (such as inflated declarations), time-based discrepancies, and weather correlation.
* **Generative AI Assistant**: Server-side proxy integrating Anthropic's Claude to help beneficiaries understand automatic claim triggers and suggest precautions.
* **Background Monitoring Agent**: Management task that polls WeatherAPI.com, processes active policies, and triggers payouts automatically.

---

## 🛠️ Tech Stack
* **Frontend**: HTML5, Vanilla CSS, Vanilla JavaScript (DOM manipulation, AJAX via `fetch`, LocalStorage integration)
* **Backend**: Django 5.0.7 (configured via `gigsure_project`), running on WSGI (`gunicorn`)
* **Database**: SQLite (local development), MongoDB Atlas / MongoEngine (production target)
* **AI/ML**: `scikit-learn 1.5.0` (Random Forest, StandardScaler), `anthropic` (Claude 3.5 Sonnet)

---

## 📂 Folder Structure

```txt
GigSure/
├── manage.py                    # Django CLI manager
├── requirements.txt             # Pinned project dependencies
├── runtime.txt                  # Python runtime version
├── build.sh                     # Build script for Render Cloud
├── render.yaml                  # Render infrastructure-as-code
├── db.sqlite3                   # Local dev SQLite database
├── gigsure_project/             # Settings and WSGI configuration
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py              # Main configurations & keys
│   ├── urls.py                  # Main router routing to core app
│   └── wsgi.py
└── core/                        # Primary Parametric Application
    ├── admin.py                 # Django admin interfaces
    ├── apps.py                  # Application declarations
    ├── models.py                # SQL models (Policy, WeatherLog, Claim, Notification)
    ├── views.py                 # Controller endpoint logic
    ├── urls.py                  # Application API endpoints
    ├── ml_model.py              # Random Forest training and prediction services
    ├── weather_monitor.py       # Parametric monitor background routines
    ├── templates/               # App views (claim, index, insurer_dashboard, etc.)
    ├── static/                  # Style spreadsheets (claim, login, style, weather)
    ├── management/
    │   └── commands/
    │       └── run_weather_monitor.py # Django command wrapper for monitor
    └── utils/
        └── weather.py           # Weather forecast utilities
```

---

## ⚙️ Installation & Setup

### Prerequisites
* Python 3.12.x installed locally.
* Git installed locally.

### Local Setup Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/GigSure.git
   cd GigSure
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root folder. See the [Environment Variables](#-environment-variables) section below for template details.

5. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Start the development server**:
   ```bash
   python manage.py runserver
   ```
   Open `http://127.0.0.1:8000/` in your browser.

7. **Run the background monitor task (in another terminal)**:
   * **Single Pass (Test)**:
     ```bash
     python manage.py run_weather_monitor
     ```
   * **Continuous Monitoring Loop (5 min interval)**:
     ```bash
     python manage.py run_weather_monitor --loop
     ```

---

## 🔑 Environment Variables
Create a `.env` file in the root directory:

```env
# General Settings
DEBUG=True
SECRET_KEY=django-insecure-dev-only-change-this-in-production
ALLOWED_HOSTS=127.0.0.1,localhost

# Database Connections
DATABASE_URL=sqlite:///db.sqlite3
# For MongoDB Atlas in production:
# MONGODB_URI=mongodb+srv://gigsure_app:SecurePassword@cluster.mongodb.net/gigsure

# Third-Party Integrations
WEATHER_API_KEY=d76f6b52979d4579b5543501260204
ANTHROPIC_API_KEY=sk-ant-api-key-here
```

---

## 🗄️ Database Design

### SQL Entity Relationships (Current SQLite Schema)
```
+---------------+        +---------------+
|     User      |1      1|    Policy     |
|---------------|------->|---------------|
| id (PK)       |        | id (PK)       |
| username      |        | name          |
| password      |        | premium       |
+---------------+        | thresholds... |
    | 1                  +---------------+
    |                           | 1
    | claimant                  |
    v *                         v *
+----------------------------------------+
|                 Claim                  |
|----------------------------------------|
| id (PK)                                |
| claim_id (Unique)                      |
| status ('pending', 'approved'...)      |
| payout_amount                          |
| weather_log_id (FK)                    |
+----------------------------------------+
    | *
    v 1
+----------------------------------------+
|               WeatherLog               |
|----------------------------------------|
| id (PK)                                |
| city                                   |
| rainfall_mm, temperature_c, wind_speed |
| recorded_at                            |
+----------------------------------------+
```

---

## 🔄 MongoDB Migration Guide

To scale GigSure to handle large amounts of telemetry data, we recommend migrating to MongoDB Atlas.

### Collection Mapping Model
1. **`users` Collection**: Stores user credentials, roles, and profiles.
2. **`policies` Collection**: Stores policy parameters. Beneficiaries are stored as a nested array of ObjectIds (`beneficiaries: [ObjectId]`) to eliminate join tables.
3. **`claims` Collection**: Embeds weather telemetry inside the claim document under `weather_evidence`. This decouples the claim history from the weather log table, preventing queries from breaking if logs are deleted.
4. **`weather_logs` Collection**: A time-series collection storing historical weather updates.

### MongoEngine Document Models
Create a new file `core/mongo_models.py`:

```python
from mongoengine import Document, StringField, EmailField, ReferenceField, ListField, DecimalField, FloatField, BooleanField, DateTimeField, EmbeddedDocument, EmbeddedDocumentField
import datetime

class UserDocument(Document):
    meta = {'collection': 'users'}
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    role = StringField(default='beneficiary')

class PolicyDocument(Document):
    meta = {'collection': 'policies'}
    name = StringField(required=True)
    max_payout_per_claim = DecimalField(precision=2, default=1200.00)
    payout_percentage = FloatField(default=80.00)
    rainfall_threshold_mm = FloatField(default=5.0)

class WeatherEvidence(EmbeddedDocument):
    temperature_c = FloatField()
    rainfall_mm = FloatField()
    wind_speed_kph = FloatField()

class ClaimDocument(Document):
    meta = {'collection': 'claims'}
    claim_id = StringField(required=True, unique=True)
    claimant_id = ReferenceField(UserDocument, required=True)
    policy_id = ReferenceField(PolicyDocument)
    status = StringField(default='pending')
    weather_evidence = EmbeddedDocumentField(WeatherEvidence)
```

---

## ☁️ MongoDB Atlas Setup
1. Sign up for a free account at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Create an `M0` Free Tier Cluster in your preferred region.
3. Under **Database Access**, create a user (e.g. `gigsure_app`) with **Read and Write** permissions.
4. Under **Network Access**, add IP `0.0.0.0/0` (required for Render's dynamic IP environment).
5. Copy the connection string:
   `mongodb+srv://gigsure_app:<password>@cluster.mongodb.net/gigsure?retryWrites=true&w=majority`
6. Set the `MONGODB_URI` environment variable to this connection string in your `.env` file.

---

## 🚀 Render Deployment Guide

Follow these steps to deploy the application on Render:

1. **Add `render.yaml` to the root directory**:
   ```yaml
   services:
     - type: web
       name: gigsure-app
       env: python
       buildCommand: "./build.sh"
       startCommand: "gunicorn gigsure_project.wsgi:application --bind 0.0.0.0:$PORT"
       envVars:
         - key: PYTHON_VERSION
           value: 3.12.10
         - key: DEBUG
           value: "False"
         - key: SECRET_KEY
           sync: false
         - key: MONGODB_URI
           sync: false
   ```

2. **Commit and push changes**:
   ```bash
   git add .
   git commit -m "Configure deployment"
   git push origin main
   ```

3. **Deploy on Render**:
   * Go to the [Render Dashboard](https://dashboard.render.com).
   * Click **New +** and select **Blueprint**.
   * Connect your GitHub repository. Render will automatically configure the services defined in `render.yaml`.
   * Fill in the values for the environment variables (`SECRET_KEY`, `MONGODB_URI`, `WEATHER_API_KEY`, `ANTHROPIC_API_KEY`).

---

## 📡 API Documentation

### 🔓 Authentication Endpoints

#### 1. Sign Up
* **URL**: `/api/signup/`
* **Method**: `POST`
* **Payload**:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword",
    "first_name": "John",
    "last_name": "Doe",
    "role": "beneficiary",
    "company": "Swiggy"
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "success": true,
    "user": { "id": 1, "email": "user@example.com", "role": "beneficiary" }
  }
  ```

#### 2. Login
* **URL**: `/api/login/`
* **Method**: `POST`
* **Payload**:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword",
    "role": "beneficiary"
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "success": true,
    "user": { "id": 1, "email": "user@example.com", "role": "beneficiary" }
  }
  ```

---

### 🛡️ Claim Endpoints

#### 1. Submit Claim
* **URL**: `/api/claims/submit/`
* **Method**: `POST`
* **Payload**:
  ```json
  {
    "disruption_type": "heavy_rain",
    "city": "Vadodara",
    "platform": "Zomato",
    "expected_earnings": 1200,
    "actual_earnings": 200,
    "description": "Heavy rainfall stopped delivery operations from 3PM to 7PM."
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "success": true,
    "fraud_score": 12,
    "decision": "approved",
    "reasoning_text": "Fraud score 12/100 - claim cleared.",
    "payment_status": "completed",
    "payout": 800.00
  }
  ```

#### 2. Get User Claims
* **URL**: `/api/claims/mine/`
* **Method**: `GET`
* **Response (200 OK)**:
  ```json
  {
    "claims": [
      {
        "claim_id": "GS-2026-894103",
        "status": "approved",
        "payout": 800.00,
        "created_at": "2026-06-18T14:31:00Z"
      }
  ]
  }
  ```

---

## 🔮 Future Improvements
* **Real-time SMS Integration**: Use Twilio to notify beneficiaries via SMS about auto-triggered claims and payout statuses.
* **Integrate Live GPS Geofencing**: Verify that the claimant was in the disruption zone during the incident using mobile GPS logs.
* **Support Multiple Gig Platforms**: Import income logs directly from Uber, Ola, Swiggy, and Zomato APIs.
* **Introduce Automated UPI Payouts**: Connect the backend to payment gateways (such as Razorpay or Cashfree) to settle claims within 60 seconds of approval.
