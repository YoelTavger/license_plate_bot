import psycopg2
import random
from psycopg2.extras import DictCursor
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
import logging
from datetime import datetime, timedelta

# הגדרת לוגר
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class DBManager:
    """
    מנהל מסד נתונים PostgreSQL
    """
    
    def __init__(self):
        """אתחול מנהל מסד הנתונים"""
        # פרטי התחברות למסד הנתונים
        self.db_params = {
            'host': DB_HOST,
            'port': DB_PORT,
            'database': DB_NAME,
            'user': DB_USER,
            'password': DB_PASSWORD
        }
        
        # יצירת טבלאות אם לא קיימות
        self._create_tables()
    
    def _get_connection(self):
        """יצירת חיבור למסד הנתונים"""
        return psycopg2.connect(**self.db_params)
    
    def test_connection(self):
        """בדיקת חיבור למסד הנתונים"""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            result = cur.fetchone()
            cur.close()
            conn.close()
            logger.info("חיבור למסד הנתונים תקין!")
            return True
        except Exception as e:
            logger.error(f"שגיאה בחיבור למסד הנתונים: {e}")
            return False
    
    def _create_tables(self):
        """יצירת טבלאות במסד הנתונים אם לא קיימות"""
        # יצירת חיבור
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # טבלת קבוצות
            cur.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    group_id BIGINT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # טבלת מספרים לקבוצה
            cur.execute("""
                CREATE TABLE IF NOT EXISTS numbers (
                    id SERIAL PRIMARY KEY,
                    group_id BIGINT REFERENCES groups(group_id),
                    number INTEGER NOT NULL,
                    is_current BOOLEAN DEFAULT FALSE,
                    is_found BOOLEAN DEFAULT FALSE,
                    found_by BIGINT,
                    found_at TIMESTAMP,
                    UNIQUE(group_id, number)
                )
            """)
            
            # טבלת תמונות זמניות
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temp_images (
                    message_id BIGINT PRIMARY KEY,
                    image_path TEXT,
                    user_id BIGINT,
                    username TEXT,
                    group_id BIGINT,
                    current_number INTEGER,
                    plate_numbers TEXT[],
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # שמירת השינויים
            conn.commit()
            logger.info("טבלאות המסד נוצרו/אומתו בהצלחה")
            
        except Exception as e:
            logger.error(f"שגיאה ביצירת טבלאות: {e}")
            conn.rollback()
            
        finally:
            # סגירת החיבור
            cur.close()
            conn.close()
    
    def init_group(self, group_id):
        """אתחול מאגר מספרים חדש לקבוצה"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # בדיקה אם הקבוצה כבר קיימת
            cur.execute("SELECT group_id FROM groups WHERE group_id = %s", (group_id,))
            if cur.fetchone() is None:
                # יצירת רשומת קבוצה חדשה
                cur.execute("INSERT INTO groups (group_id) VALUES (%s)", (group_id,))
                logger.info(f"הקבוצה {group_id} נוצרה במסד הנתונים")
                
                # יצירת מאגר מספרים (0-999)
                for number in range(1000):
                    cur.execute(
                        "INSERT INTO numbers (group_id, number, is_found, is_current) VALUES (%s, %s, %s, %s)",
                        (group_id, number, False, False)
                    )
                logger.info(f"מאגר מספרים נוצר עבור הקבוצה {group_id}")
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"שגיאה באתחול קבוצה: {e}")
            conn.rollback()
            return False
            
        finally:
            cur.close()
            conn.close()
    
    def select_next_number(self, group_id):
        """בחירת המספר הבא לחיפוש"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # וידוא שהקבוצה מאותחלת
            self.init_group(group_id)
            
            # איפוס כל המספרים הנוכחיים
            cur.execute(
                "UPDATE numbers SET is_current = FALSE WHERE group_id = %s",
                (group_id,)
            )
            
            # בחירת מספר אקראי שעדיין לא נמצא
            cur.execute(
                "SELECT number FROM numbers WHERE group_id = %s AND is_found = FALSE",
                (group_id,)
            )
            available_numbers = [row[0] for row in cur.fetchall()]
            
            if not available_numbers:
                logger.info(f"אין מספרים זמינים עבור הקבוצה {group_id}")
                return None
            
            # בחירת מספר אקראי מהזמינים
            current_number = random.choice(available_numbers)
            
            # עדכון המספר הנוכחי
            cur.execute(
                "UPDATE numbers SET is_current = TRUE WHERE group_id = %s AND number = %s",
                (group_id, current_number)
            )
            
            conn.commit()
            logger.info(f"המספר {current_number} נבחר כמספר הנוכחי לקבוצה {group_id}")
            return current_number
            
        except Exception as e:
            logger.error(f"שגיאה בבחירת מספר הבא: {e}")
            conn.rollback()
            return None
            
        finally:
            cur.close()
            conn.close()
    
    def get_current_number(self, group_id):
        """קבלת המספר הנוכחי לחיפוש"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # וידוא שהקבוצה מאותחלת
            self.init_group(group_id)
            
            # קבלת המספר הנוכחי
            cur.execute(
                "SELECT number FROM numbers WHERE group_id = %s AND is_current = TRUE",
                (group_id,)
            )
            result = cur.fetchone()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"שגיאה בקבלת מספר נוכחי: {e}")
            return None
            
        finally:
            cur.close()
            conn.close()
    
    def mark_number_as_found(self, group_id, number, user_id=None):
        """סימון מספר כנמצא"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # עדכון המספר כנמצא
            cur.execute(
                """
                UPDATE numbers 
                SET is_found = TRUE, is_current = FALSE, found_by = %s, found_at = CURRENT_TIMESTAMP
                WHERE group_id = %s AND number = %s
                """,
                (user_id, group_id, number)
            )
            
            conn.commit()
            logger.info(f"המספר {number} סומן כנמצא על ידי המשתמש {user_id} בקבוצה {group_id}")
            
            # בחירת מספר חדש
            return self.select_next_number(group_id)
            
        except Exception as e:
            logger.error(f"שגיאה בסימון מספר כנמצא: {e}")
            conn.rollback()
            return None
            
        finally:
            cur.close()
            conn.close()
    
    def revert_found_number(self, group_id, number):
        """החזרת מספר למאגר (פסילת מציאה)"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # איפוס כל המספרים הנוכחיים
            cur.execute(
                "UPDATE numbers SET is_current = FALSE WHERE group_id = %s",
                (group_id,)
            )
            
            # החזרת המספר למאגר
            cur.execute(
                """
                UPDATE numbers 
                SET is_found = FALSE, is_current = TRUE, found_by = NULL, found_at = NULL
                WHERE group_id = %s AND number = %s
                """,
                (group_id, number)
            )
            
            conn.commit()
            logger.info(f"המספר {number} הוחזר למאגר בקבוצה {group_id}")
            return number
            
        except Exception as e:
            logger.error(f"שגיאה בהחזרת מספר למאגר: {e}")
            conn.rollback()
            return None
            
        finally:
            cur.close()
            conn.close()
    
    def get_stats(self, group_id):
        """קבלת סטטיסטיקות משחק"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        try:
            # וידוא שהקבוצה מאותחלת
            self.init_group(group_id)
            
            # קבלת סטטיסטיקות
            cur.execute("""
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN is_found THEN 1 ELSE 0 END) AS found
                FROM numbers
                WHERE group_id = %s
            """, (group_id,))
            
            result = dict(cur.fetchone())
            result['found'] = int(result['found']) if result['found'] else 0  # המרה ל-int (לפעמים מוחזר כ-Decimal)
            result['remaining'] = result['total'] - result['found']
            result['percentage'] = round((result['found'] / result['total']) * 100, 2) if result['total'] > 0 else 0
            
            logger.info(f"נקראו סטטיסטיקות עבור קבוצה {group_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"שגיאה בקבלת סטטיסטיקות: {e}")
            return {'total': 1000, 'found': 0, 'remaining': 1000, 'percentage': 0}
            
        finally:
            cur.close()
            conn.close()
    
    def save_temp_image(self, message_id, image_path, user_id, username, group_id, current_number, plate_numbers):
        """שמירת נתוני תמונה זמנית"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # הוספת התמונה למסד הנתונים
            cur.execute("""
                INSERT INTO temp_images 
                (message_id, image_path, user_id, username, group_id, current_number, plate_numbers)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO UPDATE
                SET image_path = EXCLUDED.image_path,
                    user_id = EXCLUDED.user_id,
                    username = EXCLUDED.username,
                    group_id = EXCLUDED.group_id,
                    current_number = EXCLUDED.current_number,
                    plate_numbers = EXCLUDED.plate_numbers
            """, (
                message_id, image_path, user_id, username, group_id, current_number, plate_numbers
            ))
            
            conn.commit()
            logger.info(f"נשמרה תמונה זמנית למסד הנתונים, message_id={message_id}")
            return True
            
        except Exception as e:
            logger.error(f"שגיאה בשמירת תמונה זמנית: {e}")
            conn.rollback()
            return False
            
        finally:
            cur.close()
            conn.close()
    
    def get_temp_image(self, message_id):
        """קבלת נתוני תמונה זמנית"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cur.execute("SELECT * FROM temp_images WHERE message_id = %s", (message_id,))
            result = cur.fetchone()
            
            if result:
                logger.info(f"נמצאו נתוני תמונה זמנית, message_id={message_id}")
                return dict(result)
            else:
                logger.warning(f"לא נמצאו נתוני תמונה זמנית, message_id={message_id}")
                return None
            
        except Exception as e:
            logger.error(f"שגיאה בקבלת תמונה זמנית: {e}")
            return None
            
        finally:
            cur.close()
            conn.close()
    
    def delete_temp_image(self, message_id):
        """מחיקת נתוני תמונה זמנית"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("DELETE FROM temp_images WHERE message_id = %s", (message_id,))
            conn.commit()
            logger.info(f"נמחקו נתוני תמונה זמנית, message_id={message_id}")
            return True
            
        except Exception as e:
            logger.error(f"שגיאה במחיקת תמונה זמנית: {e}")
            conn.rollback()
            return False
            
        finally:
            cur.close()
            conn.close()
    
    def clean_old_temp_images(self, hours=24):
        """ניקוי תמונות זמניות ישנות"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute(
                "DELETE FROM temp_images WHERE created_at < NOW() - INTERVAL '%s hours' RETURNING message_id",
                (hours,)
            )
            
            deleted_rows = cur.fetchall()
            deleted_count = len(deleted_rows)
            
            conn.commit()
            logger.info(f"נוקו {deleted_count} תמונות זמניות ישנות (מלפני {hours} שעות)")
            return True
            
        except Exception as e:
            logger.error(f"שגיאה בניקוי תמונות זמניות: {e}")
            conn.rollback()
            return False
            
        finally:
            cur.close()
            conn.close()