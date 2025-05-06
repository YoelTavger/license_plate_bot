import os
from dotenv import load_dotenv

# טעינת משתני סביבה
load_dotenv()

# טוקן לבוט טלגרם
TELEGRAM_TOKEN = '6309037100:AAFz7e8FmI53--cM1s0oR6cXIw1ECcxAyAU'

# טוקן ל-API של זיהוי לוחיות
PLATE_RECOGNIZER_TOKEN = '41b42b7083e058a39581b4e6e7dcb2bad727638e'
PLATE_RECOGNIZER_API_URL = 'https://api.platerecognizer.com/v1/plate-reader/'

# מזהה של המנהל
ADMIN_ID = 599028048

# הגדרות לוחיות רישוי
REGIONS = ["il"]  # קוד מדינה לישראל