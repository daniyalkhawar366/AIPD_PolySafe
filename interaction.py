from utils import fetch_interaction_text
import re
from collections import defaultdict

MAX_DAILY_MG = {
    "acetaminophen": 4000,
    "paracetamol": 4000,
    "ibuprofen": 3200,
    "aspirin": 4000,
    "naproxen": 1000,
    "diclofenac": 150,
    "metformin": 2550,
    "amlodipine": 10,
    "atorvastatin": 80,
    "lisinopril": 40,
}

MAX_SINGLE_DOSE_MG = {
    "acetaminophen": 1000,
    "paracetamol": 1000,
    "ibuprofen": 800,
    "aspirin": 1000,
    "naproxen": 500,
    "diclofenac": 75,
    "metformin": 1000,
    "amlodipine": 10,
    "atorvastatin": 80,
    "lisinopril": 40,
}

INGREDIENT_ALIASES = {
    "acetaminophen": ["acetaminophen", "paracetamol", "apap"],
    "ibuprofen": ["ibuprofen"],
    "aspirin": ["aspirin", "asa"],
    "naproxen": ["naproxen"],
    "diclofenac": ["diclofenac"],
    "metformin": ["metformin"],
    "amlodipine": ["amlodipine"],
    "atorvastatin": ["atorvastatin"],
    "lisinopril": ["lisinopril"],
    "losartan": ["losartan"],
    "simvastatin": ["simvastatin"],
}

THERAPEUTIC_CLASS_KEYWORDS = {
    "NSAID pain relievers": ["ibuprofen", "naproxen", "diclofenac", "aspirin", "ketorolac"],
    "ACE inhibitor blood-pressure medicines": ["lisinopril", "enalapril", "ramipril"],
    "ARB blood-pressure medicines": ["losartan", "valsartan", "olmesartan", "telmisartan"],
    "Statin cholesterol medicines": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"],
    "Diabetes biguanides": ["metformin"],
}

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

    interaction_text_by_drug = {}
    for drug_name in med_names:
        interaction_text = fetch_interaction_text(drug_name)
        if interaction_text == "ERROR_TIMEOUT":
            return "API_FAILED"
        interaction_text_by_drug[drug_name] = interaction_text or ""

    for i in range(len(med_names)):
        drug_a = med_names[i]
        for j in range(i + 1, len(med_names)):
            drug_b = med_names[j]

            text_a = interaction_text_by_drug.get(drug_a, "")
            text_b = interaction_text_by_drug.get(drug_b, "")

            # Prefer A->B match, then B->A using already-fetched labels.
            interaction_text = None
            if text_a and drug_b.lower() in text_a.lower():
                interaction_text = text_a
            elif text_b and drug_a.lower() in text_b.lower():
                interaction_text = text_b

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


def _dose_to_mg(dose_value: str | None) -> float:
    if not dose_value:
        return 0.0
    text = str(dose_value).strip().lower()
    match = re.search(r"([\d.]+)\s*(mg|g|mcg|ug)?", text)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = (match.group(2) or "mg").lower()
    if unit == "g":
        return amount * 1000
    if unit in ("mcg", "ug"):
        return amount / 1000
    return amount


def _frequency_per_day(freq_text: str | None) -> float:
    if not freq_text:
        return 0.0
    text = str(freq_text).strip().lower()

    numeric = re.search(r"([\d.]+)", text)
    if numeric and any(token in text for token in ["per day", "times", "x"]):
        return float(numeric.group(1))

    if "once" in text or "daily" in text or "qd" in text:
        return 1.0
    if "bid" in text or "twice" in text:
        return 2.0
    if "tid" in text or "three" in text:
        return 3.0
    if "qid" in text or "four" in text:
        return 4.0

    every_hours = re.search(r"every\s*(\d+)\s*hour", text)
    if every_hours:
        hours = max(float(every_hours.group(1)), 1.0)
        return 24.0 / hours

    return 0.0


def _max_daily_for_name(name: str) -> tuple[str, float] | tuple[None, None]:
    lower = (name or "").lower()
    for ingredient, max_mg in MAX_DAILY_MG.items():
        if ingredient in lower:
            return ingredient, float(max_mg)
    return None, None


def _max_single_dose_for_name(name: str) -> tuple[str, float] | tuple[None, None]:
    lower = (name or "").lower()
    for ingredient, max_mg in MAX_SINGLE_DOSE_MG.items():
        if ingredient in lower:
            return ingredient, float(max_mg)
    return None, None


def _normalize_ingredient(name: str) -> str | None:
    lowered = (name or "").lower()
    for canonical, aliases in INGREDIENT_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return canonical
    return None


def _normalize_schedule(freq_text: str | None) -> str:
    if not freq_text:
        return ""
    text = str(freq_text).strip().lower()
    # normalize common shorthand for easier duplicate-schedule detection
    text = text.replace("b.i.d", "bid").replace("t.i.d", "tid").replace("q.i.d", "qid")
    if "bid" in text or "twice" in text:
        return "twice daily"
    if "tid" in text or "three" in text:
        return "three times daily"
    if "qid" in text or "four" in text:
        return "four times daily"
    if "once" in text or "daily" in text or "qd" in text:
        return "once daily"
    every_hours = re.search(r"every\s*(\d+)\s*hour", text)
    if every_hours:
        return f"every {every_hours.group(1)} hours"
    return text


def check_overdose_risks(medications):
    alerts = []
    for med in medications:
        med_name = med.get("name", "")
        ingredient, max_daily = _max_daily_for_name(med_name)
        if not ingredient:
            continue

        dose_mg = float(med.get("dose_mg") or 0) or _dose_to_mg(med.get("dose"))
        freq_day = float(med.get("frequency_per_day") or 0) or _frequency_per_day(med.get("frequency"))
        if dose_mg <= 0 or freq_day <= 0:
            continue

        estimated_daily = dose_mg * freq_day
        if estimated_daily <= max_daily:
            continue

        severity = "High" if estimated_daily > (1.2 * max_daily) else "Medium"
        alerts.append({
            "drug_a": med_name,
            "drug_b": "Dose/Frequency",
            "severity": severity,
            "summary": f"Estimated daily dose ({estimated_daily:.0f} mg) exceeds recommended maximum for {ingredient} ({max_daily:.0f} mg/day).",
            "detail": (
                f"Entered dose: {med.get('dose') or f'{dose_mg:.0f} mg'}; "
                f"frequency: {med.get('frequency') or f'{freq_day:.1f} times/day'}. "
                f"Estimated total: {estimated_daily:.0f} mg/day."
            ),
            "kind": "overdose",
        })

    return alerts


def check_double_dose_and_schedule_risks(medications):
    alerts = []

    by_ingredient: dict[str, list[dict]] = defaultdict(list)
    by_class: dict[str, list[dict]] = defaultdict(list)

    for med in medications:
        med_name = med.get("name", "")
        ingredient = _normalize_ingredient(med_name)
        if ingredient:
            by_ingredient[ingredient].append(med)

        lowered = med_name.lower()
        for class_name, keywords in THERAPEUTIC_CLASS_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                by_class[class_name].append(med)

        # single-dose sanity check
        dose_mg = float(med.get("dose_mg") or 0) or _dose_to_mg(med.get("dose"))
        ingredient_for_single, max_single = _max_single_dose_for_name(med_name)
        if ingredient_for_single and max_single and dose_mg > max_single:
            alerts.append({
                "drug_a": med_name,
                "drug_b": "Single dose limit",
                "severity": "High" if dose_mg > (1.2 * max_single) else "Medium",
                "summary": f"Entered single dose ({dose_mg:.0f} mg) appears above common limit for {ingredient_for_single} ({max_single:.0f} mg).",
                "detail": f"Dose entered: {med.get('dose') or f'{dose_mg:.0f} mg'}. Please verify with your prescriber/pharmacist.",
                "kind": "dose_sanity",
            })

    # duplicate active ingredient / formula overlap
    for ingredient, meds in by_ingredient.items():
        if len(meds) < 2:
            continue

        med_names = [m.get("name", "Unknown") for m in meds]
        schedules = [_normalize_schedule(m.get("frequency")) for m in meds]
        same_schedule = len({s for s in schedules if s}) == 1 and any(schedules)

        alerts.append({
            "drug_a": med_names[0],
            "drug_b": med_names[1] if len(med_names) > 1 else ingredient,
            "severity": "High" if same_schedule else "Medium",
            "summary": f"Possible duplicate therapy: multiple medicines appear to contain {ingredient}.",
            "detail": (
                f"Detected medicines: {', '.join(med_names)}. "
                f"This can lead to accidental double-dosing across prescriptions/brands."
            ),
            "kind": "duplicate_ingredient",
        })

        if same_schedule:
            alerts.append({
                "drug_a": med_names[0],
                "drug_b": med_names[1] if len(med_names) > 1 else ingredient,
                "severity": "High",
                "summary": f"Duplicate schedule detected for {ingredient}.",
                "detail": f"Multiple {ingredient} medicines are set to the same schedule ({schedules[0]}), which increases overdose risk.",
                "kind": "duplicate_schedule",
            })

    # same-class overlap
    for class_name, meds in by_class.items():
        unique_names = []
        seen = set()
        for med in meds:
            med_name = med.get("name", "")
            key = med_name.lower()
            if key and key not in seen:
                seen.add(key)
                unique_names.append(med_name)
        if len(unique_names) < 2:
            continue

        alerts.append({
            "drug_a": unique_names[0],
            "drug_b": unique_names[1],
            "severity": "Medium",
            "summary": f"Overlapping same-class medicines detected: {class_name}.",
            "detail": f"Detected in profile: {', '.join(unique_names)}. Same-class overlap may increase side-effect burden and should be reviewed.",
            "kind": "class_overlap",
        })

    return alerts


def _profile_allergies(profile: dict) -> list[str]:
    raw = profile.get("allergies") or []
    if not isinstance(raw, list):
        return []
    return [str(item).strip().lower() for item in raw if str(item).strip()]


def _profile_conditions(profile: dict) -> list[str]:
    raw = profile.get("chronic_conditions") or []
    if not isinstance(raw, list):
        return []
    return [str(item).strip().lower() for item in raw if str(item).strip()]


def check_profile_context_risks(medications: list[dict], profile: dict | None = None) -> list[dict]:
    profile = profile or {}
    alerts: list[dict] = []
    med_names = [str(med.get("name") or "").strip() for med in medications if str(med.get("name") or "").strip()]
    lowered_names = [name.lower() for name in med_names]

    if not med_names:
        return alerts

    try:
        age_value = int(float(profile.get("age") or 0))
    except Exception:
        age_value = 0

    if age_value >= 65 and len(med_names) >= 2:
        alerts.append({
            "drug_a": med_names[0],
            "drug_b": "Age 65+ profile context",
            "severity": "Medium" if len(med_names) >= 4 else "Low",
            "summary": "Age-sensitive medication review recommended for this profile.",
            "detail": (
                f"Profile age is {age_value}. With {len(med_names)} active medicines, sensitivity to side effects and interactions can increase. "
                "Review dose timing and necessity with your clinician."
            ),
            "kind": "profile_age",
        })

    kidney_keywords = ["ibuprofen", "naproxen", "diclofenac", "aspirin", "ketorolac", "metformin", "lisinopril", "losartan"]
    if bool(profile.get("kidney_disease")):
        kidney_matches = [name for name in med_names if any(token in name.lower() for token in kidney_keywords)]
        if kidney_matches:
            alerts.append({
                "drug_a": kidney_matches[0],
                "drug_b": "Kidney disease profile context",
                "severity": "High" if any("ibuprofen" in name.lower() or "naproxen" in name.lower() or "diclofenac" in name.lower() for name in kidney_matches) else "Medium",
                "summary": "Kidney profile flag: medicine choice/dose may need renal review.",
                "detail": (
                    f"Profile indicates kidney disease. Relevant medicines in your list: {', '.join(kidney_matches)}. "
                    "A renal dose/safety check is recommended before continuing unchanged."
                ),
                "kind": "profile_kidney",
            })

    liver_keywords = ["acetaminophen", "paracetamol", "atorvastatin", "simvastatin", "diclofenac", "aspirin"]
    if bool(profile.get("liver_disease")):
        liver_matches = [name for name in med_names if any(token in name.lower() for token in liver_keywords)]
        if liver_matches:
            alerts.append({
                "drug_a": liver_matches[0],
                "drug_b": "Liver disease profile context",
                "severity": "High" if any("acetaminophen" in name.lower() or "paracetamol" in name.lower() for name in liver_matches) else "Medium",
                "summary": "Liver profile flag: medicines may increase hepatic burden.",
                "detail": (
                    f"Profile indicates liver disease. Relevant medicines in your list: {', '.join(liver_matches)}. "
                    "A liver safety review is recommended for dose and monitoring."
                ),
                "kind": "profile_liver",
            })

    allergies = _profile_allergies(profile)
    for allergy in allergies:
        if len(allergy) < 3:
            continue
        matched_meds = [name for name in med_names if allergy in name.lower() or name.lower() in allergy]
        if not matched_meds:
            # Handle common shorthand mapping in allergy entries
            if allergy in {"asa", "aspirin"}:
                matched_meds = [name for name in med_names if "aspirin" in name.lower()]
        if matched_meds:
            alerts.append({
                "drug_a": matched_meds[0],
                "drug_b": f"Allergy profile: {allergy}",
                "severity": "High",
                "summary": "Potential allergy conflict with your recorded profile.",
                "detail": (
                    f"Profile allergies include '{allergy}'. Matching medicine(s): {', '.join(matched_meds)}. "
                    "Stop and verify immediately with your clinician/pharmacist if this is an active allergy."
                ),
                "kind": "profile_allergy",
            })

    chronic_conditions = _profile_conditions(profile)
    has_hypertension = any("hypertension" in condition or "high blood pressure" in condition for condition in chronic_conditions)
    if has_hypertension:
        nsaid_matches = [name for name in med_names if any(token in name.lower() for token in ["ibuprofen", "naproxen", "diclofenac", "aspirin"])]
        if nsaid_matches:
            alerts.append({
                "drug_a": nsaid_matches[0],
                "drug_b": "Hypertension profile context",
                "severity": "Medium",
                "summary": "Blood-pressure profile context: NSAID use may need monitoring.",
                "detail": (
                    f"Profile includes hypertension and NSAID medicine(s): {', '.join(nsaid_matches)}. "
                    "Monitor blood pressure and discuss alternatives if readings worsen."
                ),
                "kind": "profile_hypertension",
            })

    return alerts


def check_safety_for_profile(medications, profile: dict | None = None):
    interaction_alerts = check_interactions_for_profile(medications)
    if interaction_alerts == "API_FAILED":
        return "API_FAILED"
    overdose_alerts = check_overdose_risks(medications)
    duplicate_and_sanity_alerts = check_double_dose_and_schedule_risks(medications)
    profile_alerts = check_profile_context_risks(medications, profile)
    return interaction_alerts + overdose_alerts + duplicate_and_sanity_alerts + profile_alerts


def _severity_rank(severity: str) -> int:
    ranking = {
        "High": 0,
        "Medium": 1,
        "Low": 2,
    }
    return ranking.get(str(severity or "").strip(), 3)


def _severity_counts(alerts: list[dict]) -> dict:
    counts = {"High": 0, "Medium": 0, "Low": 0, "Unknown": 0}
    for alert in alerts:
        severity = str(alert.get("severity") or "Unknown")
        if severity not in counts:
            counts["Unknown"] += 1
        else:
            counts[severity] += 1
    return counts


def _kind_counts(alerts: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for alert in alerts:
        kind = str(alert.get("kind") or "interaction")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _build_medication_risk_map(medications: list[dict], alerts: list[dict]) -> dict:
    profile_names = [str(m.get("name") or "").strip() for m in medications if str(m.get("name") or "").strip()]
    risk_map = {
        name: {
            "highest_severity": None,
            "high": 0,
            "medium": 0,
            "low": 0,
            "unknown": 0,
            "total_alerts": 0,
            "kinds": {},
        }
        for name in profile_names
    }

    def bump(name: str, severity: str, kind: str):
        if name not in risk_map:
            return
        entry = risk_map[name]
        sev = (severity or "Unknown").strip()
        if sev == "High":
            entry["high"] += 1
        elif sev == "Medium":
            entry["medium"] += 1
        elif sev == "Low":
            entry["low"] += 1
        else:
            entry["unknown"] += 1
        entry["total_alerts"] += 1
        entry["kinds"][kind] = entry["kinds"].get(kind, 0) + 1

        current = entry.get("highest_severity")
        if current is None or _severity_rank(sev) < _severity_rank(current):
            entry["highest_severity"] = sev

    for alert in alerts:
        kind = str(alert.get("kind") or "interaction")
        severity = str(alert.get("severity") or "Unknown")
        drug_a = str(alert.get("drug_a") or "").strip()
        drug_b = str(alert.get("drug_b") or "").strip()

        if drug_a in risk_map:
            bump(drug_a, severity, kind)
        if drug_b in risk_map:
            bump(drug_b, severity, kind)

    return risk_map


def _build_dynamic_recommendations(alerts: list[dict]) -> list[str]:
    if not alerts:
        return [
            "No active safety alerts were detected right now. Keep your medication profile updated and re-run checks after any changes.",
        ]

    severities = _severity_counts(alerts)
    kinds = _kind_counts(alerts)
    recommendations: list[str] = []

    if severities["High"] > 0:
        recommendations.append(
            "At least one high-risk conflict was detected. Contact your pharmacist or prescriber before your next dose to confirm a safe plan."
        )

    if kinds.get("duplicate_ingredient", 0) > 0 or kinds.get("duplicate_schedule", 0) > 0:
        recommendations.append(
            "Potential duplicate therapy was found. Bring all medicine labels (including combination products) for a same-ingredient verification."
        )

    if kinds.get("overdose", 0) > 0 or kinds.get("dose_sanity", 0) > 0:
        recommendations.append(
            "Dose-related concerns were detected. Verify strength and frequency instructions with your care team before continuing unchanged."
        )

    if kinds.get("class_overlap", 0) > 0:
        recommendations.append(
            "Same-class overlap was detected. Ask whether both medicines are intended together or if one was meant to replace the other."
        )

    if any(kind.startswith("profile_") for kind in kinds):
        recommendations.append(
            "Profile-linked risk factors were detected. Confirm this plan with your clinician using your age, condition, and organ-risk context."
        )

    if not recommendations:
        recommendations.append(
            "Review this report with your pharmacist to confirm clinical relevance based on your full history and lab context."
        )

    return recommendations


def build_safety_report(medications: list[dict], alerts: list[dict]) -> dict:
    sorted_alerts = sorted(
        alerts,
        key=lambda item: (
            _severity_rank(str(item.get("severity") or "")),
            str(item.get("drug_a") or "").lower(),
            str(item.get("drug_b") or "").lower(),
        ),
    )

    severity_counts = _severity_counts(sorted_alerts)
    high_count = severity_counts.get("High", 0)
    medium_count = severity_counts.get("Medium", 0)
    low_count = severity_counts.get("Low", 0)

    return {
        "med_count": len(medications),
        "total_alerts": len(sorted_alerts),
        "severity_counts": severity_counts,
        "kind_counts": _kind_counts(sorted_alerts),
        "top_priority_alerts": sorted_alerts[:3],
        "recommendations": _build_dynamic_recommendations(sorted_alerts),
        "medication_risk_map": _build_medication_risk_map(medications, sorted_alerts),
        "overall_status": (
            "critical"
            if high_count > 0
            else "caution"
            if medium_count > 0
            else "stable"
            if low_count == 0
            else "monitor"
        ),
    }
