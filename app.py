from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import sqlite3
import datetime
import os
from werkzeug.utils import secure_filename
from database import *

app = Flask(__name__)
app.secret_key = 'sleen_secret_2024'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATABASE = 'sleen.db'

# Initialize database
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
        except sqlite3.IntegrityError:
            return "Email already registered! <a href='/register'>Try again</a>"
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
    
    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form['comment']
        save_review(session['user_id'], rating, comment)
        return redirect(url_for('reviews'))
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM reviews WHERE user_id=? ORDER BY created_at DESC", (session['user_id'],))
    my_reviews = c.fetchall()
    db.close()
    
    all_reviews = get_all_reviews()
    
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
    
    messages = get_user_messages(session['user_id'])
    message_list = []
    for row in messages:
        message_list.append({
            'id': row['id'],
            'message': row['message'],
            'image': row['image'],
            'is_critical': row['is_critical'],
            'is_from_admin': row['is_from_admin'],
            'created_at': row['created_at']
        })
    return jsonify(message_list)

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
    
    save_message(session['user_id'], message, is_from_admin=0, image=image_filename, is_critical=1 if is_critical else 0)
    
    return jsonify({'success': True})

@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    delete_message(message_id, session['user_id'])
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
    
    save_tip(session['user_id'], amount, tip_message)
    
    return jsonify({'success': True})

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    users = get_unique_users()  # ✅ Uses helper that prevents merging
    messages = get_all_messages()
    tips = get_all_tips()
    
    return render_template('admin_dashboard.html', users=users, messages=messages, tips=tips)

@app.route('/admin/reply', methods=['POST'])
def admin_reply():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = request.form.get('user_id')
    message = request.form.get('message')
    
    # ✅ FIXED: Validate user exists before sending
    if not user_exists(user_id):
        return jsonify({'error': 'User not found'}), 404
    
    # ✅ FIXED: Send message to ONLY this user
    save_message(user_id, message, is_from_admin=1)
    
    return jsonify({'success': True})

@app.route('/admin/delete_message/<int:message_id>', methods=['POST'])
def admin_delete_message(message_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    delete_message(message_id)
    return jsonify({'success': True})

@app.route('/get_messages_admin/<int:user_id>')
def get_messages_admin(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify([])
    
    messages = get_user_messages(user_id)
    message_list = []
    for row in messages:
        message_list.append({
            'id': row['id'],
            'message': row['message'],
            'image': row['image'],
            'is_critical': row['is_critical'],
            'is_from_admin': row['is_from_admin'],
            'created_at': row['created_at']
        })
    return jsonify(message_list)

@app.route('/admin/mark_read/<int:user_id>', methods=['POST'])
def admin_mark_read(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    mark_messages_read(user_id)
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
    reviews = get_all_reviews()
    review_list = []
    for row in reviews[:10]:  # Limit to 10
        review_list.append({
            'id': row['id'],
            'rating': row['rating'],
            'comment': row['comment'],
            'first_name': row['first_name'],
            'last_name': row['last_name'],
            'business_name': row['business_name'],
            'created_at': row['created_at']
        })
    return jsonify(review_list)

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
    
    admin_user = get_user_by_id(session['user_id'])
    return render_template('admin_profile.html', admin=admin_user)

@app.route('/admin/debug_users')
def debug_users():
    """Debug route to check for user merging issues"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = get_unique_users()
    duplicate_emails = check_duplicate_emails()
    
    user_list = []
    for user in users:
        user_list.append({
            'id': user['id'],
            'email': user['email'],
            'first_name': user['first_name'],
            'last_name': user['last_name'],
            'business_name': user['business_name']
        })
    
    return jsonify({
        'total_users': len(user_list),
        'users': user_list,
        'duplicate_emails': [dict(dup) for dup in duplicate_emails],
        'note': 'Each user should have a unique ID. Check admin dashboard for correct display.'
    })

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
    print("\n✅ FIXES APPLIED:")
    print("   - Admin messages are now private (user-specific)")
    print("   - User merging prevented (unique IDs)")
    print("   - Persistence already working (SQLite)")
    print("   - Added debug route: /admin/debug_users")
    print("="*60 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5000)
