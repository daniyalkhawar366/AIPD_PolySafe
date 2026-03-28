from database import get_connection
from datetime import datetime

def add_medication(user_id, drug_name, rxcui, source):
    """Add a medication to the user's profile."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO medications (user_id, drug_name, rxcui, date_added, source)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, drug_name, rxcui, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source))
    conn.commit()
    conn.close()

def get_medications(user_id):
    """Fetch all medications for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, drug_name, rxcui, date_added, source FROM medications WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    meds = []
    for row in rows:
        meds.append({
            'id': row[0],
            'name': row[1],
            'rxcui': row[2],
            'date': row[3],
            'source': row[4]
        })
    return meds

def delete_medication(med_id):
    """Delete a medication by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM medications WHERE id = ?', (med_id,))
    conn.commit()
    conn.close()

def clear_profile(user_id):
    """Clear all medications for a user (useful for session management)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM medications WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
