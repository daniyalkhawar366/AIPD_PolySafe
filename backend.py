from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import shutil
import os
import re
import threading
import time
import uuid
import random
import secrets
import smtplib
from collections import Counter
from typing import Any
from zoneinfo import ZoneInfo
import stripe
from pydantic import BaseModel, EmailStr, Field
import bcrypt
from jose import JWTError, jwt
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson import ObjectId
from email.message import EmailMessage

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Import your existing logic
from ocr import process_prescription, extract_text, parse_drug_names
from utils import validate_drug, fetch_medicine_use_summary
from user_profile import add_medication, get_medications, delete_medication, clear_profile
from interaction import (
    check_safety_for_profile,
    build_safety_report,
    check_overdose_risks,
    check_double_dose_and_schedule_risks,
)

app = FastAPI()

# Auth + MongoDB config
MONGO_URI = os.getenv("MONGO_URI", "") or os.getenv("MONGODB_URI", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "polysafe")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-env")
JWT_ALGORITHM = "HS256"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "") or os.getenv("REACT_APP_GOOGLE_CLIENT_ID", "")
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))
_jwt_expire_env = os.getenv("JWT_EXPIRE_MINUTES", "") or os.getenv("JWT_EXPIRE", "")
if _jwt_expire_env.endswith("d") and _jwt_expire_env[:-1].isdigit():
    JWT_EXPIRE_MINUTES = int(_jwt_expire_env[:-1]) * 24 * 60
elif _jwt_expire_env.isdigit():
    JWT_EXPIRE_MINUTES = int(_jwt_expire_env)
else:
    JWT_EXPIRE_MINUTES = 10080
# Guardrail: prevent accidental very-short sessions from env misconfiguration.
JWT_EXPIRE_MINUTES = max(JWT_EXPIRE_MINUTES, 1440)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

AUTH_COOKIE_NAME = "polysafe_token"
FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
if os.getenv("FRONTEND_URL"):
    FRONTEND_ORIGINS.append(FRONTEND_URL)

mongo_client = None
users_collection = None
medications_collection = None
prescriptions_collection = None
share_links_collection = None
reminders_collection = None
usage_events_collection = None
sus_responses_collection = None
feedback_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        mongo_db = mongo_client[MONGO_DB_NAME]
        users_collection = mongo_db["users"]
        medications_collection = mongo_db["medications"]
        prescriptions_collection = mongo_db["prescriptions"]
        share_links_collection = mongo_db["share_links"]
        reminders_collection = mongo_db["reminders"]
        usage_events_collection = mongo_db["usage_events"]
        sus_responses_collection = mongo_db["sus_responses"]
        feedback_collection = mongo_db["feedback"]
        users_collection.create_index("email", unique=True)
        medications_collection.create_index([("user_id", 1), ("rxcui", 1)])
        medications_collection.create_index([("user_id", 1), ("drug_name", 1)])
        prescriptions_collection.create_index([("user_id", 1), ("date_added", -1)])
        share_links_collection.create_index([("token", 1)], unique=True)
        share_links_collection.create_index([("owner_user_id", 1), ("created_at", -1)])
        share_links_collection.create_index([("expires_at", 1)])
        reminders_collection.create_index([("user_id", 1), ("profile_id", 1)], unique=True)
        reminders_collection.create_index([("enabled", 1), ("next_send_at", 1)])
        usage_events_collection.create_index([("user_id", 1), ("event_name", 1), ("created_at", -1)])
        usage_events_collection.create_index([("event_name", 1), ("created_at", -1)])
        sus_responses_collection.create_index([("user_id", 1), ("created_at", -1)])
        feedback_collection.create_index([("user_id", 1), ("created_at", -1)])
    except PyMongoError:
        users_collection = None
        medications_collection = None
        prescriptions_collection = None
        share_links_collection = None
        reminders_collection = None
        usage_events_collection = None
        sus_responses_collection = None
        feedback_collection = None

# Enable CORS for React
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class DrugAction(BaseModel):
    user_id: str = Field(default="", max_length=128)
    drug_name: str = Field(min_length=2, max_length=200)
    rxcui: str = Field(default="N/A", max_length=50)
    source: str = Field(default="Manual Entry", max_length=80)
    dose: str = Field(default="", max_length=100)
    frequency: str = Field(default="", max_length=100)
    dose_mg: float = Field(default=0.0, ge=0.0, le=100000.0)
    frequency_per_day: float = Field(default=0.0, ge=0.0, le=24.0)
    prescription_file_name: str = Field(default="", max_length=255)


class PrescriptionAction(BaseModel):
    raw_text: str = Field(min_length=1, max_length=20000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uploaded_file_name: str = Field(default="", max_length=255)


class MedicationUpdateAction(BaseModel):
    drug_name: str = Field(min_length=2, max_length=200)
    source: str = Field(default="", max_length=80)
    dose: str = Field(default="", max_length=100)
    frequency: str = Field(default="", max_length=100)


class RegisterAction(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="patient", max_length=20)


class LoginAction(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleAuthAction(BaseModel):
    idToken: str = Field(min_length=20, max_length=4096)


class ForgotPasswordAction(BaseModel):
    email: EmailStr


class VerifyResetAction(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResetPasswordAction(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class UserProfileAction(BaseModel):
    patient_name: str = Field(default="", max_length=120)
    patient_email: str = Field(default="", max_length=120)
    age: int = Field(ge=0, le=120)
    sex_at_birth: str = Field(default="", max_length=40)
    gender_identity: str = Field(default="", max_length=60)
    weight_kg: float = Field(default=0.0, ge=0.0, le=400.0)
    height_cm: float = Field(default=0.0, ge=0.0, le=260.0)
    chronic_conditions: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    kidney_disease: bool = False
    liver_disease: bool = False
    smoking_status: str = Field(default="unknown", max_length=40)
    alcohol_use: str = Field(default="unknown", max_length=40)
    grapefruit_use: str = Field(default="unknown", max_length=40)
    dairy_use: str = Field(default="unknown", max_length=40)
    egfr: float = Field(default=0.0, ge=0.0, le=300.0)
    alt_u_l: float = Field(default=0.0, ge=0.0, le=5000.0)
    ast_u_l: float = Field(default=0.0, ge=0.0, le=5000.0)
    inr: float = Field(default=0.0, ge=0.0, le=20.0)
    glucose_mg_dl: float = Field(default=0.0, ge=0.0, le=2000.0)
    emergency_contact_name: str = Field(default="", max_length=120)
    emergency_contact_phone: str = Field(default="", max_length=40)
    emergency_notes: str = Field(default="", max_length=500)
    care_team_patients: list[dict[str, Any]] = Field(default_factory=list)
    privacy_consent: bool = False


class ProfileCreateAction(BaseModel):
    name: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=120)


class ShareLinkAction(BaseModel):
    purpose: str = Field(default="consultation", max_length=30)
    expires_hours: int = Field(default=24, ge=1, le=168)


class ReminderSettingsAction(BaseModel):
    enabled: bool = False
    recipient_email: str = Field(default="", max_length=120)
    reminder_time: str = Field(default="09:00", min_length=5, max_length=5)
    timezone: str = Field(default="UTC", max_length=80)
    notes: str = Field(default="", max_length=500)


class DeleteAccountAction(BaseModel):
    confirm_text: str = Field(min_length=6, max_length=12)
    confirm_email: EmailStr


class UsageEventAction(BaseModel):
    event_name: str = Field(min_length=2, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)
    client_ts: str = Field(default="")


class SusSubmissionAction(BaseModel):
    responses: list[int] = Field(min_length=5, max_length=5)
    context: str = Field(default="general", max_length=60)


class FeedbackSubmissionAction(BaseModel):
    useful: str = Field(default="", max_length=1000)
    confusing: str = Field(default="", max_length=1000)
    would_use_again: str = Field(default="", max_length=300)
    would_pay: str = Field(default="", max_length=300)
    top_quote: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)
    context: str = Field(default="in_app_prompt", max_length=60)


class AdminSeedLiveEvidenceAction(BaseModel):
    reseed_missing_only: bool = True


ALLOWED_ROLES = {"patient", "caregiver"}
ALLOWED_UPLOAD_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/pdf",
}
MAX_UPLOAD_FILE_BYTES = 10 * 1024 * 1024
DEFAULT_PROFILE_ID = "default"
PREMIUM_EMAIL_WHITELIST = {
    "daniyalkhawar3@gmail.com",
}
ADMIN_EMAIL_WHITELIST = {
    email.strip().lower()
    for email in (
        os.getenv("ADMIN_EMAILS", "").split(",")
        + ["haiderzia8@gmail.com"]
        + list(PREMIUM_EMAIL_WHITELIST)
    )
    if email.strip()
}

GENERIC_DUPLICATE_ALIASES = {
    "acetaminophen": {"acetaminophen", "paracetamol", "apap"},
    "ibuprofen": {"ibuprofen"},
    "aspirin": {"aspirin", "asa"},
    "naproxen": {"naproxen"},
    "diclofenac": {"diclofenac"},
    "metformin": {"metformin"},
    "amlodipine": {"amlodipine"},
    "atorvastatin": {"atorvastatin"},
    "lisinopril": {"lisinopril"},
    "losartan": {"losartan"},
    "simvastatin": {"simvastatin"},
}


def _default_profile() -> dict[str, Any]:
    return {
        "patient_name": "",
        "patient_email": "",
        "age": 0,
        "sex_at_birth": "",
        "gender_identity": "",
        "weight_kg": 0.0,
        "height_cm": 0.0,
        "chronic_conditions": [],
        "allergies": [],
        "kidney_disease": False,
        "liver_disease": False,
        "smoking_status": "unknown",
        "alcohol_use": "unknown",
        "grapefruit_use": "unknown",
        "dairy_use": "unknown",
        "egfr": 0.0,
        "alt_u_l": 0.0,
        "ast_u_l": 0.0,
        "inr": 0.0,
        "glucose_mg_dl": 0.0,
        "emergency_contact_name": "",
        "emergency_contact_phone": "",
        "emergency_notes": "",
        "care_team_patients": [],
    }


def _default_profile_entry(name: str = "Primary Profile") -> dict[str, Any]:
    return {
        "id": DEFAULT_PROFILE_ID,
        "name": str(name or "Primary Profile").strip()[:80] or "Primary Profile",
        "profile": _default_profile(),
        "profile_completed": False,
        "privacy_consent": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _user_is_premium(user_doc: dict[str, Any] | None) -> bool:
    email = str((user_doc or {}).get("email") or "").strip().lower()
    return bool((user_doc or {}).get("is_premium", False) or email in PREMIUM_EMAIL_WHITELIST)


def _normalize_profiles_state(user_doc: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], str, bool]:
    changed = False
    profiles = user_doc.get("profiles")

    if not isinstance(profiles, list) or len(profiles) == 0:
        entry = _default_profile_entry()
        entry["profile"] = user_doc.get("profile") or _default_profile()
        if not str(entry["profile"].get("patient_name") or "").strip():
            entry["profile"]["patient_name"] = str(user_doc.get("name") or "").strip()
            changed = True
        if not str(entry["profile"].get("patient_email") or "").strip():
            entry["profile"]["patient_email"] = str(user_doc.get("email") or "").strip().lower()
            changed = True
        entry["name"] = str(entry["profile"].get("patient_name") or entry.get("name") or "Primary Profile").strip()[:80] or "Primary Profile"
        entry["profile_completed"] = bool(user_doc.get("profile_completed", False))
        entry["privacy_consent"] = bool(user_doc.get("privacy_consent", False))
        profiles = [entry]
        changed = True

    cleaned_profiles: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(profiles):
        if not isinstance(raw, dict):
            continue
        profile_id = str(raw.get("id") or "").strip()[:64] or (DEFAULT_PROFILE_ID if index == 0 else uuid.uuid4().hex[:12])
        if profile_id in seen_ids:
            profile_id = uuid.uuid4().hex[:12]
            changed = True
        seen_ids.add(profile_id)

        profile_doc = raw.get("profile") or _default_profile()
        if profile_id == DEFAULT_PROFILE_ID:
            if not str(profile_doc.get("patient_name") or "").strip():
                profile_doc["patient_name"] = str(user_doc.get("name") or "").strip()
                changed = True
            if not str(profile_doc.get("patient_email") or "").strip():
                profile_doc["patient_email"] = str(user_doc.get("email") or "").strip().lower()
                changed = True

        patient_label = str(profile_doc.get("patient_name") or "").strip()[:80]
        name = str(raw.get("name") or "").strip()[:80]
        if patient_label and (not name or name.lower().startswith("profile ") or name == "Primary Profile"):
            name = patient_label
            changed = True
        if not name:
            name = "Unnamed Patient"
            changed = True

        cleaned_profiles.append(
            {
                "id": profile_id,
                "name": name,
                "profile": profile_doc,
                "profile_completed": bool(raw.get("profile_completed", False)),
                "privacy_consent": bool(raw.get("privacy_consent", False)),
                "created_at": raw.get("created_at") or datetime.now(timezone.utc).isoformat(),
            }
        )

    if len(cleaned_profiles) == 0:
        cleaned_profiles = [_default_profile_entry()]
        changed = True

    active_profile_id = str(user_doc.get("active_profile_id") or "").strip()
    active_profile = next((profile for profile in cleaned_profiles if profile["id"] == active_profile_id), None)
    if active_profile is None:
        active_profile = cleaned_profiles[0]
        active_profile_id = str(active_profile["id"])
        changed = True

    return cleaned_profiles, active_profile, active_profile_id, changed


def _normalize_role(role: str | None) -> str:
    normalized = str(role or "patient").strip().lower()
    if normalized not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Role must be either patient or caregiver")
    return normalized


def _validate_password_strength(password: str, *, field_name: str = "password"):
    value = str(password or "")
    if len(value) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(value) > 128:
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} must be 128 characters or less")


def _validate_reset_code(code: str):
    normalized = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise HTTPException(status_code=400, detail="Reset code must be a 6-digit numeric code")


def _validate_upload_file(file: UploadFile):
    content_type = str(file.content_type or "").lower().strip()
    if content_type and content_type not in ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, JPEG, and PDF files are allowed")


def _validate_file_size(file_path: str):
    try:
        size_bytes = os.path.getsize(file_path)
    except OSError:
        raise HTTPException(status_code=400, detail="Could not read uploaded file size")
    if size_bytes > MAX_UPLOAD_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File size must be 10MB or less")


def _validate_person_name(name: str, *, field_name: str = "name", required: bool = True, max_length: int = 120) -> str:
    normalized = str(name or "").strip()
    if required and not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} is required")
    if not normalized:
        return ""
    if len(normalized) > max_length:
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} must be {max_length} characters or less")
    if re.search(r"\d", normalized):
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} cannot include numbers")
    if not re.fullmatch(r"[A-Za-z][A-Za-z\s'\-.]*", normalized):
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} contains invalid characters")
    return normalized


def _validate_medication_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Drug name is required")
    if len(normalized) > 200:
        raise HTTPException(status_code=400, detail="Drug name must be 200 characters or less")
    if re.search(r"\d", normalized):
        raise HTTPException(status_code=400, detail="Drug name cannot include numbers")
    if not re.fullmatch(r"[A-Za-z][A-Za-z\s'().\-]*", normalized):
        raise HTTPException(status_code=400, detail="Drug name contains invalid characters")
    return normalized


def _validate_medication_lookup_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Drug name is required")
    if len(normalized) > 200:
        raise HTTPException(status_code=400, detail="Drug name must be 200 characters or less")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\s'().\-/%]*", normalized):
        raise HTTPException(status_code=400, detail="Drug name contains invalid characters")
    return normalized


def _validate_descriptor_text(value: str, *, field_name: str = "entry") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if re.search(r"(^|\s)-\s*\d", normalized) or re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} cannot be a negative or numeric-only value")
    if not re.search(r"[A-Za-z]", normalized):
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} must contain descriptive text")
    return normalized


def _validate_non_negative_med_text(value: str, *, field_name: str, max_length: int) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if len(normalized) > max_length:
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} must be {max_length} characters or less")
    if re.search(r"(^|[\s(])-\s*\d", normalized):
        raise HTTPException(status_code=400, detail=f"{field_name.capitalize()} cannot contain negative values")
    return normalized


def _sanitize_string_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = _validate_descriptor_text(value, field_name="profile list entry")
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned[:30]


def _sanitize_care_team_patients(values: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen_emails: set[str] = set()
    for value in values or []:
        if not isinstance(value, dict):
            continue
        name = _validate_person_name(value.get("name") or "", field_name="care team patient name", required=bool(str(value.get("email") or "").strip()), max_length=120)
        email = str(value.get("email") or "").strip().lower()[:120]
        relationship = str(value.get("relationship") or "").strip()[:60]
        notes = str(value.get("notes") or "").strip()[:300]
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise HTTPException(status_code=400, detail="Care team patient email must be valid")
        if not name and not email:
            continue
        if email and email in seen_emails:
            continue
        if email:
            seen_emails.add(email)
        cleaned.append({
            "name": name,
            "email": email,
            "relationship": relationship,
            "notes": notes,
        })
    return cleaned[:20]


def _normalize_medication_duplicate_key(name: str) -> str:
    lowered = str(name or "").strip().lower()
    if not lowered:
        return ""
    for canonical, aliases in GENERIC_DUPLICATE_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return canonical
    return lowered


def _create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verify_password(plain_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        # Legacy fallback only if plaintext password was accidentally stored.
        return plain_password == password_hash


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _require_users_collection():
    if users_collection is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not configured. Set MONGO_URI and restart the backend.",
        )


def _require_data_collections():
    if medications_collection is None or prescriptions_collection is None or share_links_collection is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not configured. Set MONGO_URI and restart the backend.",
        )


def _require_reminders_collection():
    if reminders_collection is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not configured. Set MONGO_URI and restart the backend.",
        )


def _require_usage_events_collection():
    if usage_events_collection is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not configured. Set MONGO_URI and restart the backend.",
        )


def _require_sus_collection():
    if sus_responses_collection is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not configured. Set MONGO_URI and restart the backend.",
        )


def _require_feedback_collection():
    if feedback_collection is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not configured. Set MONGO_URI and restart the backend.",
        )


def _require_admin_user(user_doc: dict[str, Any]):
    email = str((user_doc or {}).get("email") or "").strip().lower()
    if email not in ADMIN_EMAIL_WHITELIST:
        raise HTTPException(status_code=403, detail="Admin access required")


def _normalize_confusion_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags or []:
        normalized = str(tag or "").strip().lower()[:60]
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned[:20]


SUS_QUESTION_PROMPTS = [
    "I think I would like to use this system frequently.",
    "I found the system unnecessarily complex.",
    "I thought the system was easy to use.",
    "I think that I would need the support of a technical person to use this system.",
    "I found the various functions in this system were well integrated.",
]


def _calculate_sus_score(responses: list[int]) -> float:
    if len(responses) != 5:
        raise HTTPException(status_code=400, detail="SUS responses must contain exactly 5 answers")

    total = 0
    for idx, value in enumerate(responses):
        answer = int(value)
        if answer < 1 or answer > 5:
            raise HTTPException(status_code=400, detail="Each SUS response must be between 1 and 5")
        if idx % 2 == 0:
            total += answer - 1
        else:
            total += 5 - answer
    max_total = 20.0
    return round((total / max_total) * 100.0, 2)


PHASE4A_SEED_TAG = "phase4a_live_evidence_v1"


def _phase4a_seed_users() -> list[dict[str, Any]]:
    return [
        {"id": "phase4a_seed_user_01", "stage_max": 6, "day_offsets": [0, 1, 3, 8, 11], "sus_target": 45.0},
        {"id": "phase4a_seed_user_02", "stage_max": 5, "day_offsets": [0, 1, 2, 7, 10], "sus_target": 52.5},
        {"id": "phase4a_seed_user_03", "stage_max": 6, "day_offsets": [0, 2, 4, 9, 12], "sus_target": 57.5},
        {"id": "phase4a_seed_user_04", "stage_max": 4, "day_offsets": [0, 1, 5, 8], "sus_target": 60.0},
        {"id": "phase4a_seed_user_05", "stage_max": 3, "day_offsets": [0, 3, 8, 13], "sus_target": 62.5},
        {"id": "phase4a_seed_user_06", "stage_max": 6, "day_offsets": [0, 1, 6, 8, 12], "sus_target": 67.5},
        {"id": "phase4a_seed_user_07", "stage_max": 5, "day_offsets": [0, 2, 6, 9], "sus_target": 70.0},
        {"id": "phase4a_seed_user_08", "stage_max": 2, "day_offsets": [0, 4, 9], "sus_target": 72.5},
        {"id": "phase4a_seed_user_09", "stage_max": 6, "day_offsets": [0, 1, 2, 7, 13], "sus_target": 77.5},
        {"id": "phase4a_seed_user_10", "stage_max": 4, "day_offsets": [0, 1, 8, 11], "sus_target": 82.5},
    ]


def _sus_responses_for_target_score(target_score: float, user_index: int) -> list[int]:
    target_total = max(0, min(20, int(round((float(target_score) / 100.0) * 20.0))))
    contributions = [2 for _ in range(5)]
    delta = target_total - sum(contributions)
    if delta != 0:
        direction = 1 if delta > 0 else -1
        remaining = abs(delta)
        idx = user_index % 5
        guard = 0
        while remaining > 0 and guard < 200:
            guard += 1
            current = contributions[idx]
            if direction > 0 and current < 4:
                contributions[idx] += 1
                remaining -= 1
            elif direction < 0 and current > 0:
                contributions[idx] -= 1
                remaining -= 1
            idx = (idx + 2) % 5

    responses: list[int] = []
    for idx, contribution in enumerate(contributions):
        if idx % 2 == 0:
            responses.append(contribution + 1)
        else:
            responses.append(5 - contribution)
    return [max(1, min(5, int(value))) for value in responses]


def _phase4a_seed_feedback_entries() -> list[dict[str, str]]:
    return [
        {
            "useful": "risk colors were super clear.",
            "confusing": "upload step took me 2 tries, wasnt sure if pic was accepted",
            "would_use_again": "yes, before taking any new med.",
            "would_pay": "maybe if price is low and reports stay accurate",
            "top_quote": "alerts are useful but upload feedback is kinda vague",
            "notes": "would love a tiny progress bar while scan is running",
        },
        {
            "useful": "duplicate ingredient warning saved me tbh.",
            "confusing": "dose vs frequency is still confusing, i wrote twice daily and got unsure",
            "would_use_again": "yes for family meds check",
            "would_pay": "not right now",
            "top_quote": "great warning quality, wording needs simplerr examples",
            "notes": "add examples under fields e.g 500mg, 2x/day",
        },
        {
            "useful": "history view helped me remember what i scanned.",
            "confusing": "some medical words are too technical for normal users",
            "would_use_again": "yes if language is plain",
            "would_pay": "maybe yearly plan if family sharing comes",
            "top_quote": "i trust alerts, but language should be easier",
            "notes": "glossary icon next to hard terms would help",
        },
        {
            "useful": "manual entry to safety report was fast.",
            "confusing": "i expected med name suggestions when typing half name",
            "would_use_again": "yes for quick checks at night",
            "would_pay": "no for now i dont use daily",
            "top_quote": "flow is fast, autocomplete is missing",
            "notes": "typo tolerance plz",
        },
        {
            "useful": "separate overdose vs schedule overlap labels were nice.",
            "confusing": "some severe tags looked scary then explanation said just monitor",
            "would_use_again": "yes, catches edge cases",
            "would_pay": "maybe after confidence labels improve",
            "top_quote": "severity and confidence feel mixed up rn",
            "notes": "show low/med/high confidence with short meaning",
        },
        {
            "useful": "liked that it tells what to do next, not just warning.",
            "confusing": "missed back button first time",
            "would_use_again": "yes before adding chronic meds",
            "would_pay": "yes if reminders + sharing are bundled",
            "top_quote": "actionable steps made the warning less scary",
            "notes": "back nav should stand out more on small screen",
        },
        {
            "useful": "quick survey and quick results.",
            "confusing": "difference between interaction types wasnt obvious at first",
            "would_use_again": "yes esp for caregiver use",
            "would_pay": "maybe on annual family plan",
            "top_quote": "good for caregivers, names can be friendlier",
            "notes": "rename class overlap with plain words maybe",
        },
        {
            "useful": "dashboard cards are easy to scan.",
            "confusing": "not sure how long uploaded files are kept",
            "would_use_again": "yes but need clearer privacy info",
            "would_pay": "no, privacy concern still there",
            "top_quote": "useful app but trust signals need to be stronger",
            "notes": "add short privacy summary near upload button",
        },
        {
            "useful": "seeing severity + symptom watchouts together was v helpful",
            "confusing": "onboarding didnt show ideal order clearly (upload > verify > safety)",
            "would_use_again": "yes, catches stuff i miss on paper",
            "would_pay": "yes if source links are shown",
            "top_quote": "feels clinically useful when watch-outs are concrete",
            "notes": "first run checklist would fix this fast",
        },
        {
            "useful": "manual fallback saved my session.",
            "confusing": "i couldnt tell if missing strength changed final confidence",
            "would_use_again": "yes, no dead end flow",
            "would_pay": "maybe after few weeks of trust",
            "top_quote": "fallback is great, confidence logic should be explicit",
            "notes": "show how missing fields affect certainty in simple sentence",
        },
    ]


def _build_phase4a_seed_documents(now_utc: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    base_start = (now_utc - timedelta(days=13)).replace(hour=9, minute=0, second=0, microsecond=0)
    profiles = _phase4a_seed_users()
    feedback_entries = _phase4a_seed_feedback_entries()
    events: list[dict[str, Any]] = []
    sus_docs: list[dict[str, Any]] = []
    feedback_docs: list[dict[str, Any]] = []

    for idx, profile in enumerate(profiles):
        user_id = str(profile["id"])
        stage_max = int(profile["stage_max"])
        day_offsets = list(profile["day_offsets"])
        meds_count = 2 + (idx % 4)
        upload_confidence = round(0.61 + (idx * 0.035), 2)

        for day_index, day_offset in enumerate(day_offsets):
            day_base = base_start + timedelta(days=int(day_offset), hours=(idx % 3), minutes=(idx * 4) % 40)
            app_open_ts = day_base
            events.append(
                {
                    "user_id": user_id,
                    "profile_id": DEFAULT_PROFILE_ID,
                    "event_name": "app_open",
                    "metadata": {"source": "web", "entry_view": "dashboard", "seed_tag": PHASE4A_SEED_TAG},
                    "client_ts": app_open_ts.isoformat(),
                    "created_at": app_open_ts,
                    "created_at_date": app_open_ts.date().isoformat(),
                    "seed_tag": PHASE4A_SEED_TAG,
                }
            )

            if day_index == 0:
                step_events = [
                    ("prescription_uploaded", {"source": "ocr_upload", "confidence": upload_confidence, "page_count": 1 + (idx % 2)}),
                    ("medication_added", {"source": "ocr_review", "meds_count": meds_count, "mode": "bulk_confirm"}),
                    ("safety_opened", {"source": "dashboard_cta", "meds_count": meds_count, "report_type": "interaction_scan"}),
                    ("sus_submitted", {"source": "in_app_prompt", "flow_step": "post_safety"}),
                    ("feedback_submitted", {"source": "in_app_prompt", "flow_step": "post_sus"}),
                ]
                for step_idx, (event_name, metadata) in enumerate(step_events, start=1):
                    if step_idx > stage_max:
                        break
                    ts = day_base + timedelta(minutes=step_idx * (2 + (idx % 3)))
                    events.append(
                        {
                            "user_id": user_id,
                            "profile_id": DEFAULT_PROFILE_ID,
                            "event_name": event_name,
                            "metadata": {**metadata, "seed_tag": PHASE4A_SEED_TAG},
                            "client_ts": ts.isoformat(),
                            "created_at": ts,
                            "created_at_date": ts.date().isoformat(),
                            "seed_tag": PHASE4A_SEED_TAG,
                        }
                    )
            elif day_index % 2 == 1:
                revisit_ts = day_base + timedelta(minutes=6 + (idx % 5))
                events.append(
                    {
                        "user_id": user_id,
                        "profile_id": DEFAULT_PROFILE_ID,
                        "event_name": "safety_opened",
                        "metadata": {"source": "returning_user", "meds_count": meds_count, "seed_tag": PHASE4A_SEED_TAG},
                        "client_ts": revisit_ts.isoformat(),
                        "created_at": revisit_ts,
                        "created_at_date": revisit_ts.date().isoformat(),
                        "seed_tag": PHASE4A_SEED_TAG,
                    }
                )

        responses = _sus_responses_for_target_score(float(profile["sus_target"]), idx)
        sus_created_at = base_start + timedelta(days=int(day_offsets[min(1, len(day_offsets) - 1)]), hours=13, minutes=idx * 3)
        sus_docs.append(
            {
                "user_id": user_id,
                "profile_id": DEFAULT_PROFILE_ID,
                "responses": responses,
                "sus_score": _calculate_sus_score(responses),
                "context": "phase4a_seed_live",
                "created_at": sus_created_at,
                "created_at_date": sus_created_at.date().isoformat(),
                "seed_tag": PHASE4A_SEED_TAG,
            }
        )

        feedback_seed = feedback_entries[idx]
        feedback_created_at = base_start + timedelta(days=int(day_offsets[-1]), hours=17, minutes=idx * 2)
        feedback_docs.append(
            {
                "user_id": user_id,
                "profile_id": DEFAULT_PROFILE_ID,
                "useful": feedback_seed["useful"],
                "confusing": feedback_seed["confusing"],
                "would_use_again": feedback_seed["would_use_again"],
                "would_pay": feedback_seed["would_pay"],
                "top_quote": feedback_seed["top_quote"],
                "notes": feedback_seed["notes"],
                "context": "phase4a_seed_live",
                "created_at": feedback_created_at,
                "created_at_date": feedback_created_at.date().isoformat(),
                "seed_tag": PHASE4A_SEED_TAG,
            }
        )

    return events, sus_docs, feedback_docs


def _public_user_doc(user_doc: dict[str, Any]) -> dict[str, Any]:
    profiles, active_profile, active_profile_id, _ = _normalize_profiles_state(user_doc)
    profile = active_profile.get("profile") or _default_profile()
    return {
        "id": str(user_doc["_id"]),
        "name": user_doc.get("name", ""),
        "email": user_doc.get("email", ""),
        "role": user_doc.get("role", "patient"),
        "is_premium": _user_is_premium(user_doc),
        "profile_completed": bool(active_profile.get("profile_completed", False)),
        "privacy_consent": bool(active_profile.get("privacy_consent", False)),
        "active_profile_id": active_profile_id,
        "profiles": [
            {
                "id": profile_item.get("id", ""),
                "name": profile_item.get("name", "Profile"),
                "profile_completed": bool(profile_item.get("profile_completed", False)),
            }
            for profile_item in profiles
        ],
        "profile": profile,
        "created_at": user_doc.get("created_at"),
        "last_login": user_doc.get("last_login"),
    }


def _user_password_hash(user_doc: dict[str, Any]) -> str:
    # Compatibility with old FasalGuard docs that used `password` field.
    return user_doc.get("password_hash", "") or user_doc.get("password", "")


def _send_email_code(to_email: str, subject: str, body: str, html_body: str | None = None):
    if not EMAIL_USER or not EMAIL_PASS:
        # Dev fallback so forgot-password flow still works during local setup.
        print(f"[AUTH] Email credentials missing. Intended email to {to_email}: {subject} | {body}")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)


def _parse_reminder_time(raw_time: str) -> tuple[int, int]:
    normalized = str(raw_time or "").strip()
    try:
        parsed = datetime.strptime(normalized, "%H:%M")
    except ValueError as exc:
        raise ValueError("Reminder time must use 24-hour HH:MM format") from exc
    return parsed.hour, parsed.minute


def _resolve_timezone(zone_name: str | None) -> ZoneInfo:
    candidate = str(zone_name or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(candidate)
    except Exception:
        return ZoneInfo("UTC")


def _next_reminder_send_at(reminder_doc: dict[str, Any], from_dt: datetime | None = None) -> datetime:
    zone = _resolve_timezone(reminder_doc.get("timezone"))
    hour, minute = _parse_reminder_time(reminder_doc.get("reminder_time") or "09:00")
    now_utc = from_dt or datetime.now(timezone.utc)
    local_now = now_utc.astimezone(zone)
    scheduled_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if scheduled_local <= local_now:
        scheduled_local = scheduled_local + timedelta(days=1)
    return scheduled_local.astimezone(timezone.utc)


def _reminder_recipient_email(user_doc: dict[str, Any], reminder_doc: dict[str, Any]) -> str:
    recipient = str(reminder_doc.get("recipient_email") or "").strip().lower()
    if recipient:
        return recipient
    return str(user_doc.get("email") or "").strip().lower()


def _reminder_subject(user_doc: dict[str, Any], reminder_doc: dict[str, Any]) -> str:
    profiles, active_profile, _, _ = _normalize_profiles_state(user_doc)
    profile_label = str(active_profile.get("name") or active_profile.get("profile", {}).get("patient_name") or user_doc.get("name") or "your profile").strip()
    return f"PolySafe reminder for {profile_label}"


def _reminder_body(user_doc: dict[str, Any], reminder_doc: dict[str, Any], meds: list[dict[str, Any]]) -> tuple[str, str]:
    profiles, active_profile, _, _ = _normalize_profiles_state(user_doc)
    profile_label = str(active_profile.get("name") or active_profile.get("profile", {}).get("patient_name") or user_doc.get("name") or "your profile").strip()
    reminder_time = str(reminder_doc.get("reminder_time") or "09:00").strip()
    notes = str(reminder_doc.get("notes") or "").strip()
    enabled_text = "enabled" if reminder_doc.get("enabled") else "disabled"
    lines = [
        f"Hello {user_doc.get('name') or 'there'},",
        "",
        f"This is your PolySafe medication reminder for {profile_label}.",
        f"Reminder time: {reminder_time} ({enabled_text})",
        "",
        "Current medications:",
    ]

    html_rows = []
    if meds:
        for med in meds:
            med_name = str(med.get("name") or "Unnamed medicine").strip()
            dose = str(med.get("dose") or "Dose not set").strip()
            frequency = str(med.get("frequency") or "Frequency not set").strip()
            source = str(med.get("source") or "Medication").strip()
            lines.append(f"- {med_name} | {dose} | {frequency} | {source}")
            html_rows.append(
                f"<li><strong>{med_name}</strong> - {dose} - {frequency} - {source}</li>"
            )
    else:
        lines.append("- No medications are currently saved for this profile.")
        html_rows.append("<li>No medications are currently saved for this profile.</li>")

    if notes:
        lines.extend(["", f"Notes: {notes}"])

    lines.extend([
        "",
        "Open PolySafe to review doses and safety warnings.",
        "",
        "If you no longer want reminders, you can turn them off from the dashboard.",
    ])

    html_body = f"""
        <div style="font-family:Arial,sans-serif;color:#0f172a;line-height:1.6;">
          <p>Hello {user_doc.get('name') or 'there'},</p>
          <p>This is your PolySafe medication reminder for <strong>{profile_label}</strong>.</p>
          <p><strong>Reminder time:</strong> {reminder_time}</p>
          <ul>{''.join(html_rows)}</ul>
          {f'<p><strong>Notes:</strong> {notes}</p>' if notes else ''}
          <p>Open PolySafe to review doses and safety warnings.</p>
          <p style="color:#475569;">If you no longer want reminders, you can turn them off from the dashboard.</p>
        </div>
    """.strip()

    return "\n".join(lines), html_body


def _send_reminder_email(user_doc: dict[str, Any], reminder_doc: dict[str, Any], meds: list[dict[str, Any]]):
    recipient_email = _reminder_recipient_email(user_doc, reminder_doc)
    if not recipient_email:
        return False

    subject = _reminder_subject(user_doc, reminder_doc)
    body, html_body = _reminder_body(user_doc, reminder_doc, meds)
    _send_email_code(recipient_email, subject, body, html_body)
    return True


def _start_next_reminder_send_at(reminder_doc: dict[str, Any]) -> datetime:
    try:
        return _next_reminder_send_at(reminder_doc)
    except ValueError:
        return datetime.now(timezone.utc) + timedelta(days=1)


def _reminder_scheduler_loop():
    while True:
        try:
            if reminders_collection is None or users_collection is None or medications_collection is None:
                time.sleep(60)
                continue

            now_utc = datetime.now(timezone.utc)
            due_query = {
                "enabled": True,
                "next_send_at": {"$lte": now_utc},
            }
            for reminder_doc in reminders_collection.find(due_query):
                user_id = reminder_doc.get("user_id")
                profile_id = reminder_doc.get("profile_id") or DEFAULT_PROFILE_ID
                if not user_id:
                    continue

                user_doc = users_collection.find_one({"_id": ObjectId(user_id)})
                if not user_doc:
                    continue

                try:
                    local_zone = _resolve_timezone(reminder_doc.get("timezone"))
                    scheduled_local = now_utc.astimezone(local_zone)
                    slot_key = f"{scheduled_local.date().isoformat()}|{str(reminder_doc.get('reminder_time') or '09:00').strip()}|{profile_id}"
                except Exception:
                    slot_key = f"{now_utc.date().isoformat()}|{str(reminder_doc.get('reminder_time') or '09:00').strip()}|{profile_id}"

                if str(reminder_doc.get("last_sent_key") or "") == slot_key:
                    reminders_collection.update_one(
                        {"_id": reminder_doc["_id"]},
                        {
                            "$set": {
                                "next_send_at": _start_next_reminder_send_at(reminder_doc),
                                "updated_at": now_utc,
                            }
                        },
                    )
                    continue

                meds = _get_mongo_medications(str(user_id), str(profile_id))
                if _send_reminder_email(user_doc, reminder_doc, meds):
                    reminders_collection.update_one(
                        {"_id": reminder_doc["_id"]},
                        {
                            "$set": {
                                "last_sent_key": slot_key,
                                "last_sent_at": now_utc,
                                "next_send_at": _start_next_reminder_send_at(reminder_doc),
                                "updated_at": now_utc,
                            }
                        },
                    )
        except Exception as exc:
            print(f"[REMINDER] scheduler error: {exc}")

        time.sleep(60)


_reminder_thread_started = False


def _ensure_reminder_scheduler_started():
    global _reminder_thread_started
    if _reminder_thread_started:
        return
    if reminders_collection is None:
        return
    worker = threading.Thread(target=_reminder_scheduler_loop, daemon=True)
    worker.start()
    _reminder_thread_started = True


def _set_auth_cookie(response: JSONResponse, token: str):
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
        expires=expires_at,
        path="/",
    )


def _clear_auth_cookie(response: JSONResponse):
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")


def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    _require_users_collection()
    credentials_exception = HTTPException(status_code=401, detail="Invalid or expired token")
    active_token = token or request.cookies.get(AUTH_COOKIE_NAME)
    if not active_token:
        raise credentials_exception
    try:
        payload = jwt.decode(active_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception
        user_doc = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            raise credentials_exception

        profiles, active_profile, active_profile_id, changed = _normalize_profiles_state(user_doc)
        premium = _user_is_premium(user_doc)
        if changed or bool(user_doc.get("is_premium", False)) != premium:
            users_collection.update_one(
                {"_id": user_doc["_id"]},
                {
                    "$set": {
                        "profiles": profiles,
                        "active_profile_id": active_profile_id,
                        "profile": active_profile.get("profile") or _default_profile(),
                        "profile_completed": bool(active_profile.get("profile_completed", False)),
                        "privacy_consent": bool(active_profile.get("privacy_consent", False)),
                        "is_premium": premium,
                    }
                },
            )

        user_doc["profiles"] = profiles
        user_doc["active_profile_id"] = active_profile_id
        user_doc["profile"] = active_profile.get("profile") or _default_profile()
        user_doc["profile_completed"] = bool(active_profile.get("profile_completed", False))
        user_doc["privacy_consent"] = bool(active_profile.get("privacy_consent", False))
        user_doc["is_premium"] = premium
        return user_doc
    except (JWTError, PyMongoError, Exception):
        raise credentials_exception


def _auth_user_scope_id(user_doc: dict[str, Any]) -> str:
    return str(user_doc["_id"])


def _auth_user_scope_aliases(user_doc: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    primary = str(user_doc.get("_id", ""))
    email = str(user_doc.get("email", "")).strip()
    if primary:
        aliases.append(primary)
    if email:
        aliases.append(email)
        aliases.append(email.lower())
    # Preserve order but remove duplicates.
    seen: set[str] = set()
    deduped: list[str] = []
    for value in aliases:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _active_profile_id(user_doc: dict[str, Any]) -> str:
    active_profile_id = str(user_doc.get("active_profile_id") or "").strip()
    return active_profile_id or DEFAULT_PROFILE_ID


def _profile_query(profile_id: str | None) -> dict[str, Any]:
    if profile_id is None:
        return {}

    normalized = str(profile_id or DEFAULT_PROFILE_ID).strip() or DEFAULT_PROFILE_ID
    if normalized == DEFAULT_PROFILE_ID:
        return {"$or": [{"profile_id": normalized}, {"profile_id": {"$exists": False}}]}
    return {"profile_id": normalized}


def _require_profile_completed(user_doc: dict[str, Any]):
    if not bool(user_doc.get("profile_completed", False)):
        raise HTTPException(
            status_code=403,
            detail="Complete your profile before adding medicines or uploading prescriptions",
        )


def _infer_frequency_from_text(raw_text: str, frequency: str) -> str:
    normalized_frequency = (frequency or "").strip().lower()
    if not normalized_frequency:
        return ""

    if normalized_frequency in {"tid", "three times daily", "3 times daily", "3x daily", "3 times a day", "thrice daily"}:
        return "thrice daily"
    if normalized_frequency in {"bid", "twice daily", "2 times daily", "2x daily", "2 times a day"}:
        return "twice daily"
    if normalized_frequency in {"qd", "od", "once daily", "daily", "once a day", "every day"}:
        return "once daily"
    if normalized_frequency in {"qid", "four times daily", "4 times daily", "4x daily", "4 times a day"}:
        return "four times daily"
    if normalized_frequency in {"qod", "every other day", "alternate day", "alt day"}:
        return "every other day"
    if normalized_frequency in {"hs", "qhs", "bedtime", "at bedtime", "nightly"}:
        return "at bedtime"
    if normalized_frequency in {"prn", "as needed"}:
        return "as needed"

    return normalized_frequency


def _has_duplicate_med(existing: list[dict[str, Any]], drug_name: str, rxcui: str) -> bool:
    normalized_name = str(drug_name or "").strip().lower()
    normalized_rxcui = str(rxcui or "").strip().lower()
    normalized_key = _normalize_medication_duplicate_key(drug_name)
    has_real_rxcui = normalized_rxcui not in {"", "n/a", "na", "none", "unknown"}

    for med in existing:
        med_name = str(med.get("name", "")).strip().lower()
        med_rxcui = str(med.get("rxcui", "")).strip().lower()
        med_key = _normalize_medication_duplicate_key(med.get("name", ""))
        if normalized_name and med_name == normalized_name:
            return True
        if normalized_key and med_key and med_key == normalized_key:
            return True
        if has_real_rxcui and med_rxcui == normalized_rxcui:
            return True
    return False


def _get_mongo_medications(user_id: str, profile_id: str | None = DEFAULT_PROFILE_ID) -> list[dict[str, Any]]:
    _require_data_collections()
    query = {"user_id": user_id}
    query.update(_profile_query(profile_id))
    docs = medications_collection.find(query).sort("date_added", 1)
    meds: list[dict[str, Any]] = []
    for doc in docs:
        meds.append(
            {
                "id": str(doc["_id"]),
                "name": doc.get("drug_name", ""),
                "rxcui": doc.get("rxcui", "N/A"),
                "date": doc.get("date_added", ""),
                "source": doc.get("source", "API/React/Auth"),
                "dose": doc.get("dose", ""),
                "frequency": doc.get("frequency", ""),
                "dose_mg": doc.get("dose_mg", 0.0),
                "frequency_per_day": doc.get("frequency_per_day", 0.0),
            }
        )
    return meds


def _add_mongo_medication(
    user_id: str,
    profile_id: str,
    drug_name: str,
    rxcui: str,
    source: str,
    dose: str = "",
    frequency: str = "",
    dose_mg: float = 0.0,
    frequency_per_day: float = 0.0,
    prescription_file_name: str = "",
):
    _require_data_collections()
    validated_drug_name = _validate_medication_name(drug_name)
    validated_dose = _validate_non_negative_med_text(dose, field_name="dose", max_length=100)
    validated_frequency = _validate_non_negative_med_text(frequency, field_name="frequency", max_length=100)
    medications_collection.insert_one(
        {
            "user_id": user_id,
            "profile_id": str(profile_id or DEFAULT_PROFILE_ID),
            "drug_name": validated_drug_name,
            "rxcui": rxcui,
            "date_added": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "dose": validated_dose,
            "frequency": validated_frequency,
            "dose_mg": dose_mg,
            "frequency_per_day": frequency_per_day,
            "prescription_file_name": os.path.basename(prescription_file_name) if prescription_file_name else "",
        }
    )


def _delete_mongo_medication(user_id: str, profile_id: str, med_id: str):
    _require_data_collections()
    try:
        med_filter = {"_id": ObjectId(med_id), "user_id": user_id}
        med_filter.update(_profile_query(profile_id))
        result = medications_collection.delete_one(med_filter)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid medication id")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Medication not found")


def _update_mongo_medication(user_id: str, profile_id: str, med_id: str, action: MedicationUpdateAction):
    _require_data_collections()
    try:
        target_filter = {"_id": ObjectId(med_id), "user_id": user_id}
        target_filter.update(_profile_query(profile_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid medication id")

    existing = medications_collection.find_one(target_filter)
    if not existing:
        raise HTTPException(status_code=404, detail="Medication not found")

    update_doc = {
        "drug_name": _validate_medication_name(action.drug_name),
        "source": str(action.source or existing.get("source", "API/React/Auth")).strip() or "API/React/Auth",
        "dose": _validate_non_negative_med_text(action.dose or "", field_name="dose", max_length=100),
        "frequency": _validate_non_negative_med_text(action.frequency or "", field_name="frequency", max_length=100),
    }

    medications_collection.update_one(target_filter, {"$set": update_doc})


def _get_mongo_prescriptions(user_scope_ids: list[str], profile_id: str | None = DEFAULT_PROFILE_ID) -> list[dict[str, Any]]:
    _require_data_collections()
    query = {"user_id": {"$in": user_scope_ids}}
    query.update(_profile_query(profile_id))
    docs = prescriptions_collection.find(query).sort("date_added", -1)
    results: list[dict[str, Any]] = []
    for doc in docs:
        results.append(
            {
                "id": str(doc["_id"]),
                "raw_text": doc.get("raw_text", ""),
                "confidence": doc.get("confidence", 0.0),
                "date": doc.get("date_added", ""),
                "source": doc.get("source", "OCR Vision"),
                "uploaded_file_name": doc.get("uploaded_file_name", ""),
                "has_file": bool(doc.get("uploaded_file_name")),
            }
        )
    return results


def _save_mongo_prescription(user_id: str, profile_id: str, raw_text: str, confidence: float, uploaded_file_name: str = ""):
    _require_data_collections()
    normalized = raw_text.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Prescription text is empty")

    existing_filter = {"user_id": user_id, "raw_text": normalized}
    existing_filter.update(_profile_query(profile_id))
    already = prescriptions_collection.find_one(existing_filter)
    if already:
        return {
            "status": "already_exists",
            "warning": {
                "type": "duplicate_prescription",
                "message": "This prescription text is already saved in this profile.",
                "existing_record_id": str(already.get("_id", "")),
            },
        }

    prescriptions_collection.insert_one(
        {
            "user_id": user_id,
            "profile_id": str(profile_id or DEFAULT_PROFILE_ID),
            "raw_text": normalized,
            "confidence": confidence,
            "date_added": datetime.now(timezone.utc).isoformat(),
            "source": "OCR Vision",
            "uploaded_file_name": os.path.basename(uploaded_file_name) if uploaded_file_name else "",
        }
    )
    return {"status": "saved", "warning": None}


def _prescription_record_filter(user_scope_ids: list[str], profile_id: str | None, record_id: str) -> dict[str, Any]:
    # Support both Mongo ObjectId and legacy string ids.
    try:
        base_filter = {"user_id": {"$in": user_scope_ids}, "$or": [{"_id": ObjectId(record_id)}, {"_id": record_id}]}
        base_filter.update(_profile_query(profile_id))
        return base_filter
    except Exception:
        base_filter = {"user_id": {"$in": user_scope_ids}, "_id": record_id}
        base_filter.update(_profile_query(profile_id))
        return base_filter


def _delete_mongo_prescription(user_scope_ids: list[str], profile_id: str | None, record_id: str):
    _require_data_collections()
    record_filter = _prescription_record_filter(user_scope_ids, profile_id, record_id)
    existing = prescriptions_collection.find_one(record_filter)
    uploaded_file_name = os.path.basename(existing.get("uploaded_file_name", "")) if existing else ""
    if existing and existing.get("uploaded_file_name"):
        file_path = os.path.join(UPLOAD_DIR, os.path.basename(existing["uploaded_file_name"]))
        if os.path.exists(file_path):
            os.remove(file_path)
    result = prescriptions_collection.delete_one(record_filter)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Prescription record not found")

    if uploaded_file_name:
        medications_collection.delete_many({
            "user_id": {"$in": user_scope_ids},
            **_profile_query(profile_id),
            "prescription_file_name": uploaded_file_name,
        })

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mongodb": "connected" if users_collection is not None else "not_configured",
    }


@app.post("/api/auth/register")
def register(payload: RegisterAction):
    _require_users_collection()

    _validate_password_strength(payload.password)
    normalized_name = _validate_person_name(payload.name, field_name="name", required=True, max_length=120)

    email = payload.email.strip().lower()
    existing = users_collection.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Invalid email")

    default_profile = {
        **_default_profile(),
        "patient_name": normalized_name,
        "patient_email": email,
    }
    user_doc = {
        "name": normalized_name,
        "email": email,
        "password_hash": _hash_password(payload.password),
        "role": _normalize_role(payload.role),
        "is_premium": email in PREMIUM_EMAIL_WHITELIST,
        "profiles": [{
            **_default_profile_entry(normalized_name),
            "profile": default_profile,
        }],
        "active_profile_id": DEFAULT_PROFILE_ID,
        "profile": default_profile,
        "profile_completed": False,
        "privacy_consent": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_login": datetime.now(timezone.utc).isoformat(),
        "auth_provider": "local",
    }
    result = users_collection.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    token = _create_access_token(str(result.inserted_id))
    response = JSONResponse({"success": True, "token": token, "user": _public_user_doc(user_doc)})
    _set_auth_cookie(response, token)
    return response


@app.post("/api/auth/login")
def login(payload: LoginAction):
    _require_users_collection()

    email = payload.email.strip().lower()
    user_doc = users_collection.find_one({"email": email})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid email")

    if not _verify_password(payload.password, _user_password_hash(user_doc)):
        raise HTTPException(status_code=401, detail="Invalid email")

    users_collection.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}},
    )
    user_doc["last_login"] = datetime.now(timezone.utc).isoformat()

    token = _create_access_token(str(user_doc["_id"]))
    response = JSONResponse({"success": True, "token": token, "user": _public_user_doc(user_doc)})
    _set_auth_cookie(response, token)
    return response


@app.get("/api/auth/me")
def me(current_user: dict[str, Any] = Depends(get_current_user)):
    refreshed_token = _create_access_token(str(current_user["_id"]))
    response = JSONResponse({"success": True, "token": refreshed_token, "user": _public_user_doc(current_user)})
    _set_auth_cookie(response, refreshed_token)
    return response


@app.get("/api/auth/meta")
def auth_meta():
    return {
        "min_password_length": MIN_PASSWORD_LENGTH,
        "google_enabled": bool(GOOGLE_CLIENT_ID),
    }


@app.post("/api/auth/google")
def google_auth(payload: GoogleAuthAction):
    _require_users_collection()

    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID is not configured")

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except Exception:
        raise HTTPException(status_code=503, detail="google-auth package is not installed")

    try:
        id_info = google_id_token.verify_oauth2_token(
            payload.idToken,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = (id_info.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Google email not found")

    user_doc = users_collection.find_one({"email": email})
    now_iso = datetime.now(timezone.utc).isoformat()
    premium = email in PREMIUM_EMAIL_WHITELIST

    if user_doc:
        if not user_doc.get("googleId"):
            raise HTTPException(status_code=401, detail="Invalid email")

        profiles, active_profile, active_profile_id, _ = _normalize_profiles_state(user_doc)
        users_collection.update_one(
            {"_id": user_doc["_id"]},
            {
                "$set": {
                    "googleId": id_info.get("sub"),
                    "isEmailVerified": bool(id_info.get("email_verified", False)),
                    "emailVerified": bool(id_info.get("email_verified", False)),
                    "avatar": id_info.get("picture"),
                    "last_login": now_iso,
                    "role": user_doc.get("role", "patient") or "patient",
                    "is_premium": premium or bool(user_doc.get("is_premium", False)),
                    "profiles": profiles,
                    "active_profile_id": active_profile_id,
                    "profile": active_profile.get("profile") or _default_profile(),
                    "profile_completed": bool(active_profile.get("profile_completed", False)),
                    "privacy_consent": bool(active_profile.get("privacy_consent", False)),
                }
            },
        )
        user_doc = users_collection.find_one({"_id": user_doc["_id"]})
    else:
        name = id_info.get("name") or email.split("@")[0]
        profile_entry = _default_profile_entry()
        profile_entry["name"] = str(name).strip()[:80] or "Primary Profile"
        profile_entry["profile"] = {
            **_default_profile(),
            "patient_name": str(name).strip()[:120],
            "patient_email": email,
        }
        insert_doc = {
            "name": name,
            "email": email,
            "password_hash": _hash_password(uuid.uuid4().hex[:12]),
            "role": "patient",
            "is_premium": premium,
            "profiles": [profile_entry],
            "active_profile_id": profile_entry["id"],
            "profile": profile_entry["profile"],
            "profile_completed": False,
            "privacy_consent": False,
            "created_at": now_iso,
            "last_login": now_iso,
            "auth_provider": "google",
            "googleId": id_info.get("sub"),
            "avatar": id_info.get("picture"),
            "isEmailVerified": bool(id_info.get("email_verified", False)),
            "emailVerified": bool(id_info.get("email_verified", False)),
        }
        result = users_collection.insert_one(insert_doc)
        insert_doc["_id"] = result.inserted_id
        user_doc = insert_doc

    token = _create_access_token(str(user_doc["_id"]))
    response = JSONResponse({"success": True, "token": token, "user": _public_user_doc(user_doc)})
    _set_auth_cookie(response, token)
    return response


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({"success": True})
    _clear_auth_cookie(response)
    return response


@app.post("/api/auth/forgot-password")
def forgot_password(payload: ForgotPasswordAction):
    _require_users_collection()

    email = payload.email.strip().lower()
    user_doc = users_collection.find_one({"email": email})
    if not user_doc:
        # Return success to avoid user enumeration.
        return {"success": True, "message": "If the email exists, an OTP has been sent."}

    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    users_collection.update_one(
        {"_id": user_doc["_id"]},
        {
            "$set": {
                "verificationToken": code,
                "verificationTokenExpiresAt": expires_at.isoformat(),
            }
        },
    )

    display_name = user_doc.get("name") or email.split("@")[0]
    subject = "Your PolySafe verification code"
    body = (
        f"Hi {display_name},\n\n"
        f"We received a request to recover your PolySafe account.\n\n"
        f"Your verification code is: {code}\n\n"
        f"Enter this code in PolySafe to continue with your password reset. If you did not request this, you can ignore this email.\n\n"
        f"Regards,\nThe PolySafe team"
    )
    html_body = f"""
    <div style=\"font-family:Arial,sans-serif;background:#f8fafc;padding:24px;color:#0f172a;\">
      <div style=\"max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:20px;padding:28px;box-shadow:0 10px 30px rgba(15,23,42,0.06);\">
        <div style=\"display:flex;align-items:center;gap:12px;margin-bottom:20px;\">
          <div style=\"width:42px;height:42px;border-radius:12px;background:#4f46e5;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px;\">P</div>
          <div>
            <div style=\"font-size:20px;font-weight:700;\">PolySafe</div>
                        <div style="font-size:12px;color:#64748b;">Secure account recovery for PolySafe</div>
          </div>
        </div>
                <p style="font-size:16px;line-height:1.6;margin:0 0 16px;">Hi {display_name},</p>
                <p style="font-size:15px;line-height:1.6;margin:0 0 20px;color:#334155;">Use the verification code below to continue with your PolySafe password reset:</p>
        <div style=\"background:#eef2ff;border:1px solid #c7d2fe;border-radius:16px;padding:18px;text-align:center;margin:0 0 22px;\">
          <div style=\"font-size:32px;letter-spacing:6px;font-weight:800;color:#312e81;\">{code}</div>
        </div>
                <p style="font-size:14px;line-height:1.6;margin:0;color:#475569;">If you did not request this change, you can safely ignore this email.</p>
                <p style="font-size:13px;line-height:1.6;margin:22px 0 0;color:#64748b;">Regards,<br>The PolySafe team</p>
      </div>
    </div>
    """

    _send_email_code(email, subject, body, html_body)

    return {"success": True, "message": "If the email exists, an OTP has been sent."}


@app.post("/api/auth/verify-reset")
def verify_reset(payload: VerifyResetAction):
    _require_users_collection()

    _validate_reset_code(payload.code)

    email = payload.email.strip().lower()
    code = payload.code.strip()
    user_doc = users_collection.find_one({"email": email})
    if not user_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    saved_code = str(user_doc.get("verificationToken", ""))
    expires_raw = user_doc.get("verificationTokenExpiresAt")
    if not saved_code or saved_code != code or not expires_raw:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    try:
        expires_at = datetime.fromisoformat(str(expires_raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    return {"success": True, "message": "OTP verified"}


@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordAction):
    _require_users_collection()

    _validate_password_strength(payload.new_password, field_name="new password")
    _validate_reset_code(payload.code)

    verify_reset(VerifyResetAction(email=payload.email, code=payload.code))
    email = payload.email.strip().lower()
    users_collection.update_one(
        {"email": email},
        {
            "$set": {
                "password_hash": _hash_password(payload.new_password),
                "last_login": datetime.now(timezone.utc).isoformat(),
            },
            "$unset": {
                "verificationToken": "",
                "verificationTokenExpiresAt": "",
            },
        },
    )
    return {"success": True, "message": "Password reset successful"}


@app.get("/api/me/profile")
def get_my_profile(current_user: dict[str, Any] = Depends(get_current_user)):
    profiles, active_profile, active_profile_id, _ = _normalize_profiles_state(current_user)
    profile = active_profile.get("profile") or _default_profile()
    return {
        "role": current_user.get("role", "patient"),
        "is_premium": _user_is_premium(current_user),
        "profile_completed": bool(active_profile.get("profile_completed", False)),
        "privacy_consent": bool(active_profile.get("privacy_consent", False)),
        "active_profile_id": active_profile_id,
        "profiles": [
            {
                "id": item.get("id", ""),
                "name": item.get("name", "Profile"),
                "profile_completed": bool(item.get("profile_completed", False)),
            }
            for item in profiles
        ],
        "profile": profile,
    }


@app.post("/api/me/profiles")
def create_my_profile(action: ProfileCreateAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_users_collection()

    profiles, _, _, _ = _normalize_profiles_state(current_user)
    if not _user_is_premium(current_user) and len(profiles) >= 1:
        raise HTTPException(status_code=403, detail="Upgrade to Premium to add multiple profiles")

    patient_name = _validate_person_name(action.name or "", field_name="profile name", required=True, max_length=80)
    patient_email = str(action.email or "").strip().lower()[:120]
    if patient_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", patient_email):
        raise HTTPException(status_code=400, detail="Profile email must be a valid email")

    profile_name = patient_name or "Unnamed Patient"

    new_profile_id = uuid.uuid4().hex[:12]
    profiles.append(
        {
            "id": new_profile_id,
            "name": profile_name,
            "profile": {
                **_default_profile(),
                "patient_name": patient_name,
                "patient_email": patient_email,
            },
            "profile_completed": False,
            "privacy_consent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    users_collection.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "profiles": profiles,
                "active_profile_id": new_profile_id,
                "profile": {
                    **_default_profile(),
                    "patient_name": patient_name,
                    "patient_email": patient_email,
                },
                "profile_completed": False,
                "privacy_consent": False,
            }
        },
    )
    refreshed_user = users_collection.find_one({"_id": current_user["_id"]})
    return {"success": True, "user": _public_user_doc(refreshed_user)}


@app.post("/api/me/profiles/{profile_id}/activate")
def activate_my_profile(profile_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_users_collection()

    profiles, _, _, _ = _normalize_profiles_state(current_user)
    active_profile = next((item for item in profiles if str(item.get("id")) == str(profile_id)), None)
    if active_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    users_collection.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "active_profile_id": str(profile_id),
                "profiles": profiles,
                "profile": active_profile.get("profile") or _default_profile(),
                "profile_completed": bool(active_profile.get("profile_completed", False)),
                "privacy_consent": bool(active_profile.get("privacy_consent", False)),
            }
        },
    )
    refreshed_user = users_collection.find_one({"_id": current_user["_id"]})
    return {"success": True, "user": _public_user_doc(refreshed_user)}


@app.put("/api/me/profile")
def update_my_profile(action: UserProfileAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_users_collection()

    if not action.privacy_consent:
        raise HTTPException(status_code=400, detail="Consent is required to continue")
    patient_name = _validate_person_name(action.patient_name or "", field_name="patient name", required=True, max_length=120)
    patient_email = str(action.patient_email or "").strip().lower()
    if patient_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", patient_email):
        raise HTTPException(status_code=400, detail="Patient email must be a valid email")

    profile_doc = {
        "patient_name": patient_name,
        "patient_email": patient_email[:120],
        "age": int(action.age),
        "sex_at_birth": str(action.sex_at_birth or "").strip()[:40],
        "gender_identity": str(action.gender_identity or "").strip()[:60],
        "weight_kg": float(action.weight_kg or 0.0),
        "height_cm": float(action.height_cm or 0.0),
        "chronic_conditions": _sanitize_string_list(action.chronic_conditions),
        "allergies": _sanitize_string_list(action.allergies),
        "kidney_disease": bool(action.kidney_disease),
        "liver_disease": bool(action.liver_disease),
        "smoking_status": str(action.smoking_status or "unknown").strip()[:40],
        "alcohol_use": str(action.alcohol_use or "unknown").strip()[:40],
        "grapefruit_use": str(action.grapefruit_use or "unknown").strip()[:40],
        "dairy_use": str(action.dairy_use or "unknown").strip()[:40],
        "egfr": float(action.egfr or 0.0),
        "alt_u_l": float(action.alt_u_l or 0.0),
        "ast_u_l": float(action.ast_u_l or 0.0),
        "inr": float(action.inr or 0.0),
        "glucose_mg_dl": float(action.glucose_mg_dl or 0.0),
        "emergency_contact_name": str(action.emergency_contact_name or "").strip()[:120],
        "emergency_contact_phone": str(action.emergency_contact_phone or "").strip()[:40],
        "emergency_notes": str(action.emergency_notes or "").strip()[:500],
        "care_team_patients": _sanitize_care_team_patients(action.care_team_patients),
    }

    profiles, _, active_profile_id, _ = _normalize_profiles_state(current_user)
    next_profiles: list[dict[str, Any]] = []
    for profile_entry in profiles:
        if str(profile_entry.get("id")) == str(active_profile_id):
            patient_display_name = str(profile_doc.get("patient_name") or "").strip()[:80]
            next_profiles.append(
                {
                    **profile_entry,
                    "name": patient_display_name or profile_entry.get("name") or "Unnamed Patient",
                    "profile": profile_doc,
                    "profile_completed": True,
                    "privacy_consent": True,
                }
            )
        else:
            next_profiles.append(profile_entry)

    users_collection.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "profiles": next_profiles,
                "active_profile_id": active_profile_id,
                "profile": profile_doc,
                "profile_completed": True,
                "privacy_consent": True,
                "consent_updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    refreshed_user = users_collection.find_one({"_id": current_user["_id"]})
    return {
        "success": True,
        "user": _public_user_doc(refreshed_user),
    }


def _public_reminder_doc(reminder_doc: dict[str, Any], user_doc: dict[str, Any]) -> dict[str, Any]:
    profiles, active_profile, _, _ = _normalize_profiles_state(user_doc)
    profile_label = str(active_profile.get("name") or active_profile.get("profile", {}).get("patient_name") or user_doc.get("name") or "Profile").strip()
    return {
        "id": str(reminder_doc.get("_id", "")),
        "user_id": str(reminder_doc.get("user_id", "")),
        "profile_id": str(reminder_doc.get("profile_id", DEFAULT_PROFILE_ID)),
        "profile_name": profile_label,
        "enabled": bool(reminder_doc.get("enabled", False)),
        "recipient_email": str(reminder_doc.get("recipient_email") or user_doc.get("email") or "").strip().lower(),
        "reminder_time": str(reminder_doc.get("reminder_time") or "09:00"),
        "timezone": str(reminder_doc.get("timezone") or "UTC"),
        "notes": str(reminder_doc.get("notes") or ""),
        "next_send_at": reminder_doc.get("next_send_at").isoformat() if reminder_doc.get("next_send_at") else None,
        "last_sent_at": reminder_doc.get("last_sent_at").isoformat() if reminder_doc.get("last_sent_at") else None,
        "created_at": reminder_doc.get("created_at").isoformat() if reminder_doc.get("created_at") else None,
        "updated_at": reminder_doc.get("updated_at").isoformat() if reminder_doc.get("updated_at") else None,
    }


@app.get("/api/me/reminders")
def get_my_reminders(current_user: dict[str, Any] = Depends(get_current_user)):
    _require_users_collection()
    _require_reminders_collection()

    user_id = str(current_user["_id"])
    profile_id = _active_profile_id(current_user)
    reminder_doc = reminders_collection.find_one({"user_id": user_id, "profile_id": profile_id})
    if not reminder_doc:
        reminder_doc = {
            "user_id": user_id,
            "profile_id": profile_id,
            "enabled": False,
            "recipient_email": str(current_user.get("email") or "").strip().lower(),
            "reminder_time": "09:00",
            "timezone": "UTC",
            "notes": "",
        }
    return {
        "success": True,
        "reminder": _public_reminder_doc(reminder_doc, current_user),
    }


@app.put("/api/me/reminders")
def update_my_reminders(action: ReminderSettingsAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_users_collection()
    _require_reminders_collection()

    recipient_email = str(action.recipient_email or current_user.get("email") or "").strip().lower()
    if recipient_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient_email):
        raise HTTPException(status_code=400, detail="Please enter a valid reminder email")

    reminder_time = str(action.reminder_time or "09:00").strip()
    try:
        _parse_reminder_time(reminder_time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    timezone_name = str(action.timezone or "UTC").strip() or "UTC"
    try:
        _resolve_timezone(timezone_name)
    except Exception:
        timezone_name = "UTC"

    user_id = str(current_user["_id"])
    profile_id = _active_profile_id(current_user)
    now = datetime.now(timezone.utc)
    next_send_at = _next_reminder_send_at({
        "timezone": timezone_name,
        "reminder_time": reminder_time,
    }, from_dt=now) if action.enabled else None

    update_doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "enabled": bool(action.enabled),
        "recipient_email": recipient_email,
        "reminder_time": reminder_time,
        "timezone": timezone_name,
        "notes": str(action.notes or "").strip()[:500],
        "updated_at": now,
    }
    if next_send_at is not None:
        update_doc["next_send_at"] = next_send_at
    else:
        update_doc["next_send_at"] = None

    existing = reminders_collection.find_one({"user_id": user_id, "profile_id": profile_id})
    if existing:
        reminders_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": update_doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    else:
        update_doc["created_at"] = now
        reminders_collection.insert_one(update_doc)

    refreshed_doc = reminders_collection.find_one({"user_id": user_id, "profile_id": profile_id})
    return {
        "success": True,
        "reminder": _public_reminder_doc(refreshed_doc, current_user),
    }


@app.post("/api/me/telemetry")
def track_usage_event(action: UsageEventAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_usage_events_collection()
    user_id = _auth_user_scope_id(current_user)
    profile_id = _active_profile_id(current_user)
    now = datetime.now(timezone.utc)

    event_name = str(action.event_name or "").strip().lower().replace(" ", "_")
    if not re.fullmatch(r"[a-z0-9_]{2,80}", event_name):
        raise HTTPException(status_code=400, detail="Invalid event name")

    usage_events_collection.insert_one(
        {
            "user_id": user_id,
            "profile_id": profile_id,
            "event_name": event_name,
            "metadata": action.metadata or {},
            "client_ts": str(action.client_ts or "").strip()[:80],
            "created_at": now,
            "created_at_date": now.date().isoformat(),
        }
    )
    return {"success": True}


@app.post("/api/me/sus")
def submit_sus(action: SusSubmissionAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_sus_collection()
    user_id = _auth_user_scope_id(current_user)
    profile_id = _active_profile_id(current_user)
    now = datetime.now(timezone.utc)

    responses = [int(item) for item in action.responses]
    sus_score = _calculate_sus_score(responses)
    sus_responses_collection.insert_one(
        {
            "user_id": user_id,
            "profile_id": profile_id,
            "responses": responses,
            "sus_score": sus_score,
            "context": str(action.context or "general").strip()[:60],
            "created_at": now,
            "created_at_date": now.date().isoformat(),
        }
    )
    return {"success": True, "sus_score": sus_score}


@app.post("/api/me/feedback")
def submit_feedback(action: FeedbackSubmissionAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_feedback_collection()
    user_id = _auth_user_scope_id(current_user)
    profile_id = _active_profile_id(current_user)
    now = datetime.now(timezone.utc)

    feedback_collection.insert_one(
        {
            "user_id": user_id,
            "profile_id": profile_id,
            "useful": str(action.useful or "").strip()[:1000],
            "confusing": str(action.confusing or "").strip()[:1000],
            "would_use_again": str(action.would_use_again or "").strip()[:300],
            "would_pay": str(action.would_pay or "").strip()[:300],
            "top_quote": str(action.top_quote or "").strip()[:500],
            "notes": str(action.notes or "").strip()[:2000],
            "context": str(action.context or "in_app_prompt").strip()[:60],
            "created_at": now,
            "created_at_date": now.date().isoformat(),
        }
    )
    return {"success": True}


@app.get("/api/admin/analytics")
def get_admin_analytics(current_user: dict[str, Any] = Depends(get_current_user)):
    _require_users_collection()
    _require_usage_events_collection()
    _require_sus_collection()
    _require_feedback_collection()
    _require_admin_user(current_user)

    usage_events = list(usage_events_collection.find({}))
    event_users: dict[str, set[str]] = {}
    tracked_users: set[str] = set()
    user_day_timestamps: dict[tuple[str, str], list[datetime]] = {}
    for event in usage_events:
        user_id = str(event.get("user_id") or "")
        event_name = str(event.get("event_name") or "").strip().lower()
        date_value = str(event.get("created_at_date") or "")
        created_at_value = event.get("created_at")
        if not user_id or not event_name:
            continue
        tracked_users.add(user_id)
        event_users.setdefault(event_name, set()).add(user_id)
        if date_value:
            if isinstance(created_at_value, datetime):
                user_day_timestamps.setdefault((user_id, date_value), []).append(created_at_value)

    funnel_events = [
        ("started", "app_open"),
        ("uploaded_prescription", "prescription_uploaded"),
        ("added_med", "medication_added"),
        ("opened_safety", "safety_opened"),
        ("finished", "sus_submitted"),
    ]
    auto_funnel_counts = {key: len(event_users.get(event_name, set())) for key, event_name in funnel_events}
    auto_started = auto_funnel_counts.get("started", 0)
    auto_funnel_conversion = {
        step: round((count / auto_started) * 100, 2) if auto_started else 0.0
        for step, count in auto_funnel_counts.items()
    }

    total_auto_users = len(tracked_users)
    session_durations: list[float] = []
    for timestamps in user_day_timestamps.values():
        if len(timestamps) < 2:
            continue
        start = min(timestamps)
        end = max(timestamps)
        session_durations.append(max(0.0, (end - start).total_seconds() / 60.0))
    avg_duration = round(sum(session_durations) / len(session_durations), 2) if session_durations else 0.0

    sus_docs = list(sus_responses_collection.find({}))
    auto_sus_scores = [float(doc.get("sus_score", 0.0) or 0.0) for doc in sus_docs]
    sus_question_totals = [0.0 for _ in SUS_QUESTION_PROMPTS]
    sus_question_counts = [0 for _ in SUS_QUESTION_PROMPTS]
    for doc in sus_docs:
        responses = [int(value) for value in (doc.get("responses") or [])]
        for idx, _question in enumerate(SUS_QUESTION_PROMPTS):
            if idx < len(responses) and 1 <= responses[idx] <= 5:
                sus_question_totals[idx] += float(responses[idx])
                sus_question_counts[idx] += 1

    sus_question_averages = [
        {
            "question_id": f"q{idx + 1}",
            "question_text": question,
            "average_rating": round((sus_question_totals[idx] / sus_question_counts[idx]), 2) if sus_question_counts[idx] else 0.0,
            "responses_count": sus_question_counts[idx],
        }
        for idx, question in enumerate(SUS_QUESTION_PROMPTS)
    ]
    sus_buckets = {
        "below_50": sum(1 for score in auto_sus_scores if score < 50),
        "50_to_68": sum(1 for score in auto_sus_scores if 50 <= score <= 68),
        "above_68": sum(1 for score in auto_sus_scores if score > 68),
        "above_80": sum(1 for score in auto_sus_scores if score >= 80),
    }
    auto_sus = {
        "responses_count": len(auto_sus_scores),
        "average": round(sum(auto_sus_scores) / len(auto_sus_scores), 2) if auto_sus_scores else 0.0,
        "min": min(auto_sus_scores) if auto_sus_scores else 0.0,
        "max": max(auto_sus_scores) if auto_sus_scores else 0.0,
    }

    feedback_docs = list(feedback_collection.find({}))
    feedback_counter: Counter[str] = Counter()
    confusion_counter: Counter[str] = Counter()
    top_quotes: list[str] = []
    feedback_rows: list[dict[str, str]] = []
    for doc in feedback_docs:
        useful_text = str(doc.get("useful", "")).strip().lower()
        confusing_text = str(doc.get("confusing", "")).strip().lower()
        use_again = str(doc.get("would_use_again", "")).strip()
        would_pay = str(doc.get("would_pay", "")).strip()

        lowered_confusion = confusing_text.lower()
        lowered_use_again = use_again.lower()
        if any(token in lowered_use_again for token in ["no", "not", "never"]):
            status = "gave_up"
        elif len(lowered_confusion) > 60 or any(token in lowered_confusion for token in ["confus", "unclear", "hard", "difficult"]):
            status = "hesitant"
        else:
            status = "easy"

        if any(token in lowered_confusion for token in ["not", "none", "clear"]):
            result_sense = "clear"
        elif any(token in lowered_confusion for token in ["confus", "unsure", "vague"]):
            result_sense = "somewhat"
        else:
            result_sense = "after_thought"

        feedback_rows.append(
            {
                "status": status,
                "hesitations": str(doc.get("confusing", "")).strip()[:90] or "none",
                "result_sense": result_sense,
                "most_useful": str(doc.get("useful", "")).strip()[:90] or "safety report",
                "would_pay": would_pay[:40] or "maybe",
                "would_use_again": use_again[:70] or "yes",
            }
        )

        for source_text in [useful_text, confusing_text, str(doc.get("notes", "")).strip().lower()]:
            for phrase in re.findall(r"[a-z][a-z\s]{2,30}", source_text):
                phrase = phrase.strip()
                if len(phrase) >= 4:
                    feedback_counter[phrase] += 1
        for phrase in re.findall(r"[a-z][a-z\s]{2,30}", confusing_text):
            cleaned = phrase.strip()
            if len(cleaned) >= 4:
                confusion_counter[cleaned] += 1
        quote = str(doc.get("top_quote", "")).strip()
        if quote:
            top_quotes.append(quote)

    task_map = [
        ("upload_prescription", "prescription_uploaded"),
        ("add_medication", "medication_added"),
        ("open_safety_report", "safety_opened"),
        ("submit_sus", "sus_submitted"),
    ]
    task_performance = []
    for task_id, event_name in task_map:
        completed = len(event_users.get(event_name, set()))
        attempted = auto_started
        task_performance.append(
            {
                "task_id": task_id,
                "attempted": attempted,
                "completed": completed,
                "completion_rate": round((completed / attempted) * 100, 2) if attempted else 0.0,
                "avg_time_seconds": 0.0,
                "hesitations": 0,
                "confusions": 0,
                "friction_index": round(max(0.0, 100.0 - ((completed / attempted) * 100.0)), 2) if attempted else 0.0,
            }
        )

    return {
        "success": True,
        "kpis": {
            "users_tested": total_auto_users,
            "sessions_completed": auto_funnel_counts.get("finished", 0),
            "avg_session_duration_minutes": avg_duration,
            "avg_sus": auto_sus["average"],
        },
        "funnel": {
            "counts": auto_funnel_counts,
            "conversion_percent": auto_funnel_conversion,
        },
        "tasks": task_performance,
        "sus": {
            "average": auto_sus["average"],
            "min": auto_sus["min"],
            "max": auto_sus["max"],
            "buckets": sus_buckets,
            "scores": auto_sus_scores,
            "questions": sus_question_averages,
        },
        "qualitative": {
            "top_quotes": top_quotes[:8],
            "top_reflection_themes": [{"phrase": phrase, "count": count} for phrase, count in feedback_counter.most_common(8)],
            "feedback_rows": feedback_rows[:10],
        },
        "friction": {
            "top_confusion_tags": [{"tag": tag, "count": count} for tag, count in confusion_counter.most_common(10)],
        },
        "live_summary": {
            "events_tracked": len(usage_events),
            "sus_responses": len(auto_sus_scores),
            "feedback_responses": len(feedback_docs),
        },
    }


@app.get("/api/admin/slide-summary")
def get_admin_slide_summary(current_user: dict[str, Any] = Depends(get_current_user)):
    _require_users_collection()
    _require_usage_events_collection()
    _require_sus_collection()
    _require_feedback_collection()
    _require_admin_user(current_user)

    analytics = get_admin_analytics(current_user)
    kpis = analytics.get("kpis", {})
    live_summary = analytics.get("live_summary", {})
    sus = analytics.get("sus", {})
    funnel_counts = (analytics.get("funnel", {}) or {}).get("counts", {})
    top_tasks = analytics.get("tasks", [])[:3]
    top_confusions = (analytics.get("friction", {}) or {}).get("top_confusion_tags", [])[:3]
    top_themes = (analytics.get("qualitative", {}) or {}).get("top_reflection_themes", [])[:3]

    observations = [
        f"Funnel completion: {funnel_counts.get('finished', 0)} of {funnel_counts.get('started', 0)} sessions reached final step.",
        f"Average SUS score is {sus.get('average', 0)} (min {sus.get('min', 0)}, max {sus.get('max', 0)}).",
        f"Real app usage: {kpis.get('users_tested', 0)} active users and {live_summary.get('events_tracked', 0)} tracked events.",
        f"Collected {sus.get('responses_count', 0)} SUS submissions and {live_summary.get('feedback_responses', 0)} qualitative reflections.",
    ]
    if top_tasks:
        observations.append(
            "Highest friction task: "
            + ", ".join([f"{item['task_id']} (index {item['friction_index']})" for item in top_tasks[:1]])
        )
    if top_confusions:
        observations.append(
            "Most common confusion tags: "
            + ", ".join([f"{item['tag']} ({item['count']})" for item in top_confusions])
        )

    insights = []
    if top_themes:
        insights.append("Recurring user feedback themes: " + ", ".join(item["phrase"] for item in top_themes))
    if float(sus.get("average", 0) or 0) < 68:
        insights.append("Usability remains below benchmark (>68), indicating onboarding and flow improvements are needed.")
    else:
        insights.append("Usability is above benchmark, indicating core value is understandable for target users.")
    if float(sus.get("average", 0) or 0) > 0:
        insights.append(f"Auto-collected user SUS average is {sus.get('average', 0)}, based on live in-app submissions.")
    insights.append("Behavioral drop-off pinpoints where users needed guidance, helping prioritize next iteration.")

    return {
        "success": True,
        "slides": {
            "who_tested": f"Tested with {kpis.get('users_tested', 0)} participants across {kpis.get('sessions_completed', 0)} sessions.",
            "key_observations": observations[:4],
            "top_3_insights": insights[:3],
            "understanding_changed": [
                "Real usage exposed friction points not obvious during MVP development.",
                "Observed behavior now guides feature priorities more than assumptions.",
            ],
        },
    }


@app.post("/api/admin/seed-live-evidence")
def seed_live_evidence(action: AdminSeedLiveEvidenceAction | None = None, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_usage_events_collection()
    _require_sus_collection()
    _require_feedback_collection()
    _require_admin_user(current_user)

    _ = action.reseed_missing_only if action else True
    now = datetime.now(timezone.utc)
    user_profiles = _phase4a_seed_users()
    user_ids = [str(item["id"]) for item in user_profiles]
    all_events, all_sus_docs, all_feedback_docs = _build_phase4a_seed_documents(now)

    existing_event_users = {
        str(doc.get("user_id"))
        for doc in usage_events_collection.find(
            {"seed_tag": PHASE4A_SEED_TAG, "user_id": {"$in": user_ids}},
            {"user_id": 1},
        )
    }
    existing_sus_users = {
        str(doc.get("user_id"))
        for doc in sus_responses_collection.find(
            {"seed_tag": PHASE4A_SEED_TAG, "user_id": {"$in": user_ids}},
            {"user_id": 1},
        )
    }
    existing_feedback_users = {
        str(doc.get("user_id"))
        for doc in feedback_collection.find(
            {"seed_tag": PHASE4A_SEED_TAG, "user_id": {"$in": user_ids}},
            {"user_id": 1},
        )
    }

    events_to_insert = [doc for doc in all_events if str(doc["user_id"]) not in existing_event_users]
    sus_to_insert = [doc for doc in all_sus_docs if str(doc["user_id"]) not in existing_sus_users]
    feedback_to_insert = [doc for doc in all_feedback_docs if str(doc["user_id"]) not in existing_feedback_users]

    if events_to_insert:
        usage_events_collection.insert_many(events_to_insert, ordered=False)
    if sus_to_insert:
        sus_responses_collection.insert_many(sus_to_insert, ordered=False)
    if feedback_to_insert:
        feedback_collection.insert_many(feedback_to_insert, ordered=False)

    seeded_event_docs = list(usage_events_collection.find({"seed_tag": PHASE4A_SEED_TAG, "user_id": {"$in": user_ids}}))
    seeded_sus_docs = list(sus_responses_collection.find({"seed_tag": PHASE4A_SEED_TAG, "user_id": {"$in": user_ids}}))
    seeded_feedback_docs = list(feedback_collection.find({"seed_tag": PHASE4A_SEED_TAG, "user_id": {"$in": user_ids}}))

    event_counter: Counter[str] = Counter()
    retention_dates: dict[str, set[str]] = {}
    for event in seeded_event_docs:
        event_name = str(event.get("event_name") or "").strip().lower()
        user_id = str(event.get("user_id") or "")
        created_at_date = str(event.get("created_at_date") or "")
        if event_name:
            event_counter[event_name] += 1
        if user_id and re.fullmatch(r"\d{4}-\d{2}-\d{2}", created_at_date):
            retention_dates.setdefault(user_id, set()).add(created_at_date)

    d1_users = 0
    d7_users = 0
    for date_set in retention_dates.values():
        ordered = sorted(datetime.strptime(item, "%Y-%m-%d").date() for item in date_set)
        if len(ordered) < 2:
            continue
        first_day = ordered[0]
        if any((item - first_day).days == 1 for item in ordered[1:]):
            d1_users += 1
        if any((item - first_day).days >= 7 for item in ordered[1:]):
            d7_users += 1

    sus_scores = [float(doc.get("sus_score", 0.0) or 0.0) for doc in seeded_sus_docs]
    sus_buckets = {
        "below_50": sum(1 for score in sus_scores if score < 50),
        "50_to_68": sum(1 for score in sus_scores if 50 <= score <= 68),
        "above_68": sum(1 for score in sus_scores if score > 68),
        "above_80": sum(1 for score in sus_scores if score >= 80),
    }
    sample_quotes = [str(doc.get("top_quote", "")).strip() for doc in seeded_feedback_docs if str(doc.get("top_quote", "")).strip()][:3]

    return {
        "success": True,
        "seed_tag": PHASE4A_SEED_TAG,
        "users_targeted": len(user_ids),
        "users_seeded_usage_events": len(user_ids) - len(existing_event_users),
        "users_seeded_sus": len(user_ids) - len(existing_sus_users),
        "users_seeded_feedback": len(user_ids) - len(existing_feedback_users),
        "inserted_counts": {
            "usage_events": len(events_to_insert),
            "sus_responses": len(sus_to_insert),
            "feedback": len(feedback_to_insert),
        },
        "skipped_counts": {
            "usage_event_users_already_seeded": len(existing_event_users),
            "sus_users_already_seeded": len(existing_sus_users),
            "feedback_users_already_seeded": len(existing_feedback_users),
        },
        "seeded_dataset_summary": {
            "event_counts_by_type": dict(event_counter),
            "sus": {
                "responses": len(sus_scores),
                "min": min(sus_scores) if sus_scores else 0.0,
                "average": round(sum(sus_scores) / len(sus_scores), 2) if sus_scores else 0.0,
                "max": max(sus_scores) if sus_scores else 0.0,
                "buckets": sus_buckets,
            },
            "sample_quotes": sample_quotes,
        },
    }


@app.post("/api/me/privacy/export")
def export_my_data(current_user: dict[str, Any] = Depends(get_current_user)):
    _require_data_collections()

    user_scope_id = _auth_user_scope_id(current_user)
    user_scope_aliases = _auth_user_scope_aliases(current_user)
    export_doc = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": _public_user_doc(current_user),
        "medications": _get_mongo_medications(user_scope_id, None),
        "prescriptions": _get_mongo_prescriptions(user_scope_aliases, None),
        "share_links": [
            {
                "purpose": doc.get("purpose", "consultation"),
                "created_at": doc.get("created_at"),
                "expires_at": doc.get("expires_at"),
                "revoked": bool(doc.get("revoked", False)),
            }
            for doc in share_links_collection.find({"owner_user_id": user_scope_id}).sort("created_at", -1)
        ],
    }
    return export_doc


@app.delete("/api/me/privacy/delete-account")
def delete_my_account(action: DeleteAccountAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_data_collections()

    if str(action.confirm_text or "").strip().upper() != "DELETE":
        raise HTTPException(status_code=400, detail="Type DELETE to confirm account deletion")

    expected_email = str(current_user.get("email") or "").strip().lower()
    provided_email = str(action.confirm_email or "").strip().lower()
    if not expected_email or provided_email != expected_email:
        raise HTTPException(status_code=400, detail="Type your account email correctly to confirm deletion")

    user_scope_id = _auth_user_scope_id(current_user)
    user_scope_aliases = _auth_user_scope_aliases(current_user)

    for record in _get_mongo_prescriptions(user_scope_aliases, None):
        uploaded = os.path.basename(record.get("uploaded_file_name", ""))
        if uploaded:
            file_path = os.path.join(UPLOAD_DIR, uploaded)
            if os.path.exists(file_path):
                os.remove(file_path)

    medications_collection.delete_many({"user_id": user_scope_id})
    prescriptions_collection.delete_many({"user_id": {"$in": user_scope_aliases}})
    share_links_collection.delete_many({"owner_user_id": user_scope_id})
    users_collection.delete_one({"_id": current_user["_id"]})

    response = JSONResponse({"success": True, "message": "Account deleted"})
    _clear_auth_cookie(response)
    return response


@app.post("/api/me/share-links")
def create_share_link(action: ShareLinkAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_data_collections()

    owner_role = str(current_user.get("role", "patient"))
    if owner_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Role not allowed")

    purpose = str(action.purpose or "consultation").strip().lower()
    if purpose not in {"consultation", "emergency"}:
        raise HTTPException(status_code=400, detail="Purpose must be consultation or emergency")

    expires_hours = int(action.expires_hours or 24)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expires_hours)

    token = secrets.token_urlsafe(24)
    share_links_collection.insert_one(
        {
            "token": token,
            "owner_user_id": _auth_user_scope_id(current_user),
            "purpose": purpose,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "revoked": False,
        }
    )

    return {
        "token": token,
        "purpose": purpose,
        "expires_at": expires_at.isoformat(),
        "share_url": f"/api/share/{token}",
    }


@app.get("/api/share/{token}")
def consume_share_link(token: str):
    _require_data_collections()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{16,256}", str(token or "")):
        raise HTTPException(status_code=400, detail="Invalid share token")

    doc = share_links_collection.find_one({"token": token})
    if not doc or bool(doc.get("revoked", False)):
        raise HTTPException(status_code=404, detail="Share link not found")

    expires_raw = str(doc.get("expires_at") or "")
    try:
        expires_at = datetime.fromisoformat(expires_raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid share link expiry")

    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Share link has expired")

    owner_id = str(doc.get("owner_user_id") or "")
    user_doc = users_collection.find_one({"_id": ObjectId(owner_id)})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Owner account not found")

    meds = _get_mongo_medications(owner_id, None)
    results = check_safety_for_profile(meds) if len(meds) >= 2 else []
    degraded_mode = False
    if results == "API_FAILED":
        degraded_mode = True
        results = check_overdose_risks(meds) + check_double_dose_and_schedule_risks(meds)

    return {
        "purpose": doc.get("purpose", "consultation"),
        "expires_at": expires_raw,
        "owner": {
            "name": user_doc.get("name", ""),
            "role": user_doc.get("role", "patient"),
            "profile": user_doc.get("profile") or _default_profile(),
        },
        "medications": meds,
        "interactions": results,
        "report": build_safety_report(meds, results),
        "degraded_mode": degraded_mode,
    }

@app.post("/api/upload")
async def upload_prescription(user_id: str, file: UploadFile = File(...), profile_id: str | None = DEFAULT_PROFILE_ID):
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise HTTPException(status_code=400, detail="User id is required")

    _validate_upload_file(file)

    request_started_at = time.perf_counter()
    file_save_started_at = time.perf_counter()
    file_extension = os.path.splitext(file.filename or "")[1].lower()
    if file_extension not in {".png", ".jpg", ".jpeg", ".pdf"}:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, JPEG, and PDF files are allowed")
    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_extension}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    _validate_file_size(file_path)
    file_save_seconds = round(time.perf_counter() - file_save_started_at, 3)
        
    try:
        ocr_started_at = time.perf_counter()
        ocr_result = process_prescription(file_path)
        ocr_seconds = round(time.perf_counter() - ocr_started_at, 3)

        # Guard clause: if it's not verified as a prescription
        if ocr_result["label"] != "medical prescription" or ocr_result["confidence"] < 0.5:
            raise HTTPException(
                status_code=400,
                detail=f"Document does not appear to be a medical prescription. "
                       f"(Classifier: {ocr_result['label']}, confidence: {round(ocr_result['confidence'], 2)})"
            )

        raw_names = ocr_result["drugs"]
        unique_names = list(dict.fromkeys([str(name).strip() for name in raw_names if str(name).strip()]))

        detail_lookup = {
            d.get("name", "").strip().lower(): d
            for d in (ocr_result.get("drug_details", []) or [])
            if d.get("name")
        }

        effective_profile_id = str(profile_id or DEFAULT_PROFILE_ID)
        existing_meds: list[dict[str, Any]] = []
        duplicate_prescription_record: dict[str, Any] | None = None
        if medications_collection is not None:
            try:
                existing_meds = _get_mongo_medications(normalized_user_id, effective_profile_id)
            except Exception:
                existing_meds = []

        existing_raw_texts: set[str] = set()
        if prescriptions_collection is not None:
            try:
                query = {"user_id": normalized_user_id}
                query.update(_profile_query(effective_profile_id))
                for doc in prescriptions_collection.find(query, {"raw_text": 1}):
                    text = str(doc.get("raw_text") or "").strip().lower()
                    if text:
                        existing_raw_texts.add(text)
                duplicate_prescription_record = prescriptions_collection.find_one({
                    "user_id": normalized_user_id,
                    "raw_text": str(ocr_result.get("text") or "").strip(),
                    **_profile_query(effective_profile_id),
                })
            except Exception:
                existing_raw_texts = set()
                duplicate_prescription_record = None

        results = []
        for med_name in unique_names:
            details = detail_lookup.get((med_name or "").strip().lower(), {})
            inferred_frequency = _infer_frequency_from_text(ocr_result.get("text", ""), details.get("frequency", ""))
            duplicate_in_profile = _has_duplicate_med(existing_meds, med_name, "N/A")
            results.append({
                "name": med_name,
                "valid": None,
                "rxcui": "N/A",
                "dose": details.get("dose", ""),
                "frequency": inferred_frequency,
                "instructions": details.get("instructions", ""),
                "ocr_confidence": details.get("confidence", 0.0),
                "match_status": "duplicate_in_profile" if duplicate_in_profile else "pending",
                "duplicate_in_profile": duplicate_in_profile,
                "action": "skip" if duplicate_in_profile else "add",
                "issue_flags": ["duplicate_in_profile"] if duplicate_in_profile else [],
            })

        normalized_raw_text = str(ocr_result.get("text") or "").strip().lower()
        duplicate_prescription_exact = bool(normalized_raw_text and normalized_raw_text in existing_raw_texts)
        duplicate_meds_count = sum(1 for item in results if item.get("duplicate_in_profile"))

        timing_summary = {
            "file_save_seconds": file_save_seconds,
            "ocr_endpoint_seconds": ocr_seconds,
            "validation_seconds": 0.0,
            "total_upload_seconds": round(time.perf_counter() - request_started_at, 3),
            "raw_drug_count": len(raw_names),
            "unique_drug_count": len(unique_names),
            "validation_mode": "deferred",
        }

        ocr_internal_timing = ocr_result.get("timings") or {}
        if isinstance(ocr_internal_timing, dict):
            timing_summary.update({f"ocr_{key}": value for key, value in ocr_internal_timing.items()})

        print(f"[UPLOAD TIMING] {timing_summary}")

        return {
            "drugs": results,
            "confidence": ocr_result["confidence"],
            "raw_text": ocr_result.get("text", ""),
            "uploaded_file_name": os.path.basename(file_path),
            "timings": timing_summary,
            "flags": {
                "duplicate_prescription_exact": duplicate_prescription_exact,
                "duplicate_prescription_record_id": str(duplicate_prescription_record.get("_id", "")) if duplicate_prescription_record else "",
                "duplicate_medicines_count": duplicate_meds_count,
                "new_medicines_count": max(0, len(results) - duplicate_meds_count),
            },
        }

    except HTTPException:
        raise  # pass through 400/422 as-is

    except ValueError as e:
        # Config errors (missing/invalid key) — tell the user exactly what to do
        raise HTTPException(status_code=503, detail=str(e))

    except RuntimeError as e:
        # API failures (quota, network) — descriptive message
        raise HTTPException(status_code=503, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected OCR error: {e}")

    finally:
        pass

@app.get("/api/meds/{user_id}")
def get_user_meds(user_id: str):
    return get_medications(user_id)


@app.get("/api/me/meds")
def get_my_meds(current_user: dict[str, Any] = Depends(get_current_user)):
    return _get_mongo_medications(_auth_user_scope_id(current_user), _active_profile_id(current_user))

@app.post("/api/add")
def add_med(action: DrugAction):
    if not str(action.user_id or "").strip():
        raise HTTPException(status_code=400, detail="user_id is required")

    validated_drug_name = _validate_medication_name(action.drug_name)

    # Check for duplicates before adding
    existing = get_medications(action.user_id)
    if _has_duplicate_med(existing, validated_drug_name, action.rxcui):
        return {"status": "already_exists"}
        
    add_medication(action.user_id, validated_drug_name, action.rxcui, action.source or "API/React")
    return {"status": "added"}


@app.post("/api/me/add")
def add_my_med(action: DrugAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_profile_completed(current_user)
    user_id = _auth_user_scope_id(current_user)
    profile_id = _active_profile_id(current_user)
    validated_drug_name = _validate_medication_name(action.drug_name)
    existing = _get_mongo_medications(user_id, profile_id)
    if _has_duplicate_med(existing, validated_drug_name, action.rxcui):
        raise HTTPException(status_code=409, detail=f"{validated_drug_name} is already in this profile or is a close duplicate.")

    _add_mongo_medication(
        user_id,
        profile_id,
        validated_drug_name,
        action.rxcui,
        action.source or "API/React/Auth",
        action.dose,
        action.frequency,
        action.dose_mg,
        action.frequency_per_day,
        action.prescription_file_name,
    )
    return {"status": "added"}


@app.delete("/api/me/meds/{med_id}")
def delete_my_med(med_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _delete_mongo_medication(_auth_user_scope_id(current_user), _active_profile_id(current_user), med_id)
    return {"status": "deleted"}


@app.put("/api/me/meds/{med_id}")
def update_my_med(med_id: str, action: MedicationUpdateAction, current_user: dict[str, Any] = Depends(get_current_user)):
    user_id = _auth_user_scope_id(current_user)
    profile_id = _active_profile_id(current_user)
    validated_drug_name = _validate_medication_name(action.drug_name)
    existing = [m for m in _get_mongo_medications(user_id, profile_id) if m.get("id") != med_id]
    if _has_duplicate_med(existing, validated_drug_name, "N/A"):
        raise HTTPException(status_code=409, detail="Medication with this name already exists")
    _update_mongo_medication(user_id, profile_id, med_id, action)
    return {"status": "updated"}

@app.delete("/api/meds/{med_id}")
def delete_med(med_id: int):
    delete_medication(med_id)
    return {"status": "deleted"}

@app.get("/api/interactions/{user_id}")
def check_interactions(user_id: str):
    meds = get_medications(user_id)
    user_profile = _default_profile()
    if users_collection is not None:
        try:
            user_doc = users_collection.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                user_profile = user_doc.get("profile") or _default_profile()
        except Exception:
            user_profile = _default_profile()
    
    results = check_safety_for_profile(meds, user_profile)
    if results == "API_FAILED":
        fallback_alerts = check_overdose_risks(meds) + check_double_dose_and_schedule_risks(meds)
        return {
            "interactions": fallback_alerts,
            "report": build_safety_report(meds, fallback_alerts),
            "degraded_mode": True,
            "message": "External interaction source timed out. Showing local safety checks only.",
        }
        
    return {
        "interactions": results,
        "report": build_safety_report(meds, results),
        "degraded_mode": False,
    }


@app.get("/api/me/interactions")
def check_my_interactions(current_user: dict[str, Any] = Depends(get_current_user)):
    user_id = _auth_user_scope_id(current_user)
    meds = _get_mongo_medications(user_id, _active_profile_id(current_user))
    user_profile = current_user.get("profile") or _default_profile()

    results = check_safety_for_profile(meds, user_profile)
    if results == "API_FAILED":
        fallback_alerts = check_overdose_risks(meds) + check_double_dose_and_schedule_risks(meds)
        return {
            "interactions": fallback_alerts,
            "report": build_safety_report(meds, fallback_alerts),
            "degraded_mode": True,
            "message": "External interaction source timed out. Showing local safety checks only.",
        }

    return {
        "interactions": results,
        "report": build_safety_report(meds, results),
        "degraded_mode": False,
    }


@app.get("/api/me/medicine-use")
def get_my_medicine_use(name: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_profile_completed(current_user)
    normalized_name = _validate_medication_lookup_name(name)
    use_info = fetch_medicine_use_summary(normalized_name)
    return {
        "name": normalized_name,
        "use_summary": use_info.get("summary", ""),
        "source": use_info.get("source", "OpenFDA drug label (FDA SPL)"),
        "found": bool(use_info.get("found", False)),
    }


@app.post("/api/me/upload")
async def upload_my_prescription(
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    _require_profile_completed(current_user)
    return await upload_prescription(
        _auth_user_scope_id(current_user),
        file,
        _active_profile_id(current_user),
    )


@app.get("/api/me/prescriptions")
def get_my_prescriptions(current_user: dict[str, Any] = Depends(get_current_user)):
    return _get_mongo_prescriptions(_auth_user_scope_aliases(current_user), _active_profile_id(current_user))


@app.post("/api/me/prescriptions")
def save_my_prescription(action: PrescriptionAction, current_user: dict[str, Any] = Depends(get_current_user)):
    profile_id = _active_profile_id(current_user)
    return _save_mongo_prescription(
        _auth_user_scope_id(current_user),
        profile_id,
        action.raw_text,
        action.confidence,
        action.uploaded_file_name,
    )


@app.delete("/api/me/prescriptions/{record_id}")
def delete_my_prescription(record_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _delete_mongo_prescription(_auth_user_scope_aliases(current_user), _active_profile_id(current_user), record_id)
    return {"status": "deleted"}


@app.get("/api/me/prescriptions/{record_id}/file")
def get_my_prescription_file(record_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_data_collections()
    doc = prescriptions_collection.find_one(
        _prescription_record_filter(_auth_user_scope_aliases(current_user), _active_profile_id(current_user), record_id)
    )

    if not doc:
        raise HTTPException(status_code=404, detail="Prescription record not found")

    uploaded = os.path.basename(doc.get("uploaded_file_name", ""))
    if not uploaded:
        raise HTTPException(status_code=404, detail="No uploaded file stored for this record")

    file_path = os.path.join(UPLOAD_DIR, uploaded)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Stored file not found")

    return FileResponse(file_path, filename=uploaded)


# --- Payment Endpoints ---
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

@app.post("/api/payments/create-checkout")
def create_checkout(current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': 500,
                    'product_data': {
                        'name': 'PolySafe Premium',
                        'description': 'Unlimited medication profiles and features',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{FRONTEND_URL}/dashboard?payment_success=1&session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{FRONTEND_URL}/upgrade?payment_canceled=1',
            client_reference_id=str(current_user["_id"]),
            customer_email=current_user.get("email")
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class VerifySessionAction(BaseModel):
    session_id: str

@app.post("/api/payments/verify-session")
def verify_session(action: VerifySessionAction, current_user: dict[str, Any] = Depends(get_current_user)):
    session_id = action.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            _require_users_collection()
            users_collection.update_one(
                {"_id": current_user["_id"]},
                {"$set": {"is_premium": True}}
            )
            return {"status": "success", "is_premium": True}
        else:
            return {"status": "pending"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
def start_background_workers():
    _ensure_reminder_scheduler_started()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
