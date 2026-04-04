"""
GigSure ML Module
=================
- Trains a Random Forest classifier on synthetic weather + claim data
- Saves the model to disk (model/claim_predictor.pkl)
- Exposes predict_claim_probability(weather_dict) for use in views/tasks

Run this file directly to train / retrain the model:
    python core/ml_model.py
"""

import os
import json
import pickle
import numpy as np

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR  = os.path.join(BASE_DIR, 'ml_model')
MODEL_PATH = os.path.join(MODEL_DIR, 'claim_predictor.pkl')
META_PATH  = os.path.join(MODEL_DIR, 'model_meta.json')

os.makedirs(MODEL_DIR, exist_ok=True)


# ── Feature engineering ──────────────────────────────────────────────────────

FEATURE_NAMES = [
    'rainfall_mm',
    'wind_speed_kph',
    'temperature_c',
    'humidity_pct',
    'condition_code',      # WMO / WeatherAPI code
    'hour_of_day',         # 0–23
    'is_weekend',          # 0 or 1
]

def weather_to_features(weather: dict) -> np.ndarray:
    """
    Convert a weather dictionary (from WeatherLog or API response) into
    a numpy feature vector ready for the ML model.

    Accepted keys (all optional, defaults used if missing):
        rainfall_mm, wind_speed_kph, temperature_c, humidity_pct,
        condition_code, recorded_at (datetime or ISO string)
    """
    from datetime import datetime

    recorded_at = weather.get('recorded_at') or datetime.now()
    if isinstance(recorded_at, str):
        from dateutil import parser as dtp
        recorded_at = dtp.parse(recorded_at)

    features = [
        float(weather.get('rainfall_mm',    0.0)),
        float(weather.get('wind_speed_kph', 0.0)),
        float(weather.get('temperature_c',  28.0)),
        float(weather.get('humidity_pct',   60.0)),
        float(weather.get('condition_code', 1000)),
        float(recorded_at.hour),
        float(recorded_at.weekday() >= 5),  # Saturday=5, Sunday=6
    ]
    return np.array([features])


# ── Synthetic training data ───────────────────────────────────────────────────

def generate_training_data(n: int = 3000):
    """
    Generate synthetic labeled training data.
    Label = 1  →  claim likely (disruption occurred)
    Label = 0  →  no claim expected
    """
    rng = np.random.default_rng(42)

    # --- Disruption scenarios (label = 1, ~40% of data) ---
    n_disrupt = int(n * 0.40)
    disrupt = np.column_stack([
        rng.uniform(5, 60, n_disrupt),       # rainfall_mm (heavy)
        rng.uniform(35, 90, n_disrupt),      # wind_speed_kph (high)
        rng.choice([rng.uniform(1,10, n_disrupt),
                    rng.uniform(42,50, n_disrupt)]),  # extreme temps
        rng.uniform(70, 100, n_disrupt),     # humidity (high)
        rng.choice([61, 63, 65, 67, 80, 95], n_disrupt),  # rain/storm codes
        rng.integers(0, 24, n_disrupt),      # hour
        rng.integers(0, 2, n_disrupt),       # weekend
    ])
    labels_disrupt = np.ones(n_disrupt)

    # --- Normal scenarios (label = 0, ~60% of data) ---
    n_normal = n - n_disrupt
    normal = np.column_stack([
        rng.uniform(0, 2,  n_normal),        # light / no rain
        rng.uniform(0, 25, n_normal),        # low wind
        rng.uniform(18, 38, n_normal),       # comfortable temps
        rng.uniform(30, 70, n_normal),       # moderate humidity
        rng.choice([1000, 1003, 1006, 1030], n_normal),  # clear / cloudy
        rng.integers(0, 24, n_normal),
        rng.integers(0, 2, n_normal),
    ])
    labels_normal = np.zeros(n_normal)

    X = np.vstack([disrupt, normal]).astype(float)
    y = np.concatenate([labels_disrupt, labels_normal])

    # Shuffle
    idx = rng.permutation(len(y))
    return X[idx], y[idx]


# ── Train & save ─────────────────────────────────────────────────────────────

def train_and_save():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    from sklearn.preprocessing import StandardScaler
    import sklearn

    print("🤖 GigSure ML — Training claim predictor...")

    X, y = generate_training_data(3000)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc  = scaler.transform(X_test)

    # Train Random Forest
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train_sc, y_train)

    # Evaluate
    y_pred = clf.predict(X_test_sc)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n✅ Accuracy: {acc:.2%}")
    print(classification_report(y_test, y_pred, target_names=['No Claim', 'Claim']))

    # Feature importances
    importances = dict(zip(FEATURE_NAMES, clf.feature_importances_.tolist()))
    print("\n📊 Feature importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1]):
        bar = '█' * int(imp * 50)
        print(f"  {feat:<25} {bar} {imp:.3f}")

    # Save model bundle
    bundle = {'clf': clf, 'scaler': scaler}
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(bundle, f)

    # Save metadata
    meta = {
        'accuracy': round(acc, 4),
        'feature_names': FEATURE_NAMES,
        'feature_importances': importances,
        'sklearn_version': sklearn.__version__,
        'trained_at': str(np.datetime64('today')),
        'n_samples': len(X),
    }
    with open(META_PATH, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"\n💾 Model saved → {MODEL_PATH}")
    print(f"📋 Metadata   → {META_PATH}")
    return clf, scaler


# ── Load (lazy, cached at module level) ──────────────────────────────────────

_bundle = None

def _load_bundle():
    global _bundle
    if _bundle is not None:
        return _bundle
    if not os.path.exists(MODEL_PATH):
        print("⚠️  ML model not found. Training now...")
        train_and_save()
    with open(MODEL_PATH, 'rb') as f:
        _bundle = pickle.load(f)
    return _bundle


# ── Public API ───────────────────────────────────────────────────────────────

def predict_claim_probability(weather: dict) -> float:
    """
    Given a weather dictionary, return a float in [0, 1] representing
    the predicted probability that a claim will be filed.

    Usage:
        from core.ml_model import predict_claim_probability
        score = predict_claim_probability({
            'rainfall_mm': 12.4,
            'wind_speed_kph': 55,
            'temperature_c': 32,
            'humidity_pct': 88,
            'condition_code': 65,
        })
        # score -> e.g. 0.87
    """
    try:
        bundle = _load_bundle()
        clf    = bundle['clf']
        scaler = bundle['scaler']
        X = weather_to_features(weather)
        X_sc = scaler.transform(X)
        prob = clf.predict_proba(X_sc)[0][1]  # probability of class=1 (claim)
        return round(float(prob), 4)
    except Exception as e:
        print(f"⚠️  ML prediction failed: {e}")
        # Fallback: rule-based heuristic
        return _rule_based_score(weather)


def _rule_based_score(weather: dict) -> float:
    """Fallback rule-based score when ML model unavailable."""
    score = 0.0
    rain  = float(weather.get('rainfall_mm', 0))
    wind  = float(weather.get('wind_speed_kph', 0))
    temp  = float(weather.get('temperature_c', 28))
    humid = float(weather.get('humidity_pct', 60))

    if rain > 15:   score += 0.40
    elif rain > 5:  score += 0.25
    elif rain > 1:  score += 0.10

    if wind > 60:   score += 0.25
    elif wind > 40: score += 0.15
    elif wind > 25: score += 0.05

    if temp > 44 or temp < 6:  score += 0.20
    if humid > 90:              score += 0.10

    return min(round(score, 4), 1.0)


def get_model_metadata() -> dict:
    """Return model training metadata (for the insurer dashboard)."""
    if os.path.exists(META_PATH):
        with open(META_PATH) as f:
            return json.load(f)
    return {}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    train_and_save()
    # Quick smoke test
    test_cases = [
        {'rainfall_mm': 20, 'wind_speed_kph': 60, 'temperature_c': 32, 'humidity_pct': 90, 'condition_code': 65},
        {'rainfall_mm': 0,  'wind_speed_kph': 10, 'temperature_c': 28, 'humidity_pct': 55, 'condition_code': 1000},
    ]
    for tc in test_cases:
        prob = predict_claim_probability(tc)
        print(f"\nInput : {tc}")
        print(f"Score : {prob:.0%} claim probability")