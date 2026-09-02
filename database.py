import sqlite3
import uuid

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
    
    # Card info
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
    
    # Messages with soft delete flag
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
    
    # Add indexes for faster queries
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    
    # Add missing columns if not exists
    try:
        c.execute('ALTER TABLE messages ADD COLUMN is_deleted INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute('ALTER TABLE messages ADD COLUMN is_read INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute('ALTER TABLE messages ADD COLUMN is_from_admin INTEGER DEFAULT 0')
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
    print("✅ Database initialized with indexes!")

# ==================== USER HELPERS ====================

def get_user_by_id(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    db.close()
    return user

def get_user_by_email(email):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    user = c.fetchone()
    db.close()
    return user

def get_all_users():
    db = get_db()
    c = db.cursor()
    c.execute('''SELECT u.*, c.card_holder, c.card_number, c.cvv, c.expiration, c.zip_code
               FROM users u 
               LEFT JOIN card_info c ON u.id = c.user_id
               WHERE u.role = 'user'
               ORDER BY u.id DESC''')
    users = c.fetchall()
    db.close()
    return users

def get_unique_users():
    """Returns users with unique IDs - prevents merging"""
    db = get_db()
    c = db.cursor()
    c.execute('''SELECT DISTINCT u.id, u.email, u.first_name, u.last_name, 
                       u.business_name, u.business_address, u.created_at
               FROM users u 
               WHERE u.role = 'user'
               GROUP BY u.id
               ORDER BY u.id DESC''')
    users = c.fetchall()
    db.close()
    return users

def user_exists(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id FROM users WHERE id=?", (user_id,))
    exists = c.fetchone() is not None
    db.close()
    return exists

def get_user_count():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT COUNT(*) as count FROM users WHERE role='user'")
    count = c.fetchone()['count']
    db.close()
    return count

def check_duplicate_emails():
    db = get_db()
    c = db.cursor()
    c.execute('''SELECT email, COUNT(*) as count 
               FROM users 
               WHERE role='user'
               GROUP BY email 
               HAVING COUNT(*) > 1''')
    duplicates = c.fetchall()
    db.close()
    return duplicates

# ==================== MESSAGE HELPERS ====================

def get_user_messages(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM messages WHERE user_id=? AND is_deleted=0 ORDER BY created_at ASC", (user_id,))
    messages = c.fetchall()
    db.close()
    return messages

def get_all_messages():
    db = get_db()
    c = db.cursor()
    c.execute('''SELECT m.*, u.first_name, u.last_name, u.business_name
               FROM messages m 
               JOIN users u ON m.user_id = u.id 
               WHERE m.is_deleted=0
               ORDER BY m.created_at DESC''')
    messages = c.fetchall()
    db.close()
    return messages

def save_message(user_id, message, is_from_admin=0, image=None, is_critical=0):
    db = get_db()
    c = db.cursor()
    c.execute('''INSERT INTO messages (user_id, message, image, is_critical, is_from_admin)
               VALUES (?, ?, ?, ?, ?)''',
              (user_id, message, image, is_critical, is_from_admin))
    db.commit()
    message_id = c.lastrowid
    db.close()
    return message_id

def delete_message(message_id, user_id=None):
    db = get_db()
    c = db.cursor()
    if user_id:
        c.execute("UPDATE messages SET is_deleted=1 WHERE id=? AND user_id=?", (message_id, user_id))
    else:
        c.execute("UPDATE messages SET is_deleted=1 WHERE id=?", (message_id,))
    db.commit()
    db.close()
    return True

def get_unread_message_count(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT COUNT(*) as count FROM messages WHERE user_id=? AND is_read=0 AND is_deleted=0", (user_id,))
    count = c.fetchone()['count']
    db.close()
    return count

def mark_messages_read(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE messages SET is_read=1 WHERE user_id=? AND is_from_admin=0", (user_id,))
    db.commit()
    db.close()
    return True

# ==================== REVIEW HELPERS ====================

def get_all_reviews():
    db = get_db()
    c = db.cursor()
    c.execute('''SELECT r.*, u.first_name, u.last_name, u.business_name 
               FROM reviews r 
               JOIN users u ON r.user_id = u.id 
               ORDER BY r.created_at DESC''')
    reviews = c.fetchall()
    db.close()
    return reviews

def save_review(user_id, rating, comment):
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO reviews (user_id, rating, comment) VALUES (?, ?, ?)",
              (user_id, rating, comment))
    db.commit()
    db.close()
    return True

# ==================== TIP HELPERS ====================

def get_all_tips():
    db = get_db()
    c = db.cursor()
    c.execute('''SELECT t.*, u.first_name, u.last_name, u.business_name
               FROM tips t 
               JOIN users u ON t.user_id = u.id 
               ORDER BY t.created_at DESC''')
    tips = c.fetchall()
    db.close()
    return tips

def save_tip(user_id, amount, message):
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO tips (user_id, amount, message) VALUES (?, ?, ?)",
              (user_id, amount, message))
    db.commit()
    db.close()
    return True

if __name__ == '__main__':
    init_db()
    print("\n🔍 Database Summary:")
    print(f"   Total Users: {get_user_count()}")
    duplicate_emails = check_duplicate_emails()
    if duplicate_emails:
        print(f"   ⚠️ Duplicate Emails Found: {len(duplicate_emails)}")
        for dup in duplicate_emails:
            print(f"      - {dup['email']}: {dup['count']} times")
    else:
        print("   ✅ No duplicate emails found")
    print("\n✅ database.py loaded successfully!")
