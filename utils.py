import requests
import json
from functools import lru_cache
from urllib.parse import quote_plus


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
