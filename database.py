import sqlite3

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
    
    # Add is_deleted column if not exists (for existing DB)
    try:
        c.execute('ALTER TABLE messages ADD COLUMN is_deleted INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # column already exists
    
    # Insert admin
    c.execute("SELECT * FROM users WHERE email='admin@sleen.com'")
    if not c.fetchone():
        c.execute('''INSERT INTO users (email, first_name, last_name, business_name, business_address, password, role)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  ('admin@sleen.com', 'Admin', 'Sleen', 'Sleen Inc', '123 Main St', 'admin123', 'admin'))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")

init_db()