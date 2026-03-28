import streamlit as st
import pandas as pd
import os
from database import init_db
from profile import add_medication, get_medications, delete_medication
from utils import validate_drug
from ocr import extract_text, parse_drug_names
from interaction import check_interactions_for_profile

# Page config
st.set_page_config(page_title="PolySafe - Drug Interaction Awareness", page_icon="💊")

# Initialize DB on start
init_db()

# Session State for User Name/ID
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""

# Sidebar
st.sidebar.title("🛡️ PolySafe")
page = st.sidebar.selectbox("Navigation", ["🏠 Home", "📄 Upload Prescription", "💊 My Medications", "🔍 Check Interactions", "ℹ️ About"])

# Referral Prompt Helper
def show_referral_prompt(severity="None"):
    if severity == "High":
        st.error("⚠️ High-risk interaction detected. Do not change your medications without speaking to your pharmacist or doctor first.")
    elif severity == "Medium":
        st.warning("⚠️ Potential interaction detected. Please discuss this with your pharmacist at your next visit.")
    else:
        st.info("ℹ️ These results are for awareness only. Always speak to your pharmacist or doctor before making any changes to your medications.")

# --- Home Page ---
if page == "🏠 Home":
    st.title("Welcome to PolySafe")
    st.markdown("""
    PolySafe is a safety tool for polypharmacy patients.
    Upload your prescriptions, and we'll check for potential drug interactions
    using validated FDA and NIH databases.
    """)
    
    name = st.text_input("Please enter your Name or Patient ID to start:", value=st.session_state.user_id)
    if name:
        st.session_state.user_id = name
        st.success(f"Session started for: {name}")

# --- Upload Page ---
elif page == "📄 Upload Prescription":
    st.title("Upload Prescription")
    if not st.session_state.user_id:
        st.warning("Please enter your Name on the Home page first.")
    else:
        uploaded_file = st.file_uploader("Choose a prescription (PDF, JPG, PNG)", type=["pdf", "jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            # Save temporary file
            with open(f"temp_{uploaded_file.name}", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            with st.spinner("Extracting drug names..."):
                raw_text = extract_text(f"temp_{uploaded_file.name}")
                if not raw_text:
                    st.error("We couldn't read this file. Please try a clearer image or enter your medications manually below.")
                else:
                    drug_candidates = parse_drug_names(raw_text)
                    st.subheader("Extracted Medications")
                    
                    if not drug_candidates:
                        st.warning("No medications detected. Please try manual entry.")
                    else:
                        st.info("Check the drugs you want to add to your profile.")
                        
                        validated_meds = []
                        for drug in drug_candidates:
                            with st.spinner(f"Validating {drug}..."):
                                result = validate_drug(drug)
                                validated_meds.append(result)
                        
                        # Show confirmation UI
                        with st.form("confirm_meds"):
                            selections = {}
                            st.write("### ✅ Recognized Drugs")
                            for res in validated_meds:
                                if res.get('valid'):
                                    selections[res['name']] = st.checkbox(f"**{res['name']}** (Confirmed)", value=True, key=f"rec_{res['name']}")
                            
                            st.write("### ⚠️ Unrecognized Drugs (Please Edit/Verify)")
                            for res in validated_meds:
                                if not res.get('valid'):
                                    st.write(f"- {res['name']}")
                                    new_name = st.text_input(f"Edit '{res['name']}' if incorrect:", value=res['name'], key=f"edit_{res['name']}")
                                    selections[new_name] = st.checkbox(f"Add '{new_name}' anyway?", value=False, key=f"add_{res['name']}")
                            
                            submitted = st.form_submit_button("Confirm & Save to Profile")
                            if submitted:
                                for drug_name, to_add in selections.items():
                                    if to_add:
                                        # Re-validate if edited
                                        final_res = validate_drug(drug_name)
                                        rxcui = final_res.get('rxcui', 'N/A')
                                        add_medication(st.session_state.user_id, drug_name, rxcui, "OCR Upload")
                                st.success("Medications saved to profile!")
            
            # Cleanup temp file
            os.remove(f"temp_{uploaded_file.name}")

# --- My Medications Page ---
elif page == "💊 My Medications":
    st.title("My Medications")
    if not st.session_state.user_id:
        st.warning("Please enter your name on the Home page first.")
    else:
        # Manual Add
        with st.expander("➕ Add Medication Manually"):
            man_name = st.text_input("Drug Name (e.g. Aspirin)")
            if st.button("Add Drug"):
                with st.spinner("Validating..."):
                    res = validate_drug(man_name)
                    if res.get('valid'):
                        add_medication(st.session_state.user_id, man_name, res['rxcui'], "Manual Entry")
                        st.success(f"Added {man_name}")
                        st.rerun()
                    else:
                        st.error(f"We didn't recognize '{man_name}' — please verify this with your pharmacist before we check it.")
        
        # Profile Table
        meds = get_medications(st.session_state.user_id)
        if meds:
            df = pd.DataFrame(meds)
            st.dataframe(df[['name', 'rxcui', 'date', 'source']], hide_index=True)
            
            # Delete selection
            st.write("### Delete Medication")
            med_to_del = st.selectbox("Select medication to remove:", options=[f"{m['name']} (ID: {m['id']})" for m in meds])
            if st.button("Delete"):
                id_to_del = int(med_to_del.split("ID: ")[1].rstrip(")"))
                delete_medication(id_to_del)
                st.success("Medication removed.")
                st.rerun()
        else:
            st.info("No medications in your profile yet.")

# --- Check Interactions Page ---
elif page == "🔍 Check Interactions":
    st.title("Interaction Check")
    if not st.session_state.user_id:
        st.warning("Please enter your name on the Home page first.")
    else:
        meds = get_medications(st.session_state.user_id)
        if len(meds) < 2:
            st.warning("You need at least 2 medications in your profile to check for interactions.")
        else:
            if st.button("Run Interaction Check"):
                with st.spinner("Checking FDA database..."):
                    interactions = check_interactions_for_profile(meds)
                    
                    if interactions == "API_FAILED":
                        st.error("Interaction check failed. Please try again or consult your pharmacist directly.")
                    elif not interactions:
                        st.success("No known interactions found between your current medications. Always consult your pharmacist if anything changes.")
                        show_referral_prompt("None")
                    else:
                        worst_severity = "Low"
                        for inter in interactions:
                            # Severity badges
                            color = "red" if inter['severity'] == "High" else "orange" if inter['severity'] == "Medium" else "yellow"
                            if inter['severity'] == "High": worst_severity = "High"
                            elif inter['severity'] == "Medium" and worst_severity != "High": worst_severity = "Medium"
                            
                            st.markdown(f"""
                            <div style="border: 2px solid {color}; border-radius: 10px; padding: 15px; margin-bottom: 15px;">
                                <h3 style="color: {color}; margin-top: 0;">{inter['drug_a']} + {inter['drug_b']}</h3>
                                <strong>Severity:</strong> <span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 5px;">{inter['severity']}</span>
                                <p style="margin-top: 10px;">{inter['explanation']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        show_referral_prompt(worst_severity)

# --- About Page ---
elif page == "ℹ️ About":
    st.title("About PolySafe")
    st.markdown("""
    **What this is:**
    A university course project MVP for drug interaction awareness. It helps patients identify potential risks early.
    
    **What this is NOT:**
    This is not a medical device or a clinical substitute. It uses publicly available clinical databases to match keywords. 
    Always consult a qualified healthcare professional before taking action based on these results.
    
    **Data Sources:**
    - **Drug interactions:** [FDA OpenFDA](https://open.fda.gov)
    - **Drug name validation:** [NIH RxNorm API](https://rxnav.nlm.nih.gov)
    
    **Technology Stack:**
    - Python, Streamlit, SQLite, Tesseract OCR, Poppler.
    """)
