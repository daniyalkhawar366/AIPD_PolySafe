import requests
import json
from functools import lru_cache
from urllib.parse import quote_plus

@lru_cache(maxsize=1024)
def validate_drug(drug_name):
    """
    Validate drug name via RxNorm API with caching.
    Returns: {"name": "Aspirin", "valid": True, "rxcui": "1191"}
    """
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}&search=1"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Check if we have a match in RxNorm
        if 'idGroup' in data and 'rxnormId' in data['idGroup']:
            rxcui = data['idGroup']['rxnormId'][0]
            return {"name": drug_name, "valid": True, "rxcui": rxcui}
        else:
            return {"name": drug_name, "valid": False}
    except Exception as e:
        print(f"Error validating drug {drug_name}: {e}")
        return {"name": drug_name, "valid": False, "error": True}

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
