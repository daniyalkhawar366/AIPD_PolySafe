import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import re

# Set paths for Windows
import sys
if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\HP\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
    POPPLER_PATH = r'C:\Users\HP\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin'
else:
    POPPLER_PATH = None

def extract_text(file_path):
    """
    Accept: PDF, JPG, PNG
    Output: Raw extracted text string
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_ext == '.pdf':
            images = convert_from_path(file_path, poppler_path=POPPLER_PATH)
            raw_text = ""
            for img in images:
                raw_text += pytesseract.image_to_string(img) + "\n"
            return raw_text
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            img = Image.open(file_path)
            raw_text = pytesseract.image_to_string(img)
            return raw_text
        else:
            return ""
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""

# Basic high-freq stop-words to skip obvious noise
STOP_WORDS = {'The', 'And', 'For', 'With', 'From', 'Each', 'Take', 'This', 'That', 'These', 'Those'}

def parse_drug_names(raw_text):
    """
    Automated drug extraction logic.
    Identifies candidates by:
    1. Being alphabet-only and >= 3 characters.
    2. Not being a basic English stop-word.
    3. (Bonus) Often accompanied by dosage in next few words (contextual hinting).
    """
    lines = raw_text.split('\n')
    candidates = []
    
    # regex for identifying dosage (e.g., 500mg, 10 ml)
    dosage_pattern = re.compile(r'\d+\s*(mg|ml|mcg|iu|tablet|pill|cap|spoon|drop)', re.IGNORECASE)
    
    for line in lines:
        # Check if the line has a dosage hint - high probability of drug name presence
        has_dosage = dosage_pattern.search(line)
        
        # Clean symbols but keep structure for splitting
        clean_line = re.sub(r'[^\w\s]', ' ', line)
        tokens = clean_line.split()
        
        for i, token in enumerate(tokens):
            cleaned = token.capitalize()
            
            if len(cleaned) < 3 or not cleaned.isalpha() or cleaned in STOP_WORDS:
                continue
                
            # If the word is near a dosage hint, it's very likely a drug
            # if not, it's still a candidate to be validated by the API
            candidates.append(cleaned)
    
    # Return unique and sorted
    return sorted(list(set(candidates)))

if __name__ == '__main__':
    # Test code
    t = extract_text('data/sample_prescription_1.pdf')
    print(parse_drug_names(t))
