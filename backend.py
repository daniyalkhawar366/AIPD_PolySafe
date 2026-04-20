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
from utils import validate_drug
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
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        mongo_db = mongo_client[MONGO_DB_NAME]
        users_collection = mongo_db["users"]
        medications_collection = mongo_db["medications"]
        prescriptions_collection = mongo_db["prescriptions"]
        share_links_collection = mongo_db["share_links"]
        reminders_collection = mongo_db["reminders"]
        users_collection.create_index("email", unique=True)
        medications_collection.create_index([("user_id", 1), ("rxcui", 1)])
        medications_collection.create_index([("user_id", 1), ("drug_name", 1)])
        prescriptions_collection.create_index([("user_id", 1), ("date_added", -1)])
        share_links_collection.create_index([("token", 1)], unique=True)
        share_links_collection.create_index([("owner_user_id", 1), ("created_at", -1)])
        share_links_collection.create_index([("expires_at", 1)])
        reminders_collection.create_index([("user_id", 1), ("profile_id", 1)], unique=True)
        reminders_collection.create_index([("enabled", 1), ("next_send_at", 1)])
    except PyMongoError:
        users_collection = None
        medications_collection = None
        prescriptions_collection = None
        share_links_collection = None
        reminders_collection = None

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
