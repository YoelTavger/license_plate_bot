import psycopg2
import json
import os
from datetime import datetime
from psycopg2.extras import RealDictCursor

def backup_database():
    """Back up data from the database before making schema changes"""
    # Database connection parameters
    db_params = {
        'host': 'dpg-d0cmiqemcj7s73antifg-a.oregon-postgres.render.com',
        'port': 5432,
        'database': 'license_plate_db',
        'user': 'license_plate_admin',
        'password': 'qGVtVXMcsxAdVodYzr9nF6ekJibYXDC2'
    }
    
    # Connect to the database
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Create backup directory if it doesn't exist
    backup_dir = "database_backup"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate timestamp for backup files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        # Get list of tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [record['table_name'] for record in cur.fetchall()]
        
        # Backup each table
        for table in tables:
            try:
                print(f"Backing up table: {table}")
                
                # Get table data
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                
                # Save to JSON file
                backup_file = os.path.join(backup_dir, f"{table}_{timestamp}.json")
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(rows, f, ensure_ascii=False, default=str, indent=2)
                
                print(f"Backed up {len(rows)} rows from {table} to {backup_file}")
                
            except Exception as e:
                print(f"Error backing up table {table}: {e}")
        
        print(f"Database backup completed successfully! Files saved in '{backup_dir}' directory.")
        
    except Exception as e:
        print(f"Error during backup: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    backup_database()