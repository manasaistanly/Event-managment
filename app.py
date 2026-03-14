from flask import Flask, render_template, request, redirect, flash, session
import os
import psycopg2
from psycopg2 import Error as DBError
from datetime import datetime
import hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_please_change_it'

# Postgres (Neon) Connection Function
def get_db_connection():
    db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("NEON_DATABASE_URL")
    )
    if not db_url:
        print("Database URL not configured. Set DATABASE_URL/POSTGRES_URL.")
        return None

    try:
        db = psycopg2.connect(db_url, sslmode="require")
        return db
    except DBError as e:
        print(f"Error connecting to Postgres: {e}")
        return None

# Hash password function
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Decorator to check if user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first!', 'error')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# Decorator to check if user is admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first!', 'error')
            return redirect('/login')
        
        if session.get('role') != 'admin':
            flash('You do not have permission to access this page!', 'error')
            return redirect('/')
        
        return f(*args, **kwargs)
    return decorated_function

# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Please enter email and password!', 'error')
            return render_template('login.html')
        
        try:
            db = get_db_connection()
            if db is None:
                flash('Database connection failed!', 'error')
                return render_template('login.html')
            
            cursor = db.cursor()
            cursor.execute(
                "SELECT id, name, email, role, profile_pic FROM users WHERE email = %s AND password = %s",
                (email, hash_password(password))
            )
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user[0]
                session['name'] = user[1]
                session['email'] = user[2]
                session['role'] = user[3]
                session['profile_pic'] = user[4]
                
                flash(f'Welcome back, {user[1]}!', 'success')
                cursor.close()
                db.close()
                return redirect('/')
            else:
                cursor.close()
                db.close()
                flash('Invalid email or password!', 'error')
                return render_template('login.html')
        
        except DBError as e:
            flash(f'Error logging in: {e}', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

# Register Page 
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', 'student').strip()
        
        if not all([name, email, password, confirm_password]):
            flash('Please fill in all fields!', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters!', 'error')
            return render_template('register.html')
        
        if role not in ['admin', 'student']:
            role = 'student'
        
        try:
            db = get_db_connection()
            if db is None:
                flash('Database connection failed!', 'error')
                return render_template('register.html')
            
            cursor = db.cursor()
            
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email already registered!', 'error')
                cursor.close()
                db.close()
                return render_template('register.html')
            
            # Insert new user
            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, hash_password(password), role)
            )
            db.commit()
            cursor.close()
            db.close()
            
            flash('Registration successful! Please login.', 'success')
            return redirect('/login')
        
        except DBError as e:
            flash(f'Error registering: {e}', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out!', 'success')
    return redirect('/')

# Dashboard - Statistics and Overview (Admin only)
@app.route('/dashboard')
@admin_required
def dashboard():
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return render_template("dashboard.html", stats={}, active_page='dashboard')
        
        cursor = db.cursor()
        
        # Get total events
        cursor.execute("SELECT COUNT(*) FROM events")
        total_events = cursor.fetchone()[0]
        
        # Get total registrations
        cursor.execute("SELECT COUNT(*) FROM event_registrations")
        total_registrations = cursor.fetchone()[0]
        
        # Get total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Get registrations last 7 days
        cursor.execute("SELECT COUNT(*) FROM event_registrations WHERE registered_at >= NOW() - INTERVAL '7 days'")
        recent_registrations = cursor.fetchone()[0]
        
        # Get events by category
        cursor.execute("SELECT category, COUNT(*) as count FROM events GROUP BY category")
        categories = cursor.fetchall()
        
        # Get recent events
        cursor.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT 5")
        recent_events = cursor.fetchall()

        # Get top users by registration count
        cursor.execute("""
            SELECT u.name, COUNT(r.id) as reg_count 
            FROM users u 
            JOIN event_registrations r ON u.id = r.user_id 
            GROUP BY u.id 
            ORDER BY reg_count DESC LIMIT 5
        """)
        top_users = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        stats = {
            'total_events': total_events,
            'total_registrations': total_registrations,
            'total_users': total_users,
            'recent_registrations': recent_registrations,
            'categories': categories,
            'recent': recent_events,
            'top_users': top_users
        }
        
        return render_template("dashboard.html", stats=stats, active_page='dashboard')
    except DBError as e:
        flash(f'Error loading dashboard: {e}', 'error')
        return render_template("dashboard.html", stats={}, active_page='dashboard')

# User Management (Admin only)
@app.route('/admin/users')
@admin_required
def admin_users():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template("admin_users.html", users=users, active_page='admin_users')
    except DBError as e:
        flash(f'Error loading users: {e}', 'error')
        return redirect('/dashboard')

# Student Dashboard
@app.route('/student_dashboard')
@login_required
def student_dashboard():
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return render_template("student_dashboard.html", stats={}, active_page='student_dashboard')
        
        cursor = db.cursor()
        user_id = session['user_id']
        
        # My total registrations
        cursor.execute("SELECT COUNT(*) FROM event_registrations WHERE user_id = %s", (user_id,))
        my_registrations = cursor.fetchone()[0]
        
        # Upcoming events for me
        cursor.execute("""
            SELECT COUNT(*) FROM events e
            JOIN event_registrations r ON e.id = r.event_id
            WHERE r.user_id = %s AND e.event_date >= CURRENT_DATE
        """, (user_id,))
        my_upcoming = cursor.fetchone()[0]
        
        # Latest 3 registered events
        cursor.execute("""
            SELECT e.* FROM events e
            JOIN event_registrations r ON e.id = r.event_id
            WHERE r.user_id = %s
            ORDER BY r.registered_at DESC LIMIT 3
        """, (user_id,))
        recent_my_events = cursor.fetchall()

        # Recommended events (some logic, e.g. same category as registered)
        cursor.execute("""
            SELECT DISTINCT e.* FROM events e 
            WHERE e.id NOT IN (SELECT event_id FROM event_registrations WHERE user_id = %s)
            AND e.event_date >= CURRENT_DATE
            ORDER BY e.event_date ASC LIMIT 4
        """, (user_id,))
        recommended_events = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        stats = {
            'total': my_registrations,
            'upcoming': my_upcoming,
            'recent': recent_my_events,
            'recommended': recommended_events
        }
        
        return render_template("student_dashboard.html", stats=stats, active_page='student_dashboard')
    except DBError as e:
        flash(f'Error loading student dashboard: {e}', 'error')
        return render_template("student_dashboard.html", stats={}, active_page='student_dashboard')

# User Profile
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        bio = request.form.get('bio', '').strip()
        profile_pic = request.form.get('profile_pic', '').strip()
        
        if not name or not email:
            flash('Name and Email are required!', 'error')
            return redirect('/profile')
            
        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("""
                UPDATE users SET name=%s, email=%s, phone=%s, bio=%s, profile_pic=%s
                WHERE id=%s
            """, (name, email, phone, bio, profile_pic, user_id))
            db.commit()
            
            # Update session
            session['name'] = name
            session['email'] = email
            session['profile_pic'] = profile_pic
            
            cursor.close()
            db.close()
            flash('Profile updated successfully!', 'success')
            return redirect('/profile')
        except DBError as e:
            flash(f'Error updating profile: {e}', 'error')
            return redirect('/profile')

    # GET request
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT name, email, role, phone, bio, profile_pic, created_at FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        db.close()
        return render_template("profile.html", user=user, active_page='profile')
    except DBError as e:
        flash(f'Error loading profile: {e}', 'error')
        return redirect('/')

# Event Feedback
@app.route('/feedback/<int:event_id>', methods=['POST'])
@login_required
def submit_feedback(event_id):
    rating = request.form.get('rating')
    comment = request.form.get('comment', '').strip()
    user_id = session['user_id']
    
    if not rating:
        flash('Rating is required!', 'error')
        return redirect(f'/event/{event_id}')
        
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Check if already submitted
        cursor.execute("SELECT id FROM event_feedbacks WHERE user_id = %s AND event_id = %s", (user_id, event_id))
        if cursor.fetchone():
            cursor.execute("UPDATE event_feedbacks SET rating=%s, comment=%s WHERE user_id=%s AND event_id=%s", 
                         (rating, comment, user_id, event_id))
            flash('Feedback updated!', 'success')
        else:
            cursor.execute("INSERT INTO event_feedbacks (user_id, event_id, rating, comment) VALUES (%s, %s, %s, %s)",
                         (user_id, event_id, rating, comment))
            flash('Thank you for your feedback!', 'success')
            
        db.commit()
        cursor.close()
        db.close()
    except DBError as e:
        flash(f'Error submitting feedback: {e}', 'error')
        
    return redirect(f'/event/{event_id}')

# Home Page - List All Events
@app.route('/')
def index():
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return render_template("index.html", events=[])
        
        cursor = db.cursor()
        
        # Get search and filter parameters
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        sort = request.args.get('sort', 'date_asc')
        
        # Build query
        query = """
            SELECT e.*, 
                   CASE WHEN r.user_id IS NOT NULL THEN 1 ELSE 0 END as is_registered,
                   COALESCE(reg_counts.registration_count, 0) as registration_count
            FROM events e
            LEFT JOIN (SELECT event_id, COUNT(*) as registration_count FROM event_registrations GROUP BY event_id) reg_counts ON e.id = reg_counts.event_id
        """
        params = []
        
        if 'user_id' in session:
            query += " LEFT JOIN event_registrations r ON e.id = r.event_id AND r.user_id = %s"
            params.append(session['user_id'])
        else:
            query += " LEFT JOIN (SELECT 1 as user_id) r ON 1=0"  # Dummy join for consistency
        
        query += " WHERE 1=1"
        
        if search:
            query += " AND (e.event_name LIKE %s OR e.event_description LIKE %s OR e.event_location LIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if category:
            query += " AND e.category = %s"
            params.append(category)
        
        # Add sorting
        if sort == 'date_desc':
            query += " ORDER BY e.event_date DESC"
        elif sort == 'name':
            query += " ORDER BY e.event_name ASC"
        else:  # date_asc
            query += " ORDER BY e.event_date ASC"
        
        cursor.execute(query, params)
        events = cursor.fetchall()
        
        # Get all categories for filter
        cursor.execute("SELECT DISTINCT category FROM events")
        categories = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        db.close()
        
        if not events and search:
            flash(f'No events found for "{search}"', 'info')
        elif not events:
            flash('No events found. Create your first event!', 'info')
        
        return render_template("index.html", events=events, categories=categories, search=search, category=category, sort=sort)
    except DBError as e:
        flash(f'Error retrieving events: {e}', 'error')
        return render_template("index.html", events=[])

# Add Event Page (Admin only)
@app.route('/add')
@admin_required
def add():
    try:
        db = get_db_connection()
        if db is None:
            return render_template("add_event.html", categories=[])
        
        cursor = db.cursor()
        cursor.execute("SELECT DISTINCT category FROM events")
        categories = [row[0] for row in cursor.fetchall()]
        cursor.close()
        db.close()
        
        return render_template("add_event.html", categories=categories)
    except:
        return render_template("add_event.html", categories=[])

# Insert Event (Admin only)
@app.route('/insert', methods=['POST'])
@admin_required
def insert():
    try:
        name = request.form.get('name', '').strip()
        date = request.form.get('date', '').strip()
        time = request.form.get('time', '09:00').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'General').strip()
        organizer = request.form.get('organizer', '').strip()
        max_attendees = request.form.get('max_attendees', '0').strip()

        if not all([name, date, location]):
            flash('Please fill in all required fields!', 'error')
            return redirect('/add')

        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return redirect('/add')

        cursor = db.cursor()
        query = "INSERT INTO events (event_name, event_date, event_time, event_location, event_description, category, organizer, max_attendees) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        values = (name, date, time, location, description, category, organizer, max_attendees or 0)

        cursor.execute(query, values)
        db.commit()
        cursor.close()
        db.close()

        flash('Event added successfully!', 'success')
        return redirect('/')
    except DBError as e:
        flash(f'Error adding event: {e}', 'error')
        return redirect('/add')

# Edit Event Page (Admin only)
@app.route('/edit/<int:event_id>')
@admin_required
def edit(event_id):
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return redirect('/')
        
        cursor = db.cursor()
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        
        cursor.execute("SELECT DISTINCT category FROM events")
        categories = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        db.close()
        
        if not event:
            flash('Event not found!', 'error')
            return redirect('/')
        
        return render_template("edit_event.html", event=event, categories=categories)
    except DBError as e:
        flash(f'Error loading event: {e}', 'error')
        return redirect('/')

# Update Event (Admin only)
@app.route('/update/<int:event_id>', methods=['POST'])
@admin_required
def update(event_id):
    try:
        name = request.form.get('name', '').strip()
        date = request.form.get('date', '').strip()
        time = request.form.get('time', '09:00').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'General').strip()
        organizer = request.form.get('organizer', '').strip()
        max_attendees = request.form.get('max_attendees', '0').strip()

        if not all([name, date, location]):
            flash('Please fill in all required fields!', 'error')
            return redirect(f'/edit/{event_id}')

        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return redirect(f'/edit/{event_id}')

        cursor = db.cursor()
        query = "UPDATE events SET event_name=%s, event_date=%s, event_time=%s, event_location=%s, event_description=%s, category=%s, organizer=%s, max_attendees=%s WHERE id=%s"
        values = (name, date, time, location, description, category, organizer, max_attendees or 0, event_id)

        cursor.execute(query, values)
        db.commit()
        cursor.close()
        db.close()

        flash('Event updated successfully!', 'success')
        return redirect('/')
    except DBError as e:
        flash(f'Error updating event: {e}', 'error')
        return redirect(f'/edit/{event_id}')

# Delete Event (Admin only)
@app.route('/delete/<int:event_id>')
@admin_required
def delete(event_id):
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return redirect('/')

        cursor = db.cursor()
        cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
        db.commit()
        cursor.close()
        db.close()

        flash('Event deleted successfully!', 'success')
    except DBError as e:
        flash(f'Error deleting event: {e}', 'error')
    
    return redirect('/')

# Register for Event (Logged in users)
@app.route('/register_event/<int:event_id>')
@login_required
def register_event(event_id):
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return redirect('/')

        cursor = db.cursor()
        
        # Check if event exists and get max_attendees
        cursor.execute("SELECT id, event_name, max_attendees FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        if not event:
            flash('Event not found!', 'error')
            cursor.close()
            db.close()
            return redirect('/')
        
        # Check if already registered
        cursor.execute("SELECT id FROM event_registrations WHERE user_id = %s AND event_id = %s", (session['user_id'], event_id))
        if cursor.fetchone():
            flash('You are already registered for this event!', 'info')
            cursor.close()
            db.close()
            return redirect('/')
        
        # Check capacity
        if event[2] and event[2] > 0:  # max_attendees exists and > 0
            cursor.execute("SELECT COUNT(*) FROM event_registrations WHERE event_id = %s", (event_id,))
            current_registrations = cursor.fetchone()[0]
            if current_registrations >= event[2]:
                flash('Sorry, this event is at full capacity!', 'error')
                cursor.close()
                db.close()
                return redirect('/')
        
        # Register
        cursor.execute("INSERT INTO event_registrations (user_id, event_id) VALUES (%s, %s)", (session['user_id'], event_id))
        db.commit()
        cursor.close()
        db.close()
        
        flash(f'Successfully registered for "{event[1]}"!', 'success')
    except DBError as e:
        flash(f'Error registering for event: {e}', 'error')
    
    return redirect('/')

# Unregister from Event (Logged in users)
@app.route('/unregister_event/<int:event_id>')
@login_required
def unregister_event(event_id):
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return redirect('/')

        cursor = db.cursor()
        
        # Unregister
        cursor.execute("DELETE FROM event_registrations WHERE user_id = %s AND event_id = %s", (session['user_id'], event_id))
        db.commit()
        cursor.close()
        db.close()
        
        flash('Successfully unregistered from the event!', 'success')
    except DBError as e:
        flash(f'Error unregistering from event: {e}', 'error')
    
    return redirect('/')

# Event Details Page
@app.route('/event/<int:event_id>')
def event_details(event_id):
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return redirect('/')

        cursor = db.cursor()
        
        # Get event details with registration count
        cursor.execute("""
            SELECT e.*, 
                   CASE WHEN r.user_id IS NOT NULL THEN 1 ELSE 0 END as is_registered,
                   COALESCE(reg_counts.registration_count, 0) as registration_count
            FROM events e
            LEFT JOIN (SELECT event_id, COUNT(*) as registration_count FROM event_registrations GROUP BY event_id) reg_counts ON e.id = reg_counts.event_id
            LEFT JOIN event_registrations r ON e.id = r.event_id AND r.user_id = %s
            WHERE e.id = %s
        """, (session.get('user_id'), event_id))
        
        event = cursor.fetchone()
        
        if not event:
            flash('Event not found!', 'error')
            cursor.close()
            db.close()
            return redirect('/')
        
        # Get feedbacks
        cursor.execute("""
            SELECT f.rating, f.comment, u.name, f.created_at 
            FROM event_feedbacks f 
            JOIN users u ON f.user_id = u.id 
            WHERE f.event_id = %s 
            ORDER BY f.created_at DESC
        """, (event_id,))
        feedbacks = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return render_template("event_details.html", event=event, feedbacks=feedbacks)
    except DBError as e:
        flash(f'Error loading event details: {e}', 'error')
        return redirect('/')

# User Dashboard - My Events
@app.route('/my_events')
@login_required
def my_events():
    try:
        db = get_db_connection()
        if db is None:
            flash('Database connection failed!', 'error')
            return render_template("my_events.html", events=[])
        
        cursor = db.cursor()
        
        # Get registered events
        cursor.execute("""
            SELECT e.* FROM events e
            JOIN event_registrations r ON e.id = r.event_id
            WHERE r.user_id = %s
            ORDER BY e.event_date ASC
        """, (session['user_id'],))
        events = cursor.fetchall()
        
        cursor.close()
        db.close()
        
        return render_template("my_events.html", events=events)
    except DBError as e:
        flash(f'Error loading your events: {e}', 'error')
        return render_template("my_events.html", events=[])

if __name__ == '__main__':
    app.run(debug=True)
