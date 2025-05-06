import os
import time
import threading
import requests
import logging
from flask import Flask
import telebot
from config import IS_RENDER, PORT, WEBHOOK_URL, TELEGRAM_TOKEN, print_config_info
from bot_handlers import bot, test_bot, db

# הגדרת לוגר
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# אפליקציית Flask עבור webhook
app = Flask(__name__)

@app.route('/')
def index():
    """עמוד הבית של השירות"""
    return "בוט צייד לוחיות רישוי פעיל!"

@app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def webhook():
    """נקודת קצה לקבלת עדכונים מטלגרם במצב webhook"""
    try:
        from flask import request
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        bot.process_new_updates([update])
        return ''
    except Exception as e:
        logger.error(f"שגיאה בטיפול בעדכון: {e}")
        return 'error'

# מנגנון שמירה על עירנות לסביבת Render
def setup_keep_alive(app_url=None):
    """
    הגדרת מנגנון שמונע מהשרת להירדם על ידי ביצוע פינג כל 10 דקות.
    
    פרמטרים:
    app_url (str): כתובת URL של האפליקציה (אופציונלי). אם לא מסופק, יבוצע רק לוג.
    """
    
    def keep_alive_job():
        while True:
            try:
                logger.info("[Keep-Alive] מבצע פעולת שמירה על עירנות...")
                
                if app_url:
                    # שליחת בקשת HTTP פשוטה לשרת שלך
                    response = requests.get(app_url)
                    logger.info(f"[Keep-Alive] סטטוס תגובה: {response.status_code}")
                else:
                    # אם לא סופקה כתובת URL, פשוט רושמים לוג
                    logger.info("[Keep-Alive] הפעלת פעולת ping (ללא URL)")
                
            except Exception as e:
                logger.error(f"[Keep-Alive] שגיאה בביצוע פעולת שמירה על עירנות: {str(e)}")
            
            # המתנה של 10 דקות (600 שניות)
            time.sleep(600)
    
    # יצירת thread נפרד שירוץ ברקע
    keep_alive_thread = threading.Thread(target=keep_alive_job, daemon=True)
    keep_alive_thread.start()
    logger.info("[Keep-Alive] מנגנון שמירה על עירנות הופעל בהצלחה")

def main():
    """פונקציה ראשית להפעלת הבוט"""
    # הצגת פרטי תצורה
    print_config_info()
    
    logger.info("הבוט מופעל...")
    
    # וידוא שתיקיית הנתונים קיימת
    os.makedirs('data', exist_ok=True)
    
    # ניקוי תמונות זמניות ישנות
    db.clean_old_temp_images(hours=24)
    
    # בדיקת סטטוס הבוט
    status_ok, status_info = test_bot()
    if not status_ok:
        logger.error(f"הבוט לא הופעל עקב שגיאה בבדיקת סטטוס: {status_info}")
        return
    
    try:
        # בחירת מצב הפעלה לפי הסביבה (webhook לרנדר או polling מקומי)
        if IS_RENDER:
            # הגדרת webhook עבור Render
            logger.info("מפעיל במצב webhook עבור Render")
            
            if not WEBHOOK_URL:
                logger.warning("אזהרה: WEBHOOK_URL לא מוגדר. ייתכן שהבוט לא יעבוד כראוי.")
                # השתמש בכתובת ברירת מחדל אם לא הוגדרה
                service_name = os.environ.get('RENDER_SERVICE_NAME', 'app')
                webhook_url = f"https://{service_name}.onrender.com/{TELEGRAM_TOKEN}"
            else:
                webhook_url = WEBHOOK_URL
                
            # הפעלת מנגנון Keep-Alive עם כתובת ה-webhook
            # הוצא את חלק הנתיב מ-webhook_url כדי לקבל רק את כתובת הבסיס
            base_url = webhook_url.split('/' + TELEGRAM_TOKEN)[0] if TELEGRAM_TOKEN in webhook_url else webhook_url
            logger.info(f"מפעיל מנגנון Keep-Alive עם URL: {base_url}")
            setup_keep_alive(base_url)
            
            # הסרת webhook קיים והגדרת webhook חדש
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=webhook_url)
            
            # הפעלת שרת
            logger.info(f"מפעיל שרת על פורט {PORT}")
            app.run(host='0.0.0.0', port=PORT, debug=False)
        else:
            # הפעלה במצב polling (מקומי)
            logger.info("מפעיל במצב polling מקומי")
            bot.remove_webhook()
            time.sleep(1)
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        logger.info("הבוט הופסק על ידי המשתמש.")
    except Exception as e:
        logger.error(f"שגיאה קריטית בהפעלת הבוט: {e}")

if __name__ == '__main__':
    main()