from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import shutil
import os
import uuid
import random
import secrets
import smtplib
from typing import Any
from pydantic import BaseModel, EmailStr
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

mongo_client = None
users_collection = None
medications_collection = None
prescriptions_collection = None
share_links_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        mongo_db = mongo_client[MONGO_DB_NAME]
        users_collection = mongo_db["users"]
        medications_collection = mongo_db["medications"]
        prescriptions_collection = mongo_db["prescriptions"]
        share_links_collection = mongo_db["share_links"]
        users_collection.create_index("email", unique=True)
        medications_collection.create_index([("user_id", 1), ("rxcui", 1)])
        medications_collection.create_index([("user_id", 1), ("drug_name", 1)])
        prescriptions_collection.create_index([("user_id", 1), ("date_added", -1)])
        share_links_collection.create_index([("token", 1)], unique=True)
        share_links_collection.create_index([("owner_user_id", 1), ("created_at", -1)])
        share_links_collection.create_index([("expires_at", 1)])
    except PyMongoError:
        users_collection = None
        medications_collection = None
        prescriptions_collection = None
        share_links_collection = None

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
    user_id: str = ""
    drug_name: str
    rxcui: str
    source: str = "Manual Entry"
    dose: str = ""
    frequency: str = ""
    dose_mg: float = 0.0
    frequency_per_day: float = 0.0
    prescription_file_name: str = ""


class PrescriptionAction(BaseModel):
    raw_text: str
    confidence: float = 0.0
    uploaded_file_name: str = ""


class MedicationUpdateAction(BaseModel):
    drug_name: str
    source: str = ""
    dose: str = ""
    frequency: str = ""


class RegisterAction(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "patient"


class LoginAction(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthAction(BaseModel):
    idToken: str


class ForgotPasswordAction(BaseModel):
    email: EmailStr


class VerifyResetAction(BaseModel):
    email: EmailStr
    code: str


class ResetPasswordAction(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class UserProfileAction(BaseModel):
    age: int
    sex_at_birth: str = ""
    gender_identity: str = ""
    weight_kg: float = 0.0
    height_cm: float = 0.0
    chronic_conditions: list[str] = []
    allergies: list[str] = []
    kidney_disease: bool = False
    liver_disease: bool = False
    smoking_status: str = "unknown"
    alcohol_use: str = "unknown"
    emergency_contact_name: str = ""
    emergency_contact_phone: str = ""
    emergency_notes: str = ""
    privacy_consent: bool = False


class ShareLinkAction(BaseModel):
    purpose: str = "consultation"
    expires_hours: int = 24


class DeleteAccountAction(BaseModel):
    confirm_text: str
    confirm_email: EmailStr


ALLOWED_ROLES = {"patient", "caregiver"}


def _default_profile() -> dict[str, Any]:
    return {
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
        "emergency_contact_name": "",
        "emergency_contact_phone": "",
        "emergency_notes": "",
    }


def _normalize_role(role: str | None) -> str:
    normalized = str(role or "patient").strip().lower()
    if normalized not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Role must be either patient or caregiver")
    return normalized


def _sanitize_string_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = str(value or "").strip()
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned[:30]


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


def _public_user_doc(user_doc: dict[str, Any]) -> dict[str, Any]:
    profile = user_doc.get("profile") or _default_profile()
    return {
        "id": str(user_doc["_id"]),
        "name": user_doc.get("name", ""),
        "email": user_doc.get("email", ""),
        "role": user_doc.get("role", "patient"),
        "profile_completed": bool(user_doc.get("profile_completed", False)),
        "privacy_consent": bool(user_doc.get("privacy_consent", False)),
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


def _require_profile_completed(user_doc: dict[str, Any]):
    if not bool(user_doc.get("profile_completed", False)):
        raise HTTPException(
            status_code=403,
            detail="Complete your profile before adding medicines or uploading prescriptions",
        )


def _infer_frequency_from_text(raw_text: str, frequency: str) -> str:
    normalized_frequency = (frequency or "").strip()
    if normalized_frequency:
        return normalized_frequency

    text = (raw_text or "").lower()
    if "once daily" in text or "daily" in text or "qd" in text:
        return "once daily"
    if "twice daily" in text or "bid" in text:
        return "twice daily"
    if "three times daily" in text or "tid" in text:
        return "three times daily"
    if "four times daily" in text or "qid" in text:
        return "four times daily"
    return ""


def _has_duplicate_med(existing: list[dict[str, Any]], drug_name: str, rxcui: str) -> bool:
    normalized_name = str(drug_name or "").strip().lower()
    normalized_rxcui = str(rxcui or "").strip().lower()
    has_real_rxcui = normalized_rxcui not in {"", "n/a", "na", "none", "unknown"}

    for med in existing:
        med_name = str(med.get("name", "")).strip().lower()
        med_rxcui = str(med.get("rxcui", "")).strip().lower()
        if normalized_name and med_name == normalized_name:
            return True
        if has_real_rxcui and med_rxcui == normalized_rxcui:
            return True
    return False


def _get_mongo_medications(user_id: str) -> list[dict[str, Any]]:
    _require_data_collections()
    docs = medications_collection.find({"user_id": user_id}).sort("date_added", 1)
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
    medications_collection.insert_one(
        {
            "user_id": user_id,
            "drug_name": drug_name,
            "rxcui": rxcui,
            "date_added": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "dose": dose,
            "frequency": frequency,
            "dose_mg": dose_mg,
            "frequency_per_day": frequency_per_day,
            "prescription_file_name": os.path.basename(prescription_file_name) if prescription_file_name else "",
        }
    )


def _delete_mongo_medication(user_id: str, med_id: str):
    _require_data_collections()
    try:
        result = medications_collection.delete_one({"_id": ObjectId(med_id), "user_id": user_id})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid medication id")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Medication not found")


def _update_mongo_medication(user_id: str, med_id: str, action: MedicationUpdateAction):
    _require_data_collections()
    try:
        target_filter = {"_id": ObjectId(med_id), "user_id": user_id}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid medication id")

    existing = medications_collection.find_one(target_filter)
    if not existing:
        raise HTTPException(status_code=404, detail="Medication not found")

    update_doc = {
        "drug_name": str(action.drug_name or "").strip(),
        "source": str(action.source or existing.get("source", "API/React/Auth")).strip() or "API/React/Auth",
        "dose": str(action.dose or "").strip(),
        "frequency": str(action.frequency or "").strip(),
    }
    if not update_doc["drug_name"]:
        raise HTTPException(status_code=400, detail="Drug name is required")

    medications_collection.update_one(target_filter, {"$set": update_doc})


def _get_mongo_prescriptions(user_scope_ids: list[str]) -> list[dict[str, Any]]:
    _require_data_collections()
    docs = prescriptions_collection.find({"user_id": {"$in": user_scope_ids}}).sort("date_added", -1)
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


def _save_mongo_prescription(user_id: str, raw_text: str, confidence: float, uploaded_file_name: str = ""):
    _require_data_collections()
    normalized = raw_text.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Prescription text is empty")

    already = prescriptions_collection.find_one({"user_id": user_id, "raw_text": normalized})
    if already:
        return {"status": "already_exists"}

    prescriptions_collection.insert_one(
        {
            "user_id": user_id,
            "raw_text": normalized,
            "confidence": confidence,
            "date_added": datetime.now(timezone.utc).isoformat(),
            "source": "OCR Vision",
            "uploaded_file_name": os.path.basename(uploaded_file_name) if uploaded_file_name else "",
        }
    )
    return {"status": "saved"}


def _prescription_record_filter(user_scope_ids: list[str], record_id: str) -> dict[str, Any]:
    # Support both Mongo ObjectId and legacy string ids.
    try:
        return {"user_id": {"$in": user_scope_ids}, "$or": [{"_id": ObjectId(record_id)}, {"_id": record_id}]}
    except Exception:
        return {"user_id": {"$in": user_scope_ids}, "_id": record_id}


def _delete_mongo_prescription(user_scope_ids: list[str], record_id: str):
    _require_data_collections()
    record_filter = _prescription_record_filter(user_scope_ids, record_id)
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

    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    email = payload.email.strip().lower()
    existing = users_collection.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Invalid email")

    user_doc = {
        "name": payload.name.strip(),
        "email": email,
        "password_hash": _hash_password(payload.password),
        "role": _normalize_role(payload.role),
        "profile": _default_profile(),
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

    if user_doc:
        if not user_doc.get("googleId"):
            raise HTTPException(status_code=401, detail="Invalid email")
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
                    "profile": user_doc.get("profile") or _default_profile(),
                    "profile_completed": bool(user_doc.get("profile_completed", False)),
                    "privacy_consent": bool(user_doc.get("privacy_consent", False)),
                }
            },
        )
        user_doc = users_collection.find_one({"_id": user_doc["_id"]})
    else:
        name = id_info.get("name") or email.split("@")[0]
        insert_doc = {
            "name": name,
            "email": email,
            "password_hash": _hash_password(uuid.uuid4().hex[:12]),
            "role": "patient",
            "profile": _default_profile(),
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

    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

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
    profile = current_user.get("profile") or _default_profile()
    return {
        "role": current_user.get("role", "patient"),
        "profile_completed": bool(current_user.get("profile_completed", False)),
        "privacy_consent": bool(current_user.get("privacy_consent", False)),
        "profile": profile,
    }


@app.put("/api/me/profile")
def update_my_profile(action: UserProfileAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_users_collection()

    if action.age < 0 or action.age > 120:
        raise HTTPException(status_code=400, detail="Age must be between 0 and 120")
    if action.weight_kg < 0 or action.weight_kg > 400:
        raise HTTPException(status_code=400, detail="Weight must be between 0 and 400 kg")
    if action.height_cm < 0 or action.height_cm > 260:
        raise HTTPException(status_code=400, detail="Height must be between 0 and 260 cm")
    if not action.privacy_consent:
        raise HTTPException(status_code=400, detail="Consent is required to continue")

    profile_doc = {
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
        "emergency_contact_name": str(action.emergency_contact_name or "").strip()[:120],
        "emergency_contact_phone": str(action.emergency_contact_phone or "").strip()[:40],
        "emergency_notes": str(action.emergency_notes or "").strip()[:500],
    }

    users_collection.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
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


@app.post("/api/me/privacy/export")
def export_my_data(current_user: dict[str, Any] = Depends(get_current_user)):
    _require_data_collections()

    user_scope_id = _auth_user_scope_id(current_user)
    user_scope_aliases = _auth_user_scope_aliases(current_user)
    export_doc = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": _public_user_doc(current_user),
        "medications": _get_mongo_medications(user_scope_id),
        "prescriptions": _get_mongo_prescriptions(user_scope_aliases),
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

    for record in _get_mongo_prescriptions(user_scope_aliases):
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

    expires_hours = max(1, min(int(action.expires_hours or 24), 168))
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

    meds = _get_mongo_medications(owner_id)
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

from concurrent.futures import ThreadPoolExecutor

@app.post("/api/upload")
async def upload_prescription(user_id: str, file: UploadFile = File(...)):
    file_extension = os.path.splitext(file.filename)[1]
    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_extension}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        ocr_result = process_prescription(file_path)

        # Guard clause: if it's not verified as a prescription
        if ocr_result["label"] != "medical prescription" or ocr_result["confidence"] < 0.5:
            raise HTTPException(
                status_code=400,
                detail=f"Document does not appear to be a medical prescription. "
                       f"(Classifier: {ocr_result['label']}, confidence: {round(ocr_result['confidence'], 2)})"
            )

        raw_names = ocr_result["drugs"]

        # Parallelize drug validation for performance
        with ThreadPoolExecutor(max_workers=10) as executor:
            validation_results = list(executor.map(validate_drug, raw_names))

        detail_lookup = {
            d.get("name", "").strip().lower(): d
            for d in (ocr_result.get("drug_details", []) or [])
            if d.get("name")
        }

        results = []
        for validation in validation_results:
            med_name = validation.get("name")
            details = detail_lookup.get((med_name or "").strip().lower(), {})
            is_valid = bool(validation.get("valid", False))
            inferred_frequency = _infer_frequency_from_text(ocr_result.get("text", ""), details.get("frequency", ""))
            results.append({
                "name": med_name,
                "valid": is_valid,
                "rxcui": validation.get("rxcui", "N/A") if is_valid else "N/A",
                "dose": details.get("dose", ""),
                "frequency": inferred_frequency,
                "match_status": "matched" if is_valid else "unmatched",
            })

        return {
            "drugs": results,
            "confidence": ocr_result["confidence"],
            "raw_text": ocr_result.get("text", ""),
            "uploaded_file_name": os.path.basename(file_path),
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
    return _get_mongo_medications(_auth_user_scope_id(current_user))

@app.post("/api/add")
def add_med(action: DrugAction):
    # Check for duplicates before adding
    existing = get_medications(action.user_id)
    if _has_duplicate_med(existing, action.drug_name, action.rxcui):
        return {"status": "already_exists"}
        
    add_medication(action.user_id, action.drug_name, action.rxcui, action.source or "API/React")
    return {"status": "added"}


@app.post("/api/me/add")
def add_my_med(action: DrugAction, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_profile_completed(current_user)
    user_id = _auth_user_scope_id(current_user)
    existing = _get_mongo_medications(user_id)
    if _has_duplicate_med(existing, action.drug_name, action.rxcui):
        return {"status": "already_exists"}

    _add_mongo_medication(
        user_id,
        action.drug_name,
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
    _delete_mongo_medication(_auth_user_scope_id(current_user), med_id)
    return {"status": "deleted"}


@app.put("/api/me/meds/{med_id}")
def update_my_med(med_id: str, action: MedicationUpdateAction, current_user: dict[str, Any] = Depends(get_current_user)):
    user_id = _auth_user_scope_id(current_user)
    existing = [m for m in _get_mongo_medications(user_id) if m.get("id") != med_id]
    if _has_duplicate_med(existing, action.drug_name, "N/A"):
        raise HTTPException(status_code=409, detail="Medication with this name already exists")
    _update_mongo_medication(user_id, med_id, action)
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
    meds = _get_mongo_medications(user_id)
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
    return await upload_prescription(_auth_user_scope_id(current_user), file)


@app.get("/api/me/prescriptions")
def get_my_prescriptions(current_user: dict[str, Any] = Depends(get_current_user)):
    return _get_mongo_prescriptions(_auth_user_scope_aliases(current_user))


@app.post("/api/me/prescriptions")
def save_my_prescription(action: PrescriptionAction, current_user: dict[str, Any] = Depends(get_current_user)):
    return _save_mongo_prescription(
        _auth_user_scope_id(current_user),
        action.raw_text,
        action.confidence,
        action.uploaded_file_name,
    )


@app.delete("/api/me/prescriptions/{record_id}")
def delete_my_prescription(record_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _delete_mongo_prescription(_auth_user_scope_aliases(current_user), record_id)
    return {"status": "deleted"}


@app.get("/api/me/prescriptions/{record_id}/file")
def get_my_prescription_file(record_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _require_data_collections()
    doc = prescriptions_collection.find_one(_prescription_record_filter(_auth_user_scope_aliases(current_user), record_id))

    if not doc:
        raise HTTPException(status_code=404, detail="Prescription record not found")

    uploaded = os.path.basename(doc.get("uploaded_file_name", ""))
    if not uploaded:
        raise HTTPException(status_code=404, detail="No uploaded file stored for this record")

    file_path = os.path.join(UPLOAD_DIR, uploaded)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Stored file not found")

    return FileResponse(file_path, filename=uploaded)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
