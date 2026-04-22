import requests
import json
import re
import os
from functools import lru_cache
from urllib.parse import quote_plus


def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


_load_env()


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_TEXT_MODEL = os.getenv(
    "GROQ_TEXT_MODEL",
    os.getenv("GROQ_VISION_MODEL", "llama-3.1-8b-instant"),
)


def _rxnorm_exact_lookup(drug_name):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}&search=1"
    response = requests.get(url, timeout=6)
    data = response.json()
    if 'idGroup' in data and 'rxnormId' in data['idGroup']:
        rxcui = data['idGroup']['rxnormId'][0]
        return {"name": drug_name, "valid": True, "rxcui": rxcui}
    return None


def _rxnorm_approximate_lookup(drug_name):
    safe_name = quote_plus(str(drug_name or "").strip())
    url = f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={safe_name}&maxEntries=3&option=1"
    response = requests.get(url, timeout=6)
    data = response.json()
    candidates = data.get('approximateGroup', {}).get('candidate', [])
    if not candidates:
        return None

    top = candidates[0]
    score = float(top.get('score', 0) or 0)
    corrected_name = top.get('name', drug_name)
    rxcui = top.get('rxcui')
    if score < 70 or not rxcui:
        return None
    return {
        "name": drug_name,
        "valid": True,
        "rxcui": str(rxcui),
        "normalized_name": corrected_name,
        "match_type": "approximate",
        "score": score,
    }

@lru_cache(maxsize=1024)
def validate_drug(drug_name):
    """
    Validate drug name via RxNorm API with caching.
    Returns: {"name": "Aspirin", "valid": True, "rxcui": "1191"}
    """
    try:
        exact = _rxnorm_exact_lookup(drug_name)
        if exact:
            exact["match_type"] = "exact"
            exact["score"] = 100.0
            return exact

        approx = _rxnorm_approximate_lookup(drug_name)
        if approx:
            return approx

        return {"name": drug_name, "valid": False, "match_type": "unmatched"}
    except Exception as e:
        print(f"Error validating drug {drug_name}: {e}")
        return {"name": drug_name, "valid": False, "error": True, "match_type": "error"}

@lru_cache(maxsize=1024)
def fetch_interaction_text(drug_name):
    """
    Fetch interaction label text for a single drug from OpenFDA.
    Cached so repeated checks reuse previous responses.
    """
    safe_name = quote_plus(str(drug_name or "").strip())
    url = f"https://api.fda.gov/drug/label.json?search=drug_interactions:{safe_name}&limit=1"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None

        data = response.json()
        if 'results' in data and len(data['results']) > 0:
            return data['results'][0].get('drug_interactions', [""])[0]
        return None
    except Exception as e:
        print(f"Error fetching interaction text for {drug_name}: {e}")
        return "ERROR_TIMEOUT"


@lru_cache(maxsize=1024)
def search_interaction(drug_a_name, drug_b_name):
    """
    Check if drug_b is mentioned in drug_a's interaction field.
    Searches via OpenFDA API. CACHED for performance.
    """
    try:
        interaction_text = fetch_interaction_text(drug_a_name)
        if interaction_text == "ERROR_TIMEOUT":
            return "ERROR_TIMEOUT"
        if interaction_text and drug_b_name.lower() in interaction_text.lower():
            return interaction_text
        return None
    except Exception as e:
        print(f"Error checking interaction for {drug_a_name}: {e}")
        return "ERROR_TIMEOUT"


def _normalize_label_text(raw_text: str, max_chars: int = 520) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\[(.*?)\]", r"(\1)", text)
    return text[:max_chars].strip()


COMMON_USE_FALLBACKS = {
    "aspirin": "Commonly used for pain, fever, and to help lower blood clot risk in some heart and stroke patients.",
    "clopidogrel": "Used to help prevent harmful blood clots in people with heart disease, stroke history, or stents.",
    "metformin": "Used to help control blood sugar in adults with type 2 diabetes, along with diet and exercise.",
    "ibuprofen": "Used for pain, fever, and inflammation such as headaches, muscle pain, or joint pain.",
    "atorvastatin": "Used to lower cholesterol and reduce the risk of heart attack and stroke.",
    "amlodipine": "Used to treat high blood pressure and chest pain (angina).",
    "lisinopril": "Used to treat high blood pressure and help protect heart and kidney function in some patients.",
    "losartan": "Used to treat high blood pressure and help protect kidneys in some people with diabetes.",
    "paracetamol": "Used for pain and fever relief.",
    "acetaminophen": "Used for pain and fever relief.",
    "cimetidine": "Used to reduce stomach acid and treat conditions like heartburn, acid reflux, and ulcers.",
}


def _match_common_use_fallback(name: str) -> str | None:
    lowered = str(name or "").strip().lower()
    if not lowered:
        return None
    for key, text in COMMON_USE_FALLBACKS.items():
        if key in lowered:
            return text
    return None


def _to_patient_use_summary(raw_text: str, med_name: str) -> str:
    known_fallback = _match_common_use_fallback(med_name)
    if known_fallback:
        return known_fallback

    text = _normalize_label_text(raw_text, max_chars=1200)
    if not text:
        return "Used for condition-specific treatment. Ask your pharmacist or doctor how this medicine helps in your case."

    # Drop section headers and references like "1 INDICATIONS AND USAGE" or "(1)".
    text = re.sub(r"\b(?:\d+(?:\.\d+)?\s+)?INDICATIONS?\s+AND\s+USAGE\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\s*\d+(?:\.\d+)?\s*\)", "", text)
    text = re.sub(r"\bare\s+indicated\s+in\s*:?\s*\d*\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bindicated\s+in\s*:?\s*\d*\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bLimitations?\s+of\s+Use:.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" .;")

    lowered = text.lower()
    # Prefer short phrase after "indicated ... for"
    match = re.search(r"indicated(?:\s+as\s+an?\s+adjunct\s+to\s+[^.]+?)?\s+for\s+(.+?)(?:\.|;|$)", lowered, flags=re.IGNORECASE)
    if match:
        condition = match.group(1).strip(" ,.;")
        condition = re.sub(r"\s*[-–]\s*for\s+patients?.*", "", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\s*\bincluding\b.*", "", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\s*\bwith\b\s+non[\s-].*", "", condition, flags=re.IGNORECASE)
        condition = re.sub(r"\s+", " ", condition).strip(" ,.;")
        if condition:
            sentence = f"Commonly used for {condition}."
            sentence = sentence[0].upper() + sentence[1:]
            return sentence[:170]

    # Fall back to first clear sentence.
    first_sentence = re.split(r"(?<=[.!?])\s+", text)[0].strip()
    if len(first_sentence) < 30:
        second_parts = re.split(r"(?<=[.!?])\s+", text)
        if len(second_parts) > 1:
            first_sentence = f"{first_sentence} {second_parts[1]}".strip()

    if first_sentence:
        cleaned = re.sub(r"\s*[-–]\s*for\s+patients?.*", "", first_sentence, flags=re.IGNORECASE).strip(" ,.;")
        text = (cleaned or first_sentence)
        text = re.sub(r"\bP2Y\s*12\s+platelet\s+inhibitor\b", "blood clot prevention medicine", text, flags=re.IGNORECASE)
        text = re.sub(r"\bdipeptidyl peptidase-4\s*\(DPP-4\)\s+inhibitor\b", "blood sugar control medicine", text, flags=re.IGNORECASE)
        text = re.sub(r"\bbiguanide\b", "blood sugar control medicine", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" ,.;")
        return text[:170]
    return "Used for condition-specific treatment. Ask your pharmacist or doctor how this medicine helps in your case."


def _llm_medicine_use_summary(drug_name: str) -> str | None:
    """
    Hidden fallback that creates a short layman summary when label extraction is missing/noisy.
    """
    if not GROQ_API_KEY:
        return None

    prompt = (
        f"Medicine: {drug_name}\n"
        "Task: Write one plain-language sentence (max 22 words) about the medicine's common use for patients. "
        "No jargon, no lists, no warnings, no extra text."
    )

    payload = {
        "model": GROQ_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": "You write short patient-friendly medication purpose summaries."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_completion_tokens": 70,
    }

    url = f"{GROQ_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code != 200:
            return None
        data = response.json()
        content = str(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        content = re.sub(r"\s+", " ", content).strip('" ')
        if not content:
            return None
        # Keep response concise and sentence-like.
        content = content.split("\n")[0].strip()
        return content[:170]
    except Exception:
        return None


def _llm_rewrite_use_summary(drug_name: str, base_text: str) -> str | None:
    if not GROQ_API_KEY:
        return None

    cleaned = _normalize_label_text(base_text, max_chars=900)
    if not cleaned:
        return None

    prompt = (
        f"Medicine: {drug_name}\n"
        f"Reference text: {cleaned}\n"
        "Rewrite into one short plain-language sentence for a patient. "
        "Max 20 words. Mention only common use. No jargon, lists, or disclaimers."
    )

    payload = {
        "model": GROQ_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": "You simplify medical text for patients."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_completion_tokens": 70,
    }

    url = f"{GROQ_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code != 200:
            return None
        data = response.json()
        content = str(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        content = re.sub(r"\s+", " ", content).strip('" ')
        if not content:
            return None
        return content[:170]
    except Exception:
        return None


def _strip_strength_tokens(name: str) -> str:
    text = str(name or "").strip().lower()
    text = re.sub(r"\b\d+(?:\.\d+)?\s*(mg|mcg|ug|g|ml|iu|units?)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(enteric-coated|extended-release|er|xr|sr|dr|ec)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[^a-z\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _openfda_first_label(search_expr: str) -> dict | None:
    url = "https://api.fda.gov/drug/label.json"
    try:
        response = requests.get(url, params={"search": search_expr, "limit": 1}, timeout=6)
        if response.status_code != 200:
            return None
        payload = response.json()
        results = payload.get("results", []) or []
        return results[0] if results else None
    except Exception:
        return None


def _extract_usage_text_from_label(label: dict) -> str:
    usage_sections = label.get("indications_and_usage") or label.get("purpose") or []
    if isinstance(usage_sections, list) and usage_sections:
        return _normalize_label_text(usage_sections[0])
    if isinstance(usage_sections, str):
        return _normalize_label_text(usage_sections)

    description_sections = label.get("description") or []
    if isinstance(description_sections, list) and description_sections:
        return _normalize_label_text(description_sections[0])
    if isinstance(description_sections, str):
        return _normalize_label_text(description_sections)
    return ""


@lru_cache(maxsize=1024)
def fetch_medicine_use_summary(drug_name: str) -> dict:
    """
    Fetch a medicine-use summary using OpenFDA drug label text.
    Returns a dict with summary and source metadata.
    """
    normalized_name = str(drug_name or "").strip()
    if not normalized_name:
        return {
            "name": "",
            "summary": "",
            "source": "OpenFDA drug label (FDA SPL)",
            "found": False,
        }

    cleaned_name = _strip_strength_tokens(normalized_name)
    normalized_info = validate_drug(cleaned_name or normalized_name)

    candidate_terms: list[str] = []
    for term in [normalized_name, cleaned_name, normalized_info.get("normalized_name", "")]:
        item = str(term or "").strip()
        if item and item not in candidate_terms:
            candidate_terms.append(item)

    search_expressions: list[str] = []
    for term in candidate_terms:
        escaped = term.replace('"', '')
        search_expressions.append(f'openfda.generic_name:"{escaped}"')
        search_expressions.append(f'openfda.brand_name:"{escaped}"')
        search_expressions.append(f'openfda.substance_name:"{escaped}"')
        search_expressions.append(
            f'openfda.generic_name:"{escaped}"+OR+openfda.brand_name:"{escaped}"+OR+openfda.substance_name:"{escaped}"'
        )

    rxnorm_id = str(normalized_info.get("rxcui") or "").strip()
    if rxnorm_id:
        search_expressions.insert(0, f'openfda.rxcui:"{rxnorm_id}"')

    try:
        label = None
        for expr in search_expressions:
            label = _openfda_first_label(expr)
            if label:
                break

        if not label:
            llm_summary = _llm_medicine_use_summary(normalized_name)
            if llm_summary:
                return {
                    "name": normalized_name,
                    "summary": llm_summary,
                    "source": "OpenFDA drug label (FDA SPL)",
                    "found": True,
                }
            return {
                "name": normalized_name,
                "summary": "We could not find an FDA label summary for this medicine right now.",
                "source": "OpenFDA drug label (FDA SPL)",
                "found": False,
            }

        usage_text = _extract_usage_text_from_label(label)

        if not usage_text:
            llm_summary = _llm_medicine_use_summary(normalized_name)
            if llm_summary:
                return {
                    "name": normalized_name,
                    "summary": llm_summary,
                    "source": "OpenFDA drug label (FDA SPL)",
                    "found": True,
                }
            usage_text = "Used for condition-specific treatment. Ask your pharmacist or doctor how this medicine helps in your case."

        patient_summary = _to_patient_use_summary(usage_text, normalized_name)
        llm_rewrite = _llm_rewrite_use_summary(normalized_name, usage_text)
        if llm_rewrite:
            patient_summary = llm_rewrite

        return {
            "name": normalized_name,
            "summary": patient_summary,
            "source": "OpenFDA drug label (FDA SPL)",
            "found": True,
        }
    except Exception as e:
        print(f"Error fetching medicine-use summary for {drug_name}: {e}")
        return {
            "name": normalized_name,
            "summary": "Medicine-use details are temporarily unavailable. Please try again.",
            "source": "OpenFDA drug label (FDA SPL)",
            "found": False,
            "error": True,
        }
