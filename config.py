import os
import socket
import sys
from dotenv import load_dotenv

# טעינת משתני סביבה
load_dotenv()

# פונקציה לזיהוי אוטומטי של סביבת הרצה
def detect_environment():
    """
    זיהוי אוטומטי של סביבת ההרצה (מקומית או Render)
    
    הפונקציה בודקת מספר מאפיינים כדי להחליט אם הסביבה היא Render:
    1. בדיקת משתנה סביבה RENDER (אם הוגדר מפורשות)
    2. בדיקת משתנה סביבה RENDER_SERVICE_NAME (ייחודי ל-Render)
    3. בדיקת שם המחשב (hostname)
    
    Returns:
        bool: True אם הסביבה מזוהה כ-Render, אחרת False
    """
    # בדיקה אם המשתנה RENDER הוגדר מפורשות
    render_env = os.environ.get('RENDER', '').lower()
    if render_env in ['true', '1', 'yes']:
        return True
    if render_env in ['false', '0', 'no']:
        return False
        
    # בדיקה אם קיים משתנה סביבה ייחודי ל-Render
    if os.environ.get('RENDER_SERVICE_NAME'):
        return True
        
    # בדיקת שם המחשב (בדרך כלל מכיל "render" בסביבת Render)
    try:
        hostname = socket.gethostname()
        if 'render' in hostname.lower():
            return True
    except:
        pass
        
    # ברירת מחדל: להניח שזו סביבה מקומית
    return False

# בדיקה אם הסביבה היא Render
IS_RENDER = detect_environment()

# טוקן לבוט טלגרם - לעולם לא להציג בקוד
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    print("אזהרה: TELEGRAM_TOKEN לא מוגדר! הבוט לא יעבוד כראוי.")

# טוקן ל-API של זיהוי לוחיות - לעולם לא להציג בקוד
PLATE_RECOGNIZER_TOKEN = os.environ.get('PLATE_RECOGNIZER_TOKEN')
if not PLATE_RECOGNIZER_TOKEN:
    print("אזהרה: PLATE_RECOGNIZER_TOKEN לא מוגדר! זיהוי לוחיות לא יעבוד כראוי.")

PLATE_RECOGNIZER_API_URL = os.environ.get('PLATE_RECOGNIZER_API_URL', 'https://api.platerecognizer.com/v1/plate-reader/')

# מזהה של המנהל
try:
    ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))
    if ADMIN_ID == 0:
        print("אזהרה: ADMIN_ID לא מוגדר! פונקציות ניהול לא יעבודו כראוי.")
except ValueError:
    print("שגיאה: ADMIN_ID חייב להיות מספר שלם!")
    ADMIN_ID = 0

# פרטי התחברות למסד נתונים
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')

# בדיקת קיום פרטי התחברות למסד נתונים
if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    print("אזהרה: חלק מפרטי ההתחברות למסד הנתונים חסרים!")

# הגדרות לוחיות רישוי
REGIONS = ["il"]  # קוד מדינה לישראל

# הגדרות שרת
PORT = int(os.environ.get('PORT', 10000))  # ברירת מחדל לפורט 10000
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

# פונקצית דיאגנוסטיקה - הדפסת פרטי התצורה ללא חשיפת מידע רגיש
def print_config_info():
    """הדפסת פרטי תצורה למטרות דיאגנוסטיקה"""
    print(f"===== פרטי תצורה =====")
    print(f"סביבת הרצה: {'Render' if IS_RENDER else 'מקומית'}")
    print(f"TELEGRAM_TOKEN: {'מוגדר' if TELEGRAM_TOKEN else 'לא מוגדר'}")
    print(f"PLATE_RECOGNIZER_TOKEN: {'מוגדר' if PLATE_RECOGNIZER_TOKEN else 'לא מוגדר'}")
    print(f"ADMIN_ID: {ADMIN_ID if ADMIN_ID != 0 else 'לא מוגדר'}")
    print(f"פרטי התחברות למסד נתונים: {'מוגדרים' if all([DB_HOST, DB_PORT, DB_NAME, DB_USER]) else 'חסרים'}")
    print(f"פורט: {PORT}")
    print(f"WEBHOOK_URL: {'מוגדר' if WEBHOOK_URL else 'לא מוגדר'}")
    print(f"REGIONS: {REGIONS}")
    print(f"========================")