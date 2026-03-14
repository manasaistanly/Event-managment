import pymysql

# Migration script to update users table with profile fields

def migrate():
    try:
        # Connect to MySQL
        db = pymysql.connect(
            host="localhost",
            user="root",
            password="root",
            database="college_event_radar"
        )

        cursor = db.cursor()

        # Check for missing columns in users table
        columns_to_add = [
            ("phone", "VARCHAR(15)"),
            ("bio", "TEXT"),
            ("profile_pic", "VARCHAR(255)")
        ]

        for column_name_to_check, column_type in columns_to_add:
            cursor.execute(f"""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME='users' AND COLUMN_NAME='{column_name_to_check}' AND TABLE_SCHEMA='college_event_radar'
            """)
            
            if cursor.fetchone():
                print(f"✓ Column '{column_name_to_check}' already exists in 'users'")
            else:
                print(f"Adding column '{column_name_to_check}' to 'users' table...")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name_to_check} {column_type}")
                db.commit()
                print(f"✓ Column '{column_name_to_check}' added successfully!")

        cursor.close()
        db.close()

    except pymysql.Error as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
