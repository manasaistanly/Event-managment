import pymysql

# Migration script to add event_registrations table

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

        # Check if event_registrations table exists
        cursor.execute("""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME='event_registrations' AND TABLE_SCHEMA='college_event_radar'
        """)

        if cursor.fetchone():
            print("✓ Table 'event_registrations' already exists")
        else:
            print("Creating 'event_registrations' table...")

            # Create the event_registrations table
            cursor.execute("""
                CREATE TABLE event_registrations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    event_id INT NOT NULL,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_registration (user_id, event_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            db.commit()
            print("✓ Table 'event_registrations' created successfully!")

        cursor.close()
        db.close()

    except pymysql.Error as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()