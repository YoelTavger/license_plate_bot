import os
import telebot
from telebot import types
from config import ADMIN_ID, TELEGRAM_TOKEN
import logging

# הגדרת לוגר
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# יצירת מופע הבוט
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# טעינת שירותים מודולים אחרים
from ocr_service import OCRService
from db_manager import DBManager

# יצירת מופעי השירותים
db = DBManager()
ocr_service = OCRService()

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
            try:
                bot.reply_to(message, "כל המספרים כבר נמצאו! המשחק הסתיים 🎉")
            except Exception as e:
                logger.error(f"שגיאה בשליחת תגובה: {e}")
                bot.send_message(group_id, "כל המספרים כבר נמצאו! המשחק הסתיים 🎉")
            return
        
        try:
            bot.reply_to(message, f"המספר הנוכחי לחיפוש: {current_number}")
        except Exception as e:
            logger.error(f"שגיאה בשליחת תגובה: {e}")
            bot.send_message(group_id, f"המספר הנוכחי לחיפוש: {current_number}")
        return
    
    try:
        # שליחת הודעת טעינה - ננסה כתגובה, אם נכשל נשלח כהודעה רגילה
        try:
            loading_message = bot.reply_to(message, "🔍 מעבד את התמונה... אנא המתן")
        except Exception as reply_error:
            logger.warning(f"לא ניתן לשלוח תגובה: {reply_error}")
            loading_message = bot.send_message(group_id, "🔍 מעבד את התמונה... אנא המתן")
        
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
            try:
                # מחיקת הודעת הטעינה - עטוף בtry-except למניעת שגיאות
                bot.delete_message(group_id, loading_message.message_id)
            except Exception as delete_error:
                logger.warning(f"לא ניתן למחוק הודעת טעינה: {delete_error}")
            
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
            try:
                bot.send_photo(
                    ADMIN_ID,
                    open(image_path, 'rb'),
                    caption=f"מציאה חדשה אושרה!\n\n"
                            f"משתמש: {message.from_user.first_name}\n"
                            f"מספר: {current_number}\n"
                            f"מספרי לוחית שזוהו: {', '.join(plate_numbers)}",
                    reply_markup=markup
                )
            except Exception as admin_error:
                logger.error(f"שגיאה בשליחת הודעה למנהל: {admin_error}")
            
            # שליחת הודעת הצלחה לקבוצה
            if next_number is not None:
                success_message += f"המספר הבא לחיפוש: {next_number}"
                
                # הכנת מקלדת אינליין
                markup = get_game_markup(group_id)
                
                # ננסה להשתמש בתגובה, אם נכשל נשלח הודעה רגילה
                try:
                    bot.reply_to(message, success_message, reply_markup=markup)
                except Exception as reply_error:
                    logger.warning(f"לא ניתן לשלוח תגובה: {reply_error}")
                    bot.send_message(group_id, success_message, reply_markup=markup)
            else:
                success_message += "כל המספרים נמצאו! המשחק הסתיים 🎉"
                try:
                    bot.reply_to(message, success_message)
                except Exception as reply_error:
                    logger.warning(f"לא ניתן לשלוח תגובה: {reply_error}")
                    bot.send_message(group_id, success_message)
        else:
            logger.info(f"Plate numbers found: {plate_numbers}")

            # המספר לא נמצא
            try:
                # עדכון הודעת הטעינה - עטוף בtry-except למניעת שגיאות
                bot.edit_message_text(
                    f"❌ המספר {current_number} לא זוהה בתמונה.\n\n"
                    f"מספרי לוחית שזוהו: {', '.join(plate_numbers or ['לא זוהו מספרים'])}",
                    group_id,
                    loading_message.message_id
                )
            except Exception as edit_error:
                logger.warning(f"לא ניתן לערוך הודעת טעינה: {edit_error}")
                # ננסה לשלוח תגובה, אם נכשל נשלח הודעה רגילה
                try:
                    bot.reply_to(
                        message,
                        f"❌ המספר {current_number} לא זוהה בתמונה.\n\n"
                        f"מספרי לוחית שזוהו: {', '.join(plate_numbers or ['לא זוהו מספרים'])}"
                    )
                except Exception as reply_error:
                    logger.warning(f"לא ניתן לשלוח תגובה: {reply_error}")
                    bot.send_message(
                        group_id,
                        f"❌ המספר {current_number} לא זוהה בתמונה.\n\n"
                        f"מספרי לוחית שזוהו: {', '.join(plate_numbers or ['לא זוהו מספרים'])}"
                    )
            
            # יצירת כפתורים למנהל
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(
                "✅ אשר למרות הכל",
                callback_data=f"approve_{message.message_id}"
            ))
            
            # שליחת ההודעה למנהל
            try:
                bot.send_photo(
                    ADMIN_ID,
                    open(image_path, 'rb'),
                    caption=f"תמונה שלא אושרה אוטומטית:\n\n"
                            f"משתמש: {message.from_user.first_name}\n"
                            f"מספר לחיפוש: {current_number}\n"
                            f"מספרי לוחית שזוהו: {', '.join(plate_numbers or ['לא זוהו מספרים'])}",
                    reply_markup=markup
                )
            except Exception as admin_error:
                logger.error(f"שגיאה בשליחת הודעה למנהל: {admin_error}")
    
    except Exception as e:
        # שגיאה בעיבוד התמונה
        try:
            # עדכון הודעת הטעינה אם היא קיימת
            if 'loading_message' in locals():
                try:
                    bot.edit_message_text(
                        f"❌ שגיאה בעיבוד התמונה: {str(e)}",
                        group_id,
                        loading_message.message_id
                    )
                except:
                    pass
            
            # ננסה לשלוח תגובה, אם נכשל נשלח הודעה רגילה
            try:
                bot.reply_to(message, f"❌ שגיאה בעיבוד התמונה: {str(e)}")
            except Exception as reply_error:
                logger.warning(f"לא ניתן לשלוח תגובה: {reply_error}")
                bot.send_message(group_id, f"❌ שגיאה בעיבוד התמונה: {str(e)}")
        except Exception as final_error:
            logger.error(f"שגיאה חמורה בטיפול בתמונה: {final_error}")
                
        logger.error(f"Error processing image: {e}")
    
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

# פונקציה לבדיקת סטטוס הבוט
def test_bot():
    """בדיקת סטטוס הבוט"""
    try:
        # בדיקת חיבור למסד נתונים
        db_ok = db.test_connection()
        
        # בדיקת תקינות הטוקן
        bot_info = bot.get_me()
        bot_ok = True
        
        logger.info(f"בדיקת סטטוס בוט: מסד נתונים - {'תקין' if db_ok else 'שגיאה'}, בוט - {'תקין' if bot_ok else 'שגיאה'}")
        logger.info(f"פרטי הבוט: @{bot_info.username} (ID: {bot_info.id})")
        
        return db_ok and bot_ok, {
            'db': db_ok,
            'bot': bot_ok,
            'bot_info': bot_info if bot_ok else None
        }
    except Exception as e:
        logger.error(f"שגיאה בבדיקת סטטוס בוט: {e}")
        return False, {'error': str(e)}