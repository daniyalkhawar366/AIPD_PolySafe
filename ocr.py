import os
import re
import base64
import requests
import json
import time
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Load .env file if present ──────────────────────────────────────────────
def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

# ── API Keys ───────────────────────────────────────────────────────────────
# Groq Vision — PRIMARY (fast, reliable)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Google Gemini Vision — FALLBACK (free at https://aistudio.google.com/app/apikey)
#   - 15 req/min free tier, 1500 req/day
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")

# Gemini models (in fallback order)
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

EXTRACTION_PROMPT = """You are a medical prescription OCR system.
Analyze this prescription image (handwritten OR printed) and return ONLY this JSON (no markdown, no extra text):
{
  "is_prescription": true,
  "raw_text": "<only the medicine/drug lines from the prescription, not patient or doctor info>",
  "drugs": [
    {"name": "Full Drug Name", "dose": "500mg", "frequency": "once a day"}
  ]
}
Rules:
- drugs: list every medication. Each entry is ONE drug name only.
- Expand abbreviations: FeSO4→Ferrous Sulfate, AA→Ascorbic Acid, APAP→Acetaminophen, ASA→Aspirin, HCTZ→Hydrochlorothiazide
- Lines starting with Sig:, A.D., BID, TID, QID, PRN, or a dosage like 100mg are INSTRUCTIONS — exclude from drugs list
- A dosage line (e.g. "100mg tab") directly below a drug name belongs to THAT drug as its dose field
- raw_text: include only the medication section (drug names, doses, frequencies) — skip patient name, address, doctor info
- CRITICAL: Ensure the JSON is completely valid. Any newlines inside the raw_text string must be escaped as \\n.
- Be concise. Do not include explanations.
"""


def _prepare_image(file_path: str) -> tuple:
    """
    Load image, resize to max 800px on longest side, compress to JPEG.
    This is the #1 speed optimization — turns a 5MB photo into ~80KB,
    making the API payload ~60x smaller and upload ~10-20x faster.
    Returns (base64_string, mime_type).
    """
    import io
    from PIL import Image

    if file_path.lower().endswith(".pdf"):
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(file_path, dpi=150, first_page=1, last_page=1)
            img = pages[0]
        except Exception as e:
            print(f"[OCR] PDF conversion failed: {e}")
            return None, None
    else:
        try:
            img = Image.open(file_path)
        except Exception as e:
            print(f"[OCR] Cannot open image: {e}")
            return None, None

    # Convert to RGB (handles RGBA PNGs, palette images, etc.)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Resize: cap longest side at 800px — enough for text, much smaller payload
    MAX_DIM = 800
    w, h = img.size
    scale = min(MAX_DIM / w, MAX_DIM / h, 1.0)  # never upscale
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        print(f"[OCR] Resized image {w}x{h} → {img.size[0]}x{img.size[1]}")

    # Compress to JPEG at 80% quality
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    size_kb = buf.tell() / 1024
    print(f"[OCR] Compressed image size: {size_kb:.1f} KB")

    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"


# ── Groq Vision ────────────────────────────────────────────────────────────

def _call_groq(img_b64: str, mime: str) -> dict:
    """
    Call Groq Vision API (primary OCR engine).
    Returns parsed dict: {is_prescription, raw_text, drugs}
    Raises RuntimeError/ValueError on failure.
    """
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set. "
            "Get a key from https://console.groq.com/keys "
            "then add it to your .env file as: GROQ_API_KEY=your_key_here"
        )

    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                ],
            }
        ],
        "temperature": 0.1,
        "max_completion_tokens": 1200,
        "response_format": {"type": "json_object"},
    }

    url = f"{GROQ_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

            if resp.status_code in (401, 403):
                raise ValueError(
                    "Groq API key is invalid or expired. "
                    "Get a new key at https://console.groq.com/keys"
                )

            if resp.status_code == 429:
                wait = 1
                print(f"[OCR] Groq rate limit, waiting {wait}s...")
                time.sleep(wait)
                if attempt == 1:
                    raise RuntimeError("Groq quota exhausted")
                continue

            resp.raise_for_status()
            data = resp.json()
            raw_output = data["choices"][0]["message"]["content"]
            parsed = _parse_json_response(raw_output)
            print(f"[OCR] Groq success")
            return parsed

        except ValueError:
            raise
        except json.JSONDecodeError as e:
            print(f"[OCR] Groq JSON parse error: {e}")
            raise
        except Exception as e:
            print(f"[OCR] Groq error attempt {attempt+1}: {e}")
            if attempt == 1:
                raise RuntimeError(f"Groq failed after retries: {e}")
            time.sleep(0.25)

    raise RuntimeError("Groq call failed unexpectedly")


def _parse_json_response(raw_output: str) -> dict:
    """Strip markdown fences and parse JSON from model output. Handles incomplete responses gracefully."""
    raw_output = re.sub(r"```(?:json)?", "", raw_output).strip().strip("`").strip()
    try:
        return json.loads(raw_output, strict=False)
    except json.JSONDecodeError as e:
        print(f"[OCR] JSON Parse Error: {e}. Attempting recovery...")
        # Try salvaging raw_text from incomplete JSON
        text_match = re.search(r'"raw_text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_output, re.DOTALL)
        if text_match:
            raw_text = text_match.group(1)
            # Also try to extract any drug names already parsed
            drugs = []
            drug_matches = re.findall(r'"name"\s*:\s*"([^"]+)"', raw_output)
            for name in drug_matches:
                drugs.append({"name": name})
            print(f"[OCR] Recovered raw_text and {len(drugs)} drugs from incomplete JSON")
            return {"is_prescription": True, "raw_text": raw_text, "drugs": drugs}
        raise


# ── Google Gemini Vision ────────────────────────────────────────────────

def _call_gemini(img_b64: str, mime: str) -> dict:
    """
    Fallback: Call Gemini Flash Vision API.
    Returns parsed dict: {is_prescription, raw_text, drugs}
    Raises RuntimeError/ValueError on failure.
    """
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com/app/apikey "
            "then add it to your .env file as: GEMINI_API_KEY=your_key_here"
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": EXTRACTION_PROMPT},
                    {"inline_data": {"mime_type": mime, "data": img_b64}},
                ]
            }
        ],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000},
    }

    last_error = None
    for model in GEMINI_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_API_KEY}"
        )
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=60)

                if resp.status_code in (401, 403):
                    raise ValueError(
                        "Gemini API key is invalid or expired. "
                        "Get a new key at https://aistudio.google.com/app/apikey"
                    )

                if resp.status_code == 404:
                    last_error = f"Gemini model {model} not found (may be deprecated)"
                    print(f"[OCR] {last_error}")
                    break  # try next model

                if resp.status_code == 429:
                    wait = 2 ** attempt
                    print(f"[OCR] Gemini rate limit on {model}, waiting {wait}s...")
                    time.sleep(wait)
                    if attempt == 2:
                        last_error = f"Gemini quota exhausted on {model}"
                    continue

                resp.raise_for_status()
                data = resp.json()
                raw_output = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = _parse_json_response(raw_output)
                print(f"[OCR] Gemini success with model: {model}")
                return parsed

            except ValueError:
                raise
            except json.JSONDecodeError as e:
                last_error = f"Gemini JSON parse error on {model}: {e}"
                print(f"[OCR] {last_error}")
                break
            except Exception as e:
                last_error = f"Gemini error on {model} attempt {attempt+1}: {e}"
                print(f"[OCR] {last_error}")
                if attempt == 2:
                    break
                time.sleep(1)

    raise RuntimeError(last_error or "All Gemini models failed.")


# ── Public API ─────────────────────────────────────────────────────────────

def _call_vision(file_path: str) -> dict:
    """
    Call Vision API: try Groq (primary), fall back to Gemini.
    Raises RuntimeError with a clear message if all fail.
    """
    img_b64, mime = _prepare_image(file_path)
    if not img_b64:
        raise ValueError("Could not read the uploaded file. Please upload a JPG, PNG, or PDF.")

    last_error = None

    # Try Groq first (primary)
    if GROQ_API_KEY:
        try:
            return _call_groq(img_b64, mime)
        except Exception as e:
            last_error = f"Groq failed: {e}"
            print(f"[OCR] {last_error}, trying Gemini fallback...")
    else:
        print(f"[OCR] GROQ_API_KEY not set, trying Gemini fallback...")

    # Fall back to Gemini
    if GEMINI_API_KEY:
        try:
            return _call_gemini(img_b64, mime)
        except Exception as e:
            last_error = f"Gemini fallback failed: {e}"
            raise RuntimeError(last_error)
    else:
        raise ValueError(
            "No vision API configured. Set at least one of:\n"
            "  GROQ_API_KEY=... (get from https://console.groq.com/keys)\n"
            "  GEMINI_API_KEY=... (get from https://aistudio.google.com/app/apikey)"
        )


def extract_text(file_path: str) -> str:
    """Run vision OCR on the prescription. Returns raw text string."""
    result = _call_vision(file_path)
    return result.get("raw_text", "")


def classify_prescription_zero_shot(text: str):
    """Simple keyword heuristic — vision model already tells us if it's a prescription."""
    if not text:
        return "No text found", 0.0
    keywords = ["mg", "ml", "tab", "rx", "dose", "prescribed", "capsule",
                 "refill", "sig", "disp", "bid", "tid", "qid", "prn"]
    has = any(k in text.lower() for k in keywords)
    return ("medical prescription", 0.85) if has else ("not medical prescription", 0.55)


# Common pharmaceutical abbreviations the model may leave unexpanded
_ABBREVIATIONS = {
    "feso4":  "Ferrous Sulfate",
    "fes04":  "Ferrous Sulfate",   # common OCR confusion of 4→0
    "aa":     "Ascorbic Acid",
    "apap":   "Acetaminophen",
    "asa":    "Aspirin",
    "hct":    "Hydrochlorothiazide",
    "hctz":   "Hydrochlorothiazide",
    "mom":    "Magnesium Hydroxide",
    "pcm":    "Paracetamol",
    "amox":   "Amoxicillin",
    "augmentin": "Amoxicillin-Clavulanate",
    "mtx":    "Methotrexate",
    "nitro":  "Nitroglycerin",
    "pred":   "Prednisone",
    "epi":    "Epinephrine",
}
# Keys that came from the abbreviation table — no need to fuzzy-match these
_ABBREVIATION_VALUES = {v.lower() for v in _ABBREVIATIONS.values()}


def _expand_abbreviation(name: str) -> tuple:
    """
    Expand known pharmaceutical abbreviations.
    Returns (expanded_name, was_expanded) so we can skip fuzzy for already-known names.
    """
    expanded = _ABBREVIATIONS.get(name.lower(), name)
    return expanded, (expanded != name)


@lru_cache(maxsize=512)
def _rxnorm_fuzzy_correct(name: str) -> str:
    """
    Use RxNorm approximateTerm to correct OCR misreadings.
    Cached — same drug name across uploads is instant after first call.
    Timeout: 2s (fail fast rather than hanging the response).
    """
    try:
        url = f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={name}&maxEntries=1&option=1"
        resp = requests.get(url, timeout=2)
        data = resp.json()
        candidates = data.get("approximateGroup", {}).get("candidate", [])
        if candidates:
            score = float(candidates[0].get("score", 0))
            corrected = candidates[0].get("name", name)
            if score >= 70:
                print(f"[OCR] Fuzzy corrected '{name}' → '{corrected}' (score={score:.1f})")
                return corrected
    except Exception as e:
        print(f"[OCR] RxNorm fuzzy skipped for '{name}': {e}")
    return name


def parse_drug_names(raw_text: str) -> list:
    """Fallback parser — used only if vision model returns no structured drugs list."""
    FORM_WORDS = {
        "The","And","For","With","From","Each","Take","This","That","These","Those",
        "Name","Address","Date","Age","Sex","Weight","Height","Dob","Phone",
        "Patient","Doctor","Physician","Clinic","Hospital","Medical","Centre",
        "Center","Street","City","State","Zip","Country","Usa","Ny","Ca","Tx",
        "Dea","Lic","License","Signature","Signed","Print","Printed",
        "Refill","Refills","Times","Dispense","Dispensed","Quantity","Qty",
        "Unit","Units","Directions","Instructions","Label","Rx","Npi",
        "Exempt","Substitution","Permitted","Brand","Generic",
        "Mon","Tue","Wed","Thu","Fri","Sat","Sun",
        "Morning","Evening","Night","Daily","Weekly","Twice","Thrice",
        "Without","Food","Water","Milk","Meals","Bedtime","Once",
    }
    dosage_re = re.compile(
        r"([A-Za-z]{3,})\s*[\d\.]*\s*(mg|ml|mcg|iu|tablet|tab|pill|cap|capsule|drop|spoon|unit)",
        re.IGNORECASE,
    )
    candidates = [m.group(1).capitalize() for m in dosage_re.finditer(raw_text)
                  if m.group(1).capitalize() not in FORM_WORDS]
    if candidates:
        return sorted(set(candidates))
    return sorted({t.capitalize() for t in re.findall(r"[A-Za-z]{4,}", raw_text)
                   if t.capitalize() not in FORM_WORDS})


def process_prescription(file_path: str) -> dict:
    """
    Full pipeline:
    1. Send image to Groq Vision (primary) or Gemini Vision (fallback)
    2. Get structured JSON back (is_prescription, raw_text, drugs[])
    3. Pass drug names to FDA validation in backend

    Raises RuntimeError/ValueError with clear messages on failure.
    """
    result = _call_vision(file_path)

    raw_text = result.get("raw_text", "")
    is_prescription = result.get("is_prescription", False)

    # Extract structured drug rows from model output
    structured_rows = [d for d in result.get("drugs", []) if d.get("name")]
    drugs = [d.get("name", "") for d in structured_rows if d.get("name")]

    # Fallback to regex if model gave no structured drugs
    if not drugs and raw_text:
        drugs = parse_drug_names(raw_text)

    # Expand known abbreviations (FeSO4 → Ferrous Sulfate, etc.)
    # Fuzzy RxNorm correction removed from critical path — prompt handles normalization.
    # The validate_drug step in backend already confirms names via RxNorm exact match.
    drugs = [_expand_abbreviation(d)[0] for d in drugs]

    # Keep dose/frequency paired with the normalized names for downstream safety checks
    drug_details = []
    for row in structured_rows:
        normalized_name = _expand_abbreviation(row.get("name", ""))[0]
        if not normalized_name:
            continue
        drug_details.append(
            {
                "name": normalized_name,
                "dose": str(row.get("dose", "")).strip(),
                "frequency": str(row.get("frequency", "")).strip(),
            }
        )

    # Deduplicate while preserving order
    seen = set()
    unique_drugs = []
    for d in drugs:
        key = d.lower()
        if key not in seen:
            seen.add(key)
            unique_drugs.append(d)
    drugs = unique_drugs

    label = "medical prescription" if is_prescription else "not medical prescription"
    confidence = 0.92 if is_prescription else 0.40

    # If model says not-prescription but keywords say otherwise, trust content
    if not is_prescription and raw_text:
        fallback_label, fallback_conf = classify_prescription_zero_shot(raw_text)
        if fallback_label == "medical prescription":
            label, confidence = fallback_label, fallback_conf

    return {
        "text": raw_text,
        "label": label,
        "confidence": confidence,
        "drugs": drugs,
        "drug_details": drug_details,
    }
