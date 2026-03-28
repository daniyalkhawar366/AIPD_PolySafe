# 🛡️ PolySafe: Advanced Drug Interaction & Safety Shield

**PolySafe** is a high-fidelity, AI-powered drug interaction awareness platform designed for polypharmacy patients and caregivers. It uses advanced OCR to extract medications from prescriptions and cross-references them with global clinical databases to detect life-threatening interactions in real-time.

![PolySafe Dashboard](https://raw.githubusercontent.com/placeholder-image-for-readme.png)

---

## ✨ Key Features

- **👁️ Digital Vision OCR**: Intelligent extraction of drug names from images and PDFs using a dosage-proximity heuristic (mg/ml detection).
- **📋 Safety Profile Management**: Track and manage your active medication list with instant clinical validation via NIH RxNorm.
- **🚨 Risk Decoder**: Automatically translates dense clinical jargon (e.g., *CNS Depression*, *Hepatotoxicity*) into plain English (e.g., *Extreme Drowsiness*, *Liver Damage*).
- **📑 Multi-View Dashboard**: Switch between high-density medication management and dedicated Safety Analysis Reports.
- **🎨 Premium Aesthetics**: A state-of-the-art glassmorphic UI built with React 19, Tailwind CSS v4, and Framer Motion for smooth, cinematic transitions.
- **⚡ High Performance**: Parallelized clinical validation using `ThreadPoolExecutor` and LRU caching for sub-second analysis.

---

## 🛠️ Technology Stack

- **Frontend**: React 19, Vite, Tailwind CSS v4, Framer Motion, Lucide Icons.
- **Backend**: FastAPI (Python), Uvicorn.
- **OCR Engine**: Pytesseract (Tesseract OCR) & Pdf2image (Poppler).
- **Clinical APIs**: NIH RxNav (RxNorm) & FDA OpenFDA (Drug Labels).

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Tesseract OCR**: [Install Guide](https://tesseract-ocr.github.io/tessdoc/Installation.html)
- **Poppler**: [Install Guide](https://github.com/oschwartz10612/poppler-windows/releases) (Ensure both are in your System PATH)

### 2. Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
python backend.py
```
*Backend runs on `http://localhost:8000`*

### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```
*Frontend runs on `http://localhost:5173`*

---

## 🔬 How It Works

1. **Extraction**: The system uses `pytesseract` to scan documents. It specifically looks for words near dosage units (e.g., "500 mg") to intelligently identify medications while ignoring clinic headers and administrative text.
2. **Validation**: Each extracted word is validated against the **NIH RxNorm** database in parallel.
3. **Cross-Check**: When "Analyze Interaction" is triggered, the engine pairs every medication and performs a targeted search within the **FDA OpenFDA** interaction database.
4. **Translation**: The **Risk Decoder** scans for clinical severity markers and phrase-maps them to layperson-friendly warnings.

---

## ⚖️ Legal Disclaimer
PolySafe is a safety **awareness** tool for education and informational purposes only. It is **not** a substitute for professional medical advice, diagnosis, or treatment. Always consult with a licensed physician or registered pharmacist before making any changes to your medication regimen.

---

## 📊 Data Sources
- **Drug interactions**: [FDA OpenFDA](https://open.fda.gov)
- **Clinical Validation**: [NIH RxNorm API](https://rxnav.nlm.nih.gov)
