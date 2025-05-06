import os
import time
import telebot
import threading
import requests
from telebot import types
from config import TELEGRAM_TOKEN, ADMIN_ID

# בדיקה אם הסביבה היא Render
IS_RENDER = os.environ.get('RENDER', 'False').lower() == 'true'
PORT = int(os.environ.get('PORT', 10000))  # שינוי ברירת המחדל ל-10000 (נפוץ ב-Render)
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', None)

# ייבוא נוסף של מודולים מקומיים
from db_manager import DBManager
from ocr_service import OCRService

# יצירת מופע הבוט
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# יצירת מופעי השירותים
db = DBManager()
ocr_service = OCRService()

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
                print("[Keep-Alive] מבצע פעולת שמירה על עירנות...")
                
                if app_url:
                    # שליחת בקשת HTTP פשוטה לשרת שלך
                    response = requests.get(app_url)
                    print(f"[Keep-Alive] סטטוס תגובה: {response.status_code}")
                else:
                    # אם לא סופקה כתובת URL, פשוט רושמים לוג
                    print("[Keep-Alive] הפעלת פעולת ping (ללא URL)")
                
            except Exception as e:
                print(f"[Keep-Alive] שגיאה בביצוע פעולת שמירה על עירנות: {str(e)}")
            
            # המתנה של 10 דקות (600 שניות)
            time.sleep(600)
    
    # יצירת thread נפרד שירוץ ברקע
    keep_alive_thread = threading.Thread(target=keep_alive_job, daemon=True)
    keep_alive_thread.start()
    print("[Keep-Alive] מנגנון שמירה על עירנות הופעל בהצלחה")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """טיפול בפקודות התחלה ועזרה"""
    bot.reply_to(
        message,
        "ברוכים הבאים לבוט צייד לוחיות הרישוי! 🚗\n\n"
        "במשחק זה תצטרכו למצוא לוחיות רישוי עם מספרים מסוימים.\n"
        "כדי להתחיל משחק חדש, שלחו /start_game בקבוצה.\n"
        "לצפייה במספר הנוכחי לחיפוש, שלחו /current_number.\n\n"
        "בהצלחה!"
    )

@bot.message_handler(commands=['start_game'])
def start_game(message):
    """התחלת משחק חדש"""
    # בדיקה שההודעה נשלחה בקבוצה
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "ניתן להתחיל משחק רק בקבוצה!")
        return
    
    # אתחול המשחק
    group_id = message.chat.id
    
    # בחירת מספר ראשון לחיפוש
    number = db.select_next_number(group_id)
    
    if number is None:
        bot.reply_to(message, "כל המספרים כבר נמצאו! המשחק הסתיים 🎉")
        return
    
    # הכנת מקלדת אינליין
    markup = get_game_markup(group_id)
    
    # שליחת הודעת התחלה
    bot.send_message(
        group_id,
        f"המשחק התחיל! 🎮\n\n"
        f"המספר הראשון לחיפוש: {number}\n\n"
        f"צלמו לוחית רישוי עם המספר הזה ושלחו לכאן.",
        reply_markup=markup
    )

@bot.message_handler(commands=['current_number'])
def show_current_number(message):
    """הצגת המספר הנוכחי לחיפוש"""
    group_id = message.chat.id
    
    # קבלת המספר הנוכחי
    number = db.get_current_number(group_id)
    
    if number is None:
        # אין מספר נוכחי, בחירת מספר חדש
        number = db.select_next_number(group_id)
        
        if number is None:
            bot.reply_to(message, "כל המספרים כבר נמצאו! המשחק הסתיים 🎉")
            return
    
    # הכנת מקלדת אינליין
    markup = get_game_markup(group_id)
    
    # שליחת הודעה עם המספר הנוכחי
    bot.reply_to(
        message,
        f"המספר הנוכחי לחיפוש: {number}",
        reply_markup=markup
    )

@bot.message_handler(commands=['stats'])
def show_stats(message):
    """הצגת סטטיסטיקות משחק"""
    group_id = message.chat.id
    
    # קבלת סטטיסטיקות
    stats = db.get_stats(group_id)
    
    # שליחת הודעה עם הסטטיסטיקות
    bot.reply_to(
        message,
        f"📊 סטטיסטיקות משחק:\n\n"
        f"מספרים שנמצאו: {stats['found']}/{stats['total']} ({stats['percentage']}%)\n"
        f"מספרים שנותרו: {stats['remaining']}"
    )

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """טיפול בתמונות"""
    group_id = message.chat.id
    
    # קבלת המספר הנוכחי לחיפוש
    current_number = db.get_current_number(group_id)
    
    if current_number is None:
        # אין מספר נוכחי, בחירת מספר חדש
        current_number = db.select_next_number(group_id)
        
        if current_number is None:
            bot.reply_to(message, "כל המספרים כבר נמצאו! המשחק הסתיים 🎉")
            return
        
        bot.reply_to(message, f"המספר הנוכחי לחיפוש: {current_number}")
        return
    
    # שליחת הודעת טעינה
    loading_message = bot.reply_to(message, "🔍 מעבד את התמונה... אנא המתן")
    
    try:
        # קבלת התמונה הגדולה ביותר
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        
        # הורדת התמונה
        downloaded_file = bot.download_file(file_info.file_path)
        
        # וידוא שתיקיית הנתונים קיימת
        os.makedirs('data', exist_ok=True)
        
        # שמירת התמונה בזיכרון זמני
        image_path = f"data/temp_{message.message_id}.jpg"
        with open(image_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # זיהוי לוחית רישוי
        with open(image_path, 'rb') as image_file:
            ocr_result = ocr_service.recognize_plate(image_file)
        
        # חילוץ מספרי לוחיות
        plate_numbers = ocr_service.extract_plate_numbers(ocr_result)
        
        # שמירת התמונה ונתוני הזיהוי במסד הנתונים
        db.save_temp_image(
            message_id=message.message_id,
            image_path=image_path,
            user_id=message.from_user.id,
            username=message.from_user.first_name,
            current_number=current_number,
            group_id=group_id,
            plate_numbers=plate_numbers
        )
        
        # בדיקה אם המספר המבוקש נמצא
        current_number_str = str(current_number).zfill(3)
        found = any(current_number_str in plate for plate in plate_numbers)
        
        if found:
            # המספר נמצא!
            # מחיקת הודעת הטעינה
            bot.delete_message(group_id, loading_message.message_id)
            
            # סימון המספר כנמצא ובחירת מספר חדש
            next_number = db.mark_number_as_found(group_id, current_number, message.from_user.id)
            
            # שליחת הודעת הצלחה
            success_message = (
                f"🎉 מצוין! {message.from_user.first_name} מצא את המספר {current_number}!\n\n"
            )
            
            # יצירת כפתורים למנהל
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(
                "❌ פסול מציאה זו",
                callback_data=f"reject_{message.message_id}"
            ))
            
            # שליחת ההודעה למנהל
            bot.send_photo(
                ADMIN_ID,
                open(image_path, 'rb'),
                caption=f"מציאה חדשה אושרה!\n\n"
                        f"משתמש: {message.from_user.first_name}\n"
                        f"מספר: {current_number}\n"
                        f"מספרי לוחית שזוהו: {', '.join(plate_numbers)}",
                reply_markup=markup
            )
            
            # שליחת הודעת הצלחה לקבוצה
            if next_number is not None:
                success_message += f"המספר הבא לחיפוש: {next_number}"
                
                # הכנת מקלדת אינליין
                markup = get_game_markup(group_id)
                
                bot.reply_to(message, success_message, reply_markup=markup)
            else:
                success_message += "כל המספרים נמצאו! המשחק הסתיים 🎉"
                bot.reply_to(message, success_message)
        else:
            print(f"Plate numbers found: {plate_numbers}")

            # המספר לא נמצא
            # עדכון הודעת הטעינה
            bot.edit_message_text(
                f"❌ המספר {current_number} לא זוהה בתמונה.\n\n"
                f"מספרי לוחית שזוהו: {', '.join(plate_numbers or ['לא זוהו מספרים'])}",
                group_id,
                loading_message.message_id
            )
            
            # יצירת כפתורים למנהל
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(
                "✅ אשר למרות הכל",
                callback_data=f"approve_{message.message_id}"
            ))
            
            # שליחת ההודעה למנהל
            bot.send_photo(
                ADMIN_ID,
                open(image_path, 'rb'),
                caption=f"תמונה שלא אושרה אוטומטית:\n\n"
                        f"משתמש: {message.from_user.first_name}\n"
                        f"מספר לחיפוש: {current_number}\n"
                        f"מספרי לוחית שזוהו: {', '.join(plate_numbers or ['לא זוהו מספרים'])}",
                reply_markup=markup
            )
    
    except Exception as e:
        # שגיאה בעיבוד התמונה
        bot.edit_message_text(
            f"❌ שגיאה בעיבוד התמונה: {str(e)}",
            group_id,
            loading_message.message_id
        )
        print(f"Error processing image: {e}")
    
    finally:
        # ניקוי קבצים זמניים (יתבצע במנגנון ניקוי נפרד במערכת מלאה)
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_admin_actions(call):
    """טיפול בפעולות מנהל"""
    # בדיקה שזה אכן המנהל
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "אין לך הרשאות מנהל!")
        return
    
    # חילוץ מזהה ההודעה והפעולה
    action, message_id = call.data.split('_')
    message_id = int(message_id)
    
    # קבלת נתוני התמונה
    image_data = db.get_temp_image(message_id)
    
    # בדיקה שהנתונים עדיין קיימים
    if not image_data:
        bot.answer_callback_query(call.id, "הנתונים על התמונה הזו כבר לא זמינים.")
        return
    
    group_id = image_data['group_id']
    current_number = image_data['current_number']
    username = image_data['username']
    
    if action == 'approve':
        # אישור מציאה שלא זוהתה אוטומטית
        # סימון המספר כנמצא ובחירת מספר חדש
        next_number = db.mark_number_as_found(group_id, current_number, image_data['user_id'])
        
        # שליחת הודעה לקבוצה
        if next_number is not None:
            markup = get_game_markup(group_id)
            
            bot.send_message(
                group_id,
                f"✅ המנהל אישר את המציאה של {username} למספר {current_number}!\n\n"
                f"המספר הבא לחיפוש: {next_number}",
                reply_markup=markup
            )
        else:
            bot.send_message(
                group_id,
                f"✅ המנהל אישר את המציאה של {username} למספר {current_number}!\n\n"
                f"כל המספרים נמצאו! המשחק הסתיים 🎉"
            )
        
        # עדכון הודעת המנהל
        bot.edit_message_caption(
            caption=f"מציאה אושרה ידנית! ✅\n\n"
                   f"משתמש: {username}\n"
                   f"מספר: {current_number}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        
        # מחיקת המקלדת
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        
    elif action == 'reject':
        # פסילת מציאה שאושרה אוטומטית
        # החזרת המספר למאגר
        db.revert_found_number(group_id, current_number)
        
        # שליחת הודעה לקבוצה
        markup = get_game_markup(group_id)
        
        bot.send_message(
            group_id,
            f"❌ המנהל פסל את המציאה של {username} למספר {current_number}.\n\n"
            f"המספר {current_number} חזר למאגר החיפוש.",
            reply_markup=markup
        )
        
        # עדכון הודעת המנהל
        bot.edit_message_caption(
            caption=f"מציאה נפסלה! ❌\n\n"
                   f"משתמש: {username}\n"
                   f"מספר: {current_number}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        
        # מחיקת המקלדת
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    
    # עדכון למנהל
    bot.answer_callback_query(call.id, "הפעולה בוצעה בהצלחה!")
    
    # ניקוי נתוני התמונה
    if os.path.exists(image_data['image_path']):
        os.remove(image_data['image_path'])
    db.delete_temp_image(message_id)

def get_game_markup(group_id):
    """יצירת מקלדת אינליין למשחק"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # קבלת המספר הנוכחי
    current_number = db.get_current_number(group_id)
    
    # קבלת סטטיסטיקות
    stats = db.get_stats(group_id)
    
    # הוספת כפתורים
    markup.add(
        types.InlineKeyboardButton(f"מספר נוכחי: {current_number}", callback_data="current"),
        types.InlineKeyboardButton(f"נותרו: {stats['remaining']}", callback_data="stats")
    )
    
    return markup

@bot.callback_query_handler(func=lambda call: call.data in ["current", "stats"])
def handle_inline_buttons(call):
    """טיפול בלחיצות על כפתורים אינליין"""
    group_id = call.message.chat.id
    
    if call.data == "current":
        # הצגת המספר הנוכחי
        current_number = db.get_current_number(group_id)
        if current_number is None:
            bot.answer_callback_query(call.id, "אין מספר נוכחי לחיפוש!")
        else:
            bot.answer_callback_query(call.id, f"המספר הנוכחי לחיפוש: {current_number}")
    
    elif call.data == "stats":
        # הצגת סטטיסטיקות
        stats = db.get_stats(group_id)
        bot.answer_callback_query(
            call.id,
            f"נמצאו: {stats['found']}/{stats['total']} ({stats['percentage']}%)",
            show_alert=True
        )

# הפעלת הבוט
def main():
    print("הבוט מופעל...")
    
    # וידוא שתיקיית הנתונים קיימת
    os.makedirs('data', exist_ok=True)
    
    # ניקוי תמונות זמניות ישנות
    db.clean_old_temp_images(hours=24)
    
    try:
        # בחירת מצב הפעלה לפי הסביבה (webhook לרנדר או polling מקומי)
        if IS_RENDER:
            # הגדרת webhook עבור Render
            print(f"מפעיל במצב webhook עבור Render")
            
            if not WEBHOOK_URL:
                print("אזהרה: WEBHOOK_URL לא מוגדר. ייתכן שהבוט לא יעבוד כראוי.")
                # השתמש בכתובת ברירת מחדל אם לא הוגדרה
                service_name = os.environ.get('RENDER_SERVICE_NAME', 'app')
                webhook_url = f"https://{service_name}.onrender.com/{TELEGRAM_TOKEN}"
            else:
                webhook_url = WEBHOOK_URL
                
            # הפעלת מנגנון Keep-Alive עם כתובת ה-webhook
            # הוצא את חלק הנתיב מ-webhook_url כדי לקבל רק את כתובת הבסיס
            base_url = webhook_url.split('/' + TELEGRAM_TOKEN)[0] if TELEGRAM_TOKEN in webhook_url else webhook_url
            print(f"מפעיל מנגנון Keep-Alive עם URL: {base_url}")
            setup_keep_alive(base_url)
            
            # הסרת webhook קיים והגדרת webhook חדש
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=webhook_url)
            
            # הפעלת שרת Flask לקבלת עדכונים
            from flask import Flask, request
            app = Flask(__name__)
            
            @app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
            def webhook():
                try:
                    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
                    bot.process_new_updates([update])
                    return ''
                except Exception as e:
                    print(f"שגיאה בטיפול בעדכון: {e}")
                    return 'error'
            
            @app.route('/')
            def index():
                return "בוט צייד לוחיות רישוי פעיל!"
            
            # הפעלת שרת - שינוי ל-debug=False
            print(f"מפעיל שרת על פורט {PORT}")
            app.run(host='0.0.0.0', port=PORT, debug=False)
        else:
            # הפעלה במצב polling (מקומי)
            print("מפעיל במצב polling")
            bot.remove_webhook()
            time.sleep(1)
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("הבוט הופסק על ידי המשתמש.")
    except Exception as e:
        print(f"שגיאה קריטית בהפעלת הבוט: {e}")

if __name__ == '__main__':
    main()