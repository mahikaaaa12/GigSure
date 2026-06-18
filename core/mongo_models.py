from mongoengine import Document, EmbeddedDocument, StringField, EmailField, ReferenceField, ListField, DecimalField, FloatField, BooleanField, DateTimeField, EmbeddedDocumentField, IntField
import datetime

class UserDocument(Document):
    meta = {
        'collection': 'users',
        'indexes': ['email']
    }
    django_id = IntField(unique=True) # Maps back to Django User ID for relational sync
    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    first_name = StringField(max_length=100)
    last_name = StringField(max_length=100)
    role = StringField(default='beneficiary', choices=['beneficiary', 'insurer'])
    company = StringField(blank=True, null=True)
    city = StringField(default='Vadodara')
    date_joined = DateTimeField(default=datetime.datetime.utcnow)

class PolicyDocument(Document):
    meta = {
        'collection': 'policies',
        'indexes': ['insurer_id']
    }
    django_id = IntField(unique=True, sparse=True)
    name = StringField(max_length=200, required=True)
    description = StringField()
    insurer_id = ReferenceField(UserDocument, required=True)
    beneficiaries = ListField(ReferenceField(UserDocument))
    max_payout_per_claim = DecimalField(precision=2, default=1200.00)
    payout_percentage = FloatField(default=80.00)
    max_claims_per_month = IntField(default=5)
    monthly_premium = DecimalField(precision=2, default=129.00)
    rainfall_threshold_mm = FloatField(default=5.0)
    wind_speed_threshold_kph = FloatField(default=50.0)
    temperature_min_threshold_c = FloatField(default=5.0)
    temperature_max_threshold_c = FloatField(default=45.0)
    ml_claim_probability_threshold = FloatField(default=0.65)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)

class WeatherLogDocument(Document):
    meta = {
        'collection': 'weather_logs',
        'indexes': [('-city', '-recorded_at')]
    }
    city = StringField(max_length=100, required=True)
    latitude = FloatField(null=True)
    longitude = FloatField(null=True)
    temperature_c = FloatField(required=True)
    feels_like_c = FloatField(null=True)
    humidity_pct = FloatField(null=True)
    rainfall_mm = FloatField(default=0.0)
    wind_speed_kph = FloatField(default=0.0)
    condition_text = StringField(max_length=200)
    condition_code = IntField(default=1000)
    ml_risk_score = FloatField(null=True)
    is_disruption = BooleanField(default=False)
    recorded_at = DateTimeField(default=datetime.datetime.utcnow)

class WeatherEvidence(EmbeddedDocument):
    temperature_c = FloatField()
    humidity_pct = FloatField()
    rainfall_mm = FloatField()
    wind_speed_kph = FloatField()
    condition_text = StringField()

class ClaimDocument(Document):
    meta = {
        'collection': 'claims',
        'indexes': ['claim_id', '-claimant_id']
    }
    django_id = IntField(unique=True, sparse=True)
    claim_id = StringField(required=True, unique=True)
    claimant_id = ReferenceField(UserDocument, required=True)
    policy_id = ReferenceField(PolicyDocument, null=True)
    source = StringField(default='manual', choices=['manual', 'auto'])
    status = StringField(default='pending', choices=['pending', 'approved', 'rejected'])
    disruption_type = StringField(default='heavy_rain')
    city = StringField(max_length=100, default='Vadodara')
    platform = StringField(blank=True, null=True)
    incident_date = DateTimeField(required=True)
    incident_time = StringField(blank=True, null=True) # HH:MM
    expected_earnings = DecimalField(precision=2, default=0.00)
    actual_earnings = DecimalField(precision=2, default=0.00)
    estimated_loss = DecimalField(precision=2, default=0.00)
    payout_amount = DecimalField(precision=2, default=0.00)
    fraud_score = IntField(null=True)
    ai_decision_reason = StringField()
    reviewed_by = ReferenceField(UserDocument, null=True)
    review_note = StringField(blank=True)
    reviewed_at = DateTimeField(null=True)
    weather_evidence = EmbeddedDocumentField(WeatherEvidence)
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)
