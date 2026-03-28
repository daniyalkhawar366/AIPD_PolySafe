import reflex as rx
import os
import pandas as pd
from datetime import datetime

# Import our existing logic
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database import init_db
from profile import add_medication, get_medications, delete_medication
from utils import validate_drug
from ocr import extract_text, parse_drug_names
from interaction import check_interactions_for_profile

# Initialize DB
init_db()

# --- THEME STYLING (Glassmorphism & Gradients) ---
class ThemeState(rx.State):
    """The theme state for our app."""
    bg_gradient = "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)"
    glass_box = dict(
        backdrop_filter="blur(10px) saturate(180%)",
        background_color="rgba(17, 25, 40, 0.75)",
        border_radius="12px",
        border="1px solid rgba(255, 255, 255, 0.125)",
        padding="20px",
        box_shadow="0 8px 32px 0 rgba(0, 0, 0, 0.37)",
    )

# --- APP STATE ---
class State(rx.State):
    user_id: str = ""
    medications: list[dict] = []
    interactions: list[dict] = []
    checking: bool = False
    processing_ocr: bool = False
    extracted_drugs: list[dict] = [] # list of {"name": name, "valid": bool, "checked": bool}
    show_confirm_modal: bool = False
    interaction_failed: bool = False

    @rx.var
    def medication_count(self) -> int:
        return len(self.medications)

    @rx.var
    def interaction_count(self) -> int:
        return len(self.interactions)

    @rx.var
    def has_interactions(self) -> bool:
        return len(self.interactions) > 0

    @rx.var
    def can_check(self) -> bool:
        return len(self.medications) >= 2
    
    def set_user(self, name: str):
        self.user_id = name
        self.load_meds()
        
    def load_meds(self):
        if self.user_id:
            raw_meds = get_medications(self.user_id)
            self.medications = raw_meds
            
    def handle_upload(self, files: list[rx.UploadFile]):
        if not self.user_id:
            return rx.window_alert("Please enter patient ID first.")
            
        self.processing_ocr = True
        yield
        
        # Save temp file
        file = files[0]
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(file.file.read())
            
        try:
            raw_text = extract_text(temp_path)
            drug_candidates = parse_drug_names(raw_text)
            
            validated = []
            for i, name in enumerate(drug_candidates):
                res = validate_drug(name)
                validated.append({
                    "id": i,
                    "name": name,
                    "valid": res.get("valid", False),
                    "checked": res.get("valid", False),
                    "rxcui": res.get("rxcui", "N/A")
                })
            
            self.extracted_drugs = validated
            self.show_confirm_modal = True
        finally:
            self.processing_ocr = False
            if os.path.exists(temp_path): os.remove(temp_path)
            
    def toggle_drug_check(self, drug_id: int):
        for drug in self.extracted_drugs:
            if drug["id"] == drug_id:
                drug["checked"] = not drug["checked"]
        self.extracted_drugs = self.extracted_drugs # Trigger update
        
    def save_confirmed_meds(self):
        existing_rxcui = {str(med.get("rxcui", "")) for med in self.medications if med.get("rxcui")}
        existing_names = {med.get("name", "").lower() for med in self.medications}

        for drug in self.extracted_drugs:
            if drug.get("checked"):
                drug_rxcui = str(drug.get("rxcui", ""))
                drug_name = drug.get("name", "").lower()

                # If the drug is already in the database, skip saving it again
                if (drug_rxcui != "N/A" and drug_rxcui in existing_rxcui) or (drug_name in existing_names):
                    continue

                add_medication(self.user_id, drug["name"], drug["rxcui"], "OCR Vision")
                
        self.show_confirm_modal = False
        self.load_meds()
        return rx.toast.success("Medications saved to profile!")

    def delete_med(self, med_id: int):
        delete_medication(med_id)
        self.load_meds()
        
    def check_for_interactions(self):
        if len(self.medications) < 2:
            return rx.toast.warning("Please add at least 2 medications to check for interactions.", position="top-center")
        
        self.checking = True
        self.interaction_failed = False
        yield
        
        results = check_interactions_for_profile(self.medications)
        if results == "API_FAILED":
            self.interaction_failed = True
            self.interactions = []
        else:
            self.interactions = results
            
        self.checking = False

# --- COMPONENTS ---
def sidebar():
    return rx.vstack(
        rx.heading("🛡️ PolySafe", size="8", color="white", margin_bottom="30px"),
        rx.link(rx.button("🏠 Home", variant="ghost", width="100%", color="white"), href="/"),
        rx.link(rx.button("📄 Upload", variant="ghost", width="100%", color="white"), href="/upload"),
        rx.link(rx.button("💊 Profile", variant="ghost", width="100%", color="white"), href="/profile"),
        rx.link(rx.button("🔍 Check", variant="ghost", width="100%", color="white"), href="/check"),
        width="250px",
        height="100vh",
        padding="20px",
        background="rgba(15, 12, 41, 0.9)",
        border_right="1px solid rgba(255, 255, 255, 0.1)",
        align_items="start",
    )

def layout(content):
    return rx.hstack(
        sidebar(),
        rx.box(
            content,
            flex="1",
            height="100vh",
            overflow_y="auto",
            padding="40px",
            background=ThemeState.bg_gradient,
        ),
        width="100%",
    )

# --- PAGES ---
@rx.page(route="/", title="Home - PolySafe")
def index():
    return layout(
        rx.vstack(
            rx.box(
                rx.vstack(
                    rx.heading("Patient Identity", size="7", color="white"),
                    rx.text("Enter your Name or Patient ID to access your profile.", color="gray.400"),
                    rx.input(
                        placeholder="John Doe", 
                        on_blur=State.set_user, 
                        background="rgba(255, 255, 255, 0.1)",
                        color="white",
                        border="none",
                        width="300px"
                    ),
                    rx.cond(
                        State.user_id != "",
                        rx.text(f"Welcome back, {State.user_id}", color="cyan.300", font_weight="bold"),
                    )
                ),
                style=ThemeState.glass_box
            ),
            align="center",
            justify="center",
            height="80vh"
        )
    )

@rx.page(route="/upload", title="Upload - PolySafe")
def upload_page():
    return layout(
        rx.vstack(
            rx.heading("📄 Prescription OCR Vision", size="8", color="white", margin_bottom="20px"),
            rx.upload(
                rx.vstack(
                    rx.button("Select File", color="cyan.300", border="1px solid cyan"),
                    rx.text("Drag and drop or click to upload PDF/Image", color="gray.300"),
                ),
                id="upload1",
                multiple=False,
                accept={
                    "application/pdf": [".pdf"],
                    "image/jpeg": [".jpg", ".jpeg"],
                    "image/png": [".png"],
                },
                max_files=1,
                border="2px dashed rgba(0, 255, 255, 0.3)",
                padding="50px",
                width="100%",
                background="rgba(255, 255, 255, 0.05)",
                on_drop=State.handle_upload(rx.upload_files(upload_id="upload1")),
            ),
            rx.cond(
                State.processing_ocr,
                rx.spinner(size="3", color="white"),
            ),
            # Confirmation Modal
            rx.dialog.root(
                rx.dialog.content(
                    rx.dialog.title("✅ Confirm Extracted Medications"),
                    rx.vstack(
                        rx.foreach(
                            State.extracted_drugs,
                            lambda drug: rx.hstack(
                                rx.checkbox(on_change=lambda _: State.toggle_drug_check(drug["id"]), is_checked=drug["checked"]),
                                rx.text(drug["name"], color="white"),
                                rx.cond(drug["valid"], rx.badge("Recognized", color_scheme="green"), rx.badge("Check Manual", color_scheme="orange")),
                                spacing="4"
                            )
                        )
                    ),
                    rx.hstack(
                        rx.button("Save to Profile", on_click=State.save_confirmed_meds, color_scheme="cyan"),
                        rx.dialog.close(rx.button("Close", variant="ghost")),
                        margin_top="20px",
                        justify="end"
                    ),
                    style=ThemeState.glass_box,
                ),
                open=State.show_confirm_modal,
            ),
            style=ThemeState.glass_box,
            width="100%",
        )
    )

@rx.page(route="/profile", title="Profile - PolySafe")
def profile_page():
    return layout(
        rx.vstack(
            rx.heading(f"💊 {State.user_id}'s Medication Profile", size="8", color="white", margin_bottom="20px"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Drug"),
                        rx.table.column_header_cell("RxCUI"),
                        rx.table.column_header_cell("Action"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        State.medications,
                        lambda med: rx.table.row(
                            rx.table.cell(med["name"]),
                            rx.table.cell(med["rxcui"]),
                            rx.table.cell(rx.button("Delete", on_click=lambda: State.delete_med(med["id"]), color_scheme="red", size="1")),
                        )
                    )
                ),
                width="100%",
                color="white",
            ),
            style=ThemeState.glass_box,
            width="100%",
        )
    )

@rx.page(route="/check", title="Check Interactions - PolySafe")
def check_page():
    return layout(
        rx.vstack(
            rx.heading("🔍 Safety Interaction Engine", size="8", color="white", margin_bottom="20px"),
            rx.button(
                "Run Interaction Check", 
                on_click=State.check_for_interactions, 
                loading=State.checking,
                color_scheme="cyan",
                width="100%"
            ),
            rx.cond(
                State.interaction_failed,
                rx.callout("Interaction check failed. Please try again.", icon="triangle_alert", color_scheme="red", width="100%"),
            ),
            rx.cond(
                (State.interaction_count == 0) & (~State.checking) & (~State.interaction_failed) & State.can_check,
                rx.callout("No known interactions found. Always speak to your pharmacist.", icon="info", color_scheme="green", width="100%"),
            ),
            rx.foreach(
                State.interactions,
                lambda inter: rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.heading(f"{inter['drug_a']} + {inter['drug_b']}", size="4", color="white"),
                            rx.badge(inter["severity"], color_scheme=rx.cond(inter["severity"] == "High", "red", "orange")),
                            justify="between", width="100%"
                        ),
                        rx.text(inter["explanation"], color="gray.300"),
                        align_items="start"
                    ),
                    style=ThemeState.glass_box,
                    width="100%",
                    margin_top="10px"
                )
            ),
            # Mandatory Referral Prompt
            rx.box(
                rx.text("ℹ️ These results are for awareness only. Always speak to your pharmacist or doctor before making changes.", color="cyan.200", font_size="sm"),
                padding="10px",
                border="1px solid rgba(0, 255, 255, 0.2)",
                border_radius="8px",
                margin_top="30px"
            ),
            width="100%",
        )
    )

app = rx.App()
