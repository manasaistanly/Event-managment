import pymysql

# Migration script to add event_feedbacks table

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

        # Check if event_feedbacks table exists
        cursor.execute("""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME='event_feedbacks' AND TABLE_SCHEMA='college_event_radar'
        """)

        if cursor.fetchone():
            print("✓ Table 'event_feedbacks' already exists")
        else:
            print("Creating 'event_feedbacks' table...")

            # Create the event_feedbacks table
            cursor.execute("""
                CREATE TABLE event_feedbacks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    event_id INT NOT NULL,
                    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            db.commit()
            print("✓ Table 'event_feedbacks' created successfully!")

        cursor.close()
        db.close()

    except pymysql.Error as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
