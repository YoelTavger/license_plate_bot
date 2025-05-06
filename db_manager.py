import psycopg2
import random
from psycopg2.extras import DictCursor
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db_manager.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DBManager")

class DBManager:
    """
    מנהל מסד נתונים PostgreSQL עם טיפול שגיאות משופר
    """
    
    def __init__(self, max_retries=3):
        """אתחול מנהל מסד הנתונים"""
        # פרטי התחברות למסד הנתונים
        self.db_params = {
            'host': 'dpg-d0cmiqemcj7s73antifg-a.oregon-postgres.render.com',
            'port': 5432,
            'database': 'license_plate_db',
            'user': 'license_plate_admin',
            'password': 'qGVtVXMcsxAdVodYzr9nF6ekJibYXDC2'
        }
        
        self.max_retries = max_retries
        
        # יצירת טבלאות אם לא קיימות
        self._create_tables()
    
    def _get_connection(self):
        """יצירת חיבור למסד הנתונים עם ניסיונות חוזרים"""
        retries = 0
        while retries < self.max_retries:
            try:
                return psycopg2.connect(**self.db_params)
            except psycopg2.OperationalError as e:
                retries += 1
                wait_time = 2 ** retries  # exponential backoff
                logger.warning(f"Connection failed (attempt {retries}/{self.max_retries}). Retrying in {wait_time}s. Error: {e}")
                time.sleep(wait_time)
        
        # אם לא הצלחנו להתחבר לאחר כל הניסיונות
        raise Exception("Failed to connect to database after multiple attempts")
    
    def _create_tables(self):
        """יצירת טבלאות במסד הנתונים אם לא קיימות"""
        # יצירת חיבור
        conn = None
        cur = None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            logger.info("Checking database schema...")
            
            # בדיקה אם הטבלאות קיימות
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'groups')")
            groups_exists = cur.fetchone()[0]
            
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'numbers')")
            numbers_exists = cur.fetchone()[0]
            
            # אם הטבלאות קיימות, בדיקה אם עמודת group_id קיימת בטבלת numbers
            if numbers_exists:
                cur.execute("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'numbers' AND column_name = 'group_id')")
                group_id_exists = cur.fetchone()[0]
                
                if not group_id_exists:
                    logger.warning("The 'group_id' column doesn't exist in the 'numbers' table!")
                    
                    # מחיקת הטבלאות וביצוע אתחול מחדש
                    logger.info("Dropping existing tables...")
                    cur.execute("DROP TABLE IF EXISTS temp_images")
                    cur.execute("DROP TABLE IF EXISTS numbers")
                    cur.execute("DROP TABLE IF EXISTS groups")
                    
                    # איפוס הדגלים על מנת ליצור מחדש
                    groups_exists = False
                    numbers_exists = False
            
            # טבלת קבוצות
            if not groups_exists:
                logger.info("Creating 'groups' table...")
                cur.execute("""
                    CREATE TABLE groups (
                        group_id BIGINT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            # טבלת מספרים לקבוצה
            if not numbers_exists:
                logger.info("Creating 'numbers' table...")
                cur.execute("""
                    CREATE TABLE numbers (
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
            
            # בדיקה אם טבלת תמונות זמניות קיימת
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'temp_images')")
            temp_images_exists = cur.fetchone()[0]
            
            # טבלת תמונות זמניות
            if not temp_images_exists:
                logger.info("Creating 'temp_images' table...")
                cur.execute("""
                    CREATE TABLE temp_images (
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
            logger.info("Database schema setup complete")
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            if conn:
                conn.rollback()
            raise
            
        finally:
            # סגירת החיבור
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def init_group(self, group_id):
        """אתחול מאגר מספרים חדש לקבוצה"""
        conn = None
        cur = None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # בדיקה אם הקבוצה כבר קיימת
            cur.execute("SELECT group_id FROM groups WHERE group_id = %s", (group_id,))
            if cur.fetchone() is None:
                logger.info(f"Initializing new group with ID: {group_id}")
                # יצירת רשומת קבוצה חדשה
                cur.execute("INSERT INTO groups (group_id) VALUES (%s)", (group_id,))
                
                # יצירת מאגר מספרים (0-999)
                for number in range(1000):
                    cur.execute(
                        "INSERT INTO numbers (group_id, number, is_found, is_current) VALUES (%s, %s, %s, %s)",
                        (group_id, number, False, False)
                    )
                logger.info(f"Created 1000 numbers for group {group_id}")
            else:
                logger.info(f"Group {group_id} already exists")
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error initializing group {group_id}: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def select_next_number(self, group_id):
        """בחירת המספר הבא לחיפוש"""
        conn = None
        cur = None
        
        try:
            # וידוא שהקבוצה מאותחלת
            if not self.init_group(group_id):
                logger.error(f"Failed to initialize group {group_id}")
                return None
            
            conn = self._get_connection()
            cur = conn.cursor()
            
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
                logger.info(f"No available numbers for group {group_id}")
                return None
            
            # בחירת מספר אקראי מהזמינים
            current_number = random.choice(available_numbers)
            logger.info(f"Selected number {current_number} for group {group_id}")
            
            # עדכון המספר הנוכחי
            cur.execute(
                "UPDATE numbers SET is_current = TRUE WHERE group_id = %s AND number = %s",
                (group_id, current_number)
            )
            
            conn.commit()
            return current_number
            
        except Exception as e:
            logger.error(f"Error selecting next number for group {group_id}: {e}")
            if conn:
                conn.rollback()
            return None
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def get_current_number(self, group_id):
        """קבלת המספר הנוכחי לחיפוש"""
        conn = None
        cur = None
        
        try:
            # וידוא שהקבוצה מאותחלת
            if not self.init_group(group_id):
                logger.error(f"Failed to initialize group {group_id}")
                return None
            
            conn = self._get_connection()
            cur = conn.cursor()
            
            # קבלת המספר הנוכחי
            cur.execute(
                "SELECT number FROM numbers WHERE group_id = %s AND is_current = TRUE",
                (group_id,)
            )
            result = cur.fetchone()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error getting current number for group {group_id}: {e}")
            return None
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def mark_number_as_found(self, group_id, number, user_id=None):
        """סימון מספר כנמצא"""
        conn = None
        cur = None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # עדכון המספר כנמצא
            cur.execute(
                """
                UPDATE numbers 
                SET is_found = TRUE, is_current = FALSE, found_by = %s, found_at = CURRENT_TIMESTAMP
                WHERE group_id = %s AND number = %s
                RETURNING id
                """,
                (user_id, group_id, number)
            )
            
            # וידוא שהשורה עודכנה
            if cur.fetchone() is None:
                logger.warning(f"No number {number} found for group {group_id}")
                conn.rollback()
                return None
            
            logger.info(f"Marked number {number} as found by user {user_id} in group {group_id}")
            conn.commit()
            
            # בחירת מספר חדש
            return self.select_next_number(group_id)
            
        except Exception as e:
            logger.error(f"Error marking number {number} as found for group {group_id}: {e}")
            if conn:
                conn.rollback()
            return None
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def revert_found_number(self, group_id, number):
        """החזרת מספר למאגר (פסילת מציאה)"""
        conn = None
        cur = None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
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
                RETURNING id
                """,
                (group_id, number)
            )
            
            # וידוא שהשורה עודכנה
            if cur.fetchone() is None:
                logger.warning(f"No number {number} found for group {group_id}")
                conn.rollback()
                return None
            
            logger.info(f"Reverted number {number} to pool for group {group_id}")
            conn.commit()
            return number
            
        except Exception as e:
            logger.error(f"Error reverting number {number} for group {group_id}: {e}")
            if conn:
                conn.rollback()
            return None
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def get_stats(self, group_id):
        """קבלת סטטיסטיקות משחק"""
        conn = None
        cur = None
        
        try:
            # וידוא שהקבוצה מאותחלת
            if not self.init_group(group_id):
                logger.error(f"Failed to initialize group {group_id}")
                return {'total': 1000, 'found': 0, 'remaining': 1000, 'percentage': 0}
            
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            
            # קבלת סטטיסטיקות
            cur.execute("""
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN is_found THEN 1 ELSE 0 END) AS found
                FROM numbers
                WHERE group_id = %s
            """, (group_id,))
            
            result = dict(cur.fetchone())
            result['found'] = int(result['found'])  # המרה ל-int (לפעמים מוחזר כ-Decimal)
            result['remaining'] = result['total'] - result['found']
            result['percentage'] = round((result['found'] / result['total']) * 100, 2) if result['total'] > 0 else 0
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting stats for group {group_id}: {e}")
            return {'total': 1000, 'found': 0, 'remaining': 1000, 'percentage': 0}
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def save_temp_image(self, message_id, image_path, user_id, username, group_id, current_number, plate_numbers):
        """שמירת נתוני תמונה זמנית"""
        conn = None
        cur = None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
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
            logger.info(f"Saved temp image for message {message_id} in group {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving temp image for message {message_id}: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def get_temp_image(self, message_id):
        """קבלת נתוני תמונה זמנית"""
        conn = None
        cur = None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            
            cur.execute("SELECT * FROM temp_images WHERE message_id = %s", (message_id,))
            result = cur.fetchone()
            
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"Error getting temp image for message {message_id}: {e}")
            return None
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def delete_temp_image(self, message_id):
        """מחיקת נתוני תמונה זמנית"""
        conn = None
        cur = None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("DELETE FROM temp_images WHERE message_id = %s", (message_id,))
            conn.commit()
            logger.info(f"Deleted temp image for message {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting temp image for message {message_id}: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def clean_old_temp_images(self, hours=24):
        """ניקוי תמונות זמניות ישנות"""
        conn = None
        cur = None
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute(
                "DELETE FROM temp_images WHERE created_at < NOW() - INTERVAL '%s hours'",
                (hours,)
            )
            
            deleted_count = cur.rowcount
            conn.commit()
            logger.info(f"Cleaned {deleted_count} old temp images (older than {hours} hours)")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning old temp images: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()