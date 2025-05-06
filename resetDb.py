import psycopg2

def drop_all_tables():
    db_params = {
        'host': 'dpg-d0cmiqemcj7s73antifg-a.oregon-postgres.render.com',
        'port': 5432,
        'database': 'license_plate_db',
        'user': 'license_plate_admin',
        'password': 'qGVtVXMcsxAdVodYzr9nF6ekJibYXDC2'
    }

    try:
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        cur = conn.cursor()

        # שליפת כל שמות הטבלאות
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()

        for table in tables:
            table_name = table[0]
            print(f"Deleting table: {table_name}")
            cur.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;')

        print("✅ All tables dropped successfully.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    drop_all_tables()
