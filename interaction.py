from utils import search_interaction
import re

SEVERITY_KEYWORDS = {
    "High": ["contraindicated", "fatal", "life-threatening", "avoid", "do not use"],
    "Medium": ["caution", "monitor", "risk", "may increase", "may decrease"],
    "Low": ["mild", "minor", "slight", "consider"]
}

PLAIN_LANGUAGE_MAP = {
    r"CNS depression": "may cause extreme drowsiness or dizziness",
    r"anticoagulant effect": "increases risk of serious bleeding",
    r"potentiate": "could dangerously strengthen the effect of",
    r"contraindicated": "must NOT be taken together under any circumstances",
    r"Hepatotoxicity": "could cause severe liver damage",
    r"Nephrotoxicity": "could cause severe kidney damage",
    r"Tachycardia": "may cause dangerously fast heart rate",
    r"Bradycardia": "may cause dangerously slow heart rate",
    r"Thrombocytopenia": "may lower blood platelet count (bleeding risk)",
}

def analyze_severity(text):
    """Keyword matching on the raw interaction text to determine severity."""
    for severity, keywords in SEVERITY_KEYWORDS.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
                return severity
    return "Unknown"

def convert_to_plain_language(text):
    """
    Summarizes the clinical interaction text into a primary risk + formatted detail.
    """
    # Identify high-level risk categories with more nuance
    primary_risk = "General interaction risk identified."
    
    # Priority-based matching for specific risks (if/elif ensures the most specific match wins)
    if "ulcer" in text.lower() or "stomach" in text.lower() or "gastric" in text.lower():
        primary_risk = "Major risk of stomach lining damage and GI bleeding."
    elif "bleeding" in text.lower() or "anticoagulant" in text.lower() or "hemorrhage" in text.lower():
        primary_risk = "Significant increase in internal bleeding and bruising risk."
    elif "liver" in text.lower() or "hepatotoxicity" in text.lower():
        primary_risk = "High potential for serious liver toxicity or failure."
    elif "kidney" in text.lower() or "nephro" in text.lower() or "renal" in text.lower():
        primary_risk = "Risk of acute kidney strain or renal impairment."
    elif "heart" in text.lower() or "cardiac" in text.lower() or "arrhythmia" in text.lower():
        primary_risk = "Risk of abnormal heart rhythm or cardiovascular stress."
    elif "breathing" in text.lower() or "respiratory" in text.lower():
        primary_risk = "Potential for dangerous respiratory distress or failure."
    elif "drowsiness" in text.lower() or "sedation" in text.lower() or "cns" in text.lower():
        primary_risk = "Highly likely to cause extreme sedation/sleepiness."

    # Apply phrase mappings with bold formatting
    formatted_detail = text
    for clinical, plain in PLAIN_LANGUAGE_MAP.items():
        formatted_detail = re.sub(re.escape(clinical), f"**{plain.upper()}**", formatted_detail, flags=re.IGNORECASE)
    
    return {
        "primary_risk": primary_risk,
        "detail": formatted_detail[:600] + "..." if len(formatted_detail) > 600 else formatted_detail
    }

def check_interactions_for_profile(medications):
    """
    Check interaction pairs from profile.
    medications: list of dicts with 'name' and 'rxcui'
    """
    interactions = []
    med_names = [med['name'] for med in medications]
    
    for i in range(len(med_names)):
        drug_a = med_names[i]
        for j in range(i + 1, len(med_names)):
            drug_b = med_names[j]
            
            # Check interaction both ways, since FDA api acts like a document search
            interaction_text = search_interaction(drug_a, drug_b) or search_interaction(drug_b, drug_a)

            if interaction_text == "ERROR_TIMEOUT":
                return "API_FAILED"
            if interaction_text:
                severity = analyze_severity(interaction_text)
                explanation_data = convert_to_plain_language(interaction_text)
                interactions.append({
                    "drug_a": drug_a,
                    "drug_b": drug_b,
                    "severity": severity,
                    "summary": explanation_data["primary_risk"],
                    "detail": explanation_data["detail"]
                })
                
    return interactions
