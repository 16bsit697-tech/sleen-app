import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
import datetime

# Get database URL from environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    # Fallback for local testing
    DATABASE_URL = 'postgresql://localhost/sleen_db'

def get_db():
    """Get database connection"""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
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
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        card_holder TEXT,
        card_number TEXT,
        cvv TEXT,
        expiration TEXT,
        zip_code TEXT
    )''')
    
    # Messages
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        message TEXT,
        image TEXT,
        is_critical INTEGER DEFAULT 0,
        is_read INTEGER DEFAULT 0,
        is_from_admin INTEGER DEFAULT 0,
        is_deleted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Tips table
    c.execute('''CREATE TABLE IF NOT EXISTS tips (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        amount REAL,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Reviews table
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        rating INTEGER,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    
    # Insert admin user
    c.execute("SELECT * FROM users WHERE email='admin@sleen.com'")
    admin = c.fetchone()
    if not admin:
        c.execute('''INSERT INTO users (email, first_name, last_name, business_name, business_address, password, role)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                  ('admin@sleen.com', 'Admin', 'Sleen', 'Sleen Inc', '123 Main St', 'admin123', 'admin'))
    
    conn.commit()
    conn.close()
    print(f"✅ PostgreSQL database initialized at: {DATABASE_URL}")

# ==================== USER HELPERS ====================

def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_email(email):
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = c.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('''SELECT u.*, 
                       c.card_holder, c.card_number, c.cvv, c.expiration, c.zip_code
               FROM users u 
               LEFT JOIN card_info c ON u.id = c.user_id
               WHERE u.role = 'user'
               ORDER BY u.id DESC''')
    users = c.fetchall()
    conn.close()
    return users

def get_unique_users():
    """Returns users with unique IDs - prevents merging"""
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('''SELECT DISTINCT u.id, u.email, u.first_name, u.last_name, 
                       u.business_name, u.business_address, u.created_at
               FROM users u 
               WHERE u.role = 'user'
               GROUP BY u.id
               ORDER BY u.id DESC''')
    users = c.fetchall()
    conn.close()
    return users

def user_exists(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE id=%s", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def get_user_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM users WHERE role='user'")
    count = c.fetchone()[0]
    conn.close()
    return count

def check_duplicate_emails():
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('''SELECT email, COUNT(*) as count 
               FROM users 
               WHERE role='user'
               GROUP BY email 
               HAVING COUNT(*) > 1''')
    duplicates = c.fetchall()
    conn.close()
    return duplicates

# ==================== MESSAGE HELPERS ====================

def get_user_messages(user_id):
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM messages WHERE user_id=%s AND is_deleted=0 ORDER BY created_at ASC", (user_id,))
    messages = c.fetchall()
    conn.close()
    return messages

def get_all_messages():
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('''SELECT m.*, u.first_name, u.last_name, u.business_name
               FROM messages m 
               JOIN users u ON m.user_id = u.id 
               WHERE m.is_deleted=0
               ORDER BY m.created_at DESC''')
    messages = c.fetchall()
    conn.close()
    return messages

def save_message(user_id, message, is_from_admin=0, image=None, is_critical=0):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO messages (user_id, message, image, is_critical, is_from_admin)
               VALUES (%s, %s, %s, %s, %s) RETURNING id''',
              (user_id, message, image, is_critical, is_from_admin))
    message_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return message_id

def delete_message(message_id, user_id=None):
    conn = get_db()
    c = conn.cursor()
    if user_id:
        c.execute("UPDATE messages SET is_deleted=1 WHERE id=%s AND user_id=%s", (message_id, user_id))
    else:
        c.execute("UPDATE messages SET is_deleted=1 WHERE id=%s", (message_id,))
    conn.commit()
    conn.close()
    return True

def get_unread_message_count(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM messages WHERE user_id=%s AND is_read=0 AND is_deleted=0", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def mark_messages_read(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE messages SET is_read=1 WHERE user_id=%s AND is_from_admin=0", (user_id,))
    conn.commit()
    conn.close()
    return True

# ==================== REVIEW HELPERS ====================

def get_all_reviews():
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('''SELECT r.*, u.first_name, u.last_name, u.business_name 
               FROM reviews r 
               JOIN users u ON r.user_id = u.id 
               ORDER BY r.created_at DESC''')
    reviews = c.fetchall()
    conn.close()
    return reviews

def save_review(user_id, rating, comment):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO reviews (user_id, rating, comment) VALUES (%s, %s, %s)",
              (user_id, rating, comment))
    conn.commit()
    conn.close()
    return True

# ==================== TIP HELPERS ====================

def get_all_tips():
    conn = get_db()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute('''SELECT t.*, u.first_name, u.last_name, u.business_name
               FROM tips t 
               JOIN users u ON t.user_id = u.id 
               ORDER BY t.created_at DESC''')
    tips = c.fetchall()
    conn.close()
    return tips

def save_tip(user_id, amount, message):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO tips (user_id, amount, message) VALUES (%s, %s, %s)",
              (user_id, amount, message))
    conn.commit()
    conn.close()
    return True

# Debug function to check database connection
def get_db_info():
    import os
    return {
        'database_url': DATABASE_URL,
        'type': 'PostgreSQL',
        'connected': True
    }

if __name__ == '__main__':
    init_db()
    print("\n🔍 Database Summary:")
    print(f"   Database Type: PostgreSQL")
    print(f"   Database URL: {DATABASE_URL}")
    print(f"   Total Users: {get_user_count()}")
    duplicate_emails = check_duplicate_emails()
    if duplicate_emails:
        print(f"   ⚠️ Duplicate Emails Found: {len(duplicate_emails)}")
        for dup in duplicate_emails:
            print(f"      - {dup['email']}: {dup['count']} times")
    else:
        print("   ✅ No duplicate emails found")
    print("\n✅ database.py loaded successfully!")
