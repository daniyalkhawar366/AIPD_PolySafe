from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
from typing import List
from pydantic import BaseModel

# Import your existing logic
from ocr import extract_text, parse_drug_names
from utils import validate_drug
from profile import add_medication, get_medications, delete_medication, clear_profile
from interaction import check_interactions_for_profile

app = FastAPI()

# Enable CORS for React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class DrugAction(BaseModel):
    user_id: str
    drug_name: str
    rxcui: str

@app.get("/health")
def health():
    return {"status": "ok"}

from concurrent.futures import ThreadPoolExecutor

@app.post("/api/upload")
async def upload_prescription(user_id: str, file: UploadFile = File(...)):
    file_extension = os.path.splitext(file.filename)[1]
    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_extension}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        text = extract_text(file_path)
        raw_names = parse_drug_names(text)
        
        # Parallelize drug validation for performance
        with ThreadPoolExecutor(max_workers=10) as executor:
            validation_results = list(executor.map(validate_drug, raw_names))
            
        results = []
        for validation in validation_results:
            if validation.get("valid", False):
                results.append({
                    "name": validation.get("name"),
                    "valid": True,
                    "rxcui": validation.get("rxcui", "N/A")
                })
            
        return {"drugs": results}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.get("/api/meds/{user_id}")
def get_user_meds(user_id: str):
    return get_medications(user_id)

@app.post("/api/add")
def add_med(action: DrugAction):
    # Check for duplicates before adding
    existing = get_medications(action.user_id)
    if any(m['rxcui'] == action.rxcui or m['name'].lower() == action.drug_name.lower() for m in existing):
        return {"status": "already_exists"}
        
    add_medication(action.user_id, action.drug_name, action.rxcui, "API/React")
    return {"status": "added"}

@app.delete("/api/meds/{med_id}")
def delete_med(med_id: int):
    delete_medication(med_id)
    return {"status": "deleted"}

@app.get("/api/interactions/{user_id}")
def check_interactions(user_id: str):
    meds = get_medications(user_id)
    if len(meds) < 2:
        return {"interactions": [], "message": "Need more meds"}
    
    results = check_interactions_for_profile(meds)
    if results == "API_FAILED":
        raise HTTPException(status_code=500, detail="FDA API Timeout")
        
    return {"interactions": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
