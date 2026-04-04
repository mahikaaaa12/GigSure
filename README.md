# 🛡️ GigSure — AI-Powered Income Protection for Gig Workers

GigSure is an AI-driven parametric insurance platform designed to protect gig workers (delivery partners, drivers, etc.) from income loss caused by real-world disruptions like weather, shutdowns, and platform outages.

---

## 🚀 Problem Statement

Gig workers earn on a **daily and highly variable basis**. Any disruption such as heavy rainfall, traffic, or platform outages can lead to **instant income loss**.

Traditional insurance systems:

* Require manual claims
* Take days to process
* Are not designed for dynamic gig work

GigSure solves this by introducing **real-time, automated income protection**.

> Modern gig insurance leverages AI and real-time data to enable instant claim settlement and flexible coverage models. ([Tata Consultancy Services][1])

---

## 💡 Solution Overview

GigSure uses:

* 🌦️ Weather data
* 📍 GPS & activity signals
* 🤖 AI/ML risk models

to:

* Detect disruptions automatically
* Calculate expected income loss
* Trigger payouts instantly

This follows a **parametric insurance model** where payouts are triggered by conditions instead of manual claims.

---

## 🧱 System Architecture

### 👤 Beneficiary (Gig Worker)

* Registers and logs in
* Views dashboard
* Files claims manually (Claim Module)
* Receives automated claim suggestions

### 🏛️ Insurer

* Monitors claims in real-time
* Approves/rejects claims
* Configures policies
* Tracks payouts and disruptions

---

## ✨ Recent Features & Updates

### ✅ 1. Role-Based Authentication

* Users can log in as:

  * Beneficiary
  * Insurer
* Automatic redirection based on role

---

### ✅ 2. Beneficiary Dashboard

* Interactive UI with:

  * Claim Request Module
  * Weather Forecast Module
* Role-based access (claim module locked for insurers)

---

### ✅ 3. Claim Request Flow

* Dedicated `claim.html` page
* Users can:

  * Select disruption type
  * Enter date, city, and details
* Submission creates a claim entry

---

### ✅ 4. Insurer Dashboard

* Fully functional multi-tab dashboard:

  * 📊 Overview (stats + analytics)
  * 📋 Claims Management
  * 🗂️ Policies
  * 🌦️ Weather Monitor
  * 🤖 ML Model Insights
  * 💬 AI Assistant

---

### ✅ 5. Claim Synchronization System

* Claims submitted by beneficiaries:

  * Appear in insurer dashboard
  * Update:

    * Total claims
    * Pending claims
    * Claims table dynamically

---

### ✅ 6. Policy Management

* Preloaded example policies:

  * Monsoon Basic Cover
  * High Risk Weather Cover
  * Premium Gig Protection
* Configurable thresholds:

  * Rainfall
  * Wind speed
  * ML risk score

---

### ✅ 7. Weather Integration

* Weather module connected to dashboard
* "Run Weather Check" button:

  * Triggers disruption logic
  * Can simulate auto-claims

---

### ✅ 8. ML Risk Scoring System

* Predicts claim probability based on:

  * Rainfall
  * Temperature
  * Wind
  * Humidity
* Helps automate claim approval decisions

---

### ✅ 9. Improved UI/UX

* Modular card-based layout
* Role-based UI locking
* Dashboard-style insurer interface
* Interactive components and animations

---

## 🛠️ Tech Stack

### Frontend

* HTML, CSS, JavaScript
* Dynamic UI with localStorage

### Backend

* Django (Python)
* REST-style endpoints (extendable)

### AI/ML (Conceptual / Prototype)

* Random Forest model
* Risk scoring logic

---

## 🔄 Application Flow

1. User lands on login page
2. Logs in as Beneficiary or Insurer
3. Redirect based on role:

   * Beneficiary → Dashboard
   * Insurer → Insurer Dashboard
4. Claims created → synced → monitored
5. Insurer reviews or auto-approves

---

## 📂 Project Structure

```
GigSure/
│
├── templates/
│   ├── login.html
│   ├── index.html
│   ├── claim.html
│   ├── insurer_dashboard.html
│   └── weather.html
│
├── core/
│   ├── views.py
│   ├── urls.py
│   └── ml_model.py
│
├── static/
│   └── style.css
│
└── manage.py
```

---

## ⚙️ How to Run

```bash
python manage.py runserver
```

Open:

```
http://127.0.0.1:8000/
```

---

## 🔮 Future Improvements

* Real API integration (weather + maps)
* Database-backed claims (replace localStorage)
* Real-time notifications
* Fraud detection using ML
* Mobile app version

---

## 🌍 Impact

GigSure aims to:

* Provide financial stability to gig workers
* Reduce income uncertainty
* Build trust between workers and insurers

The gig economy lacks structured safety nets, making such solutions critical for financial inclusion and protection. ([Forbes India][2])

---

## 👩‍💻 Developed By

Built as part of an innovation / hackathon project focused on:

* AI in insurance
* Real-time systems
* Social impact through technology

---

## ⭐ Final Note

GigSure is not just an insurance product —
it’s a step toward **fair, instant, and intelligent income protection** for the modern workforce.

[1]: https://www.tcs.com/insights/blogs/ai-gig-insurance-worker-benefits?utm_source=chatgpt.com "AI and Its Impact on Gig Economy Insurance"
[2]: https://www.forbesindia.com/article/upfront/brand-connect/from-daily-earnings-to-long-term-security-platforms-drive-financial-protection-for-gig-workers/2992748/1?utm_source=chatgpt.com "From daily earnings to long-term security: Platforms drive ..."
