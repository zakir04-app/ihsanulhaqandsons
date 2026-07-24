import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Products Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            image_url TEXT,
            category TEXT,
            banner_id INTEGER
        )
    ''')
    
    # Users Table with OTP support
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT,
            password_hash TEXT,
            role TEXT DEFAULT 'customer',
            is_verified INTEGER DEFAULT 0,
            otp_code TEXT
        )
    ''')
    
    # Auto Migration for Missing Columns in Users Table
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col['name'] for col in cursor.fetchall()]
    if 'password_hash' not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if 'password' not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN password TEXT")
    if 'is_verified' not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
    if 'otp_code' not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN otp_code TEXT")

    # Orders Table with Address and Phone
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            phone_number TEXT,
            address TEXT,
            city TEXT,
            total_price REAL NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_id TEXT,
            status TEXT DEFAULT 'Placed Order',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Auto Migration for Missing Columns in Orders Table
    cursor.execute("PRAGMA table_info(orders)")
    order_columns = [col['name'] for col in cursor.fetchall()]
    if 'full_name' not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN full_name TEXT")
    if 'phone_number' not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN phone_number TEXT")
    if 'address' not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN address TEXT")
    if 'city' not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN city TEXT")

    # Order Items Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # Banners Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            offer_text TEXT,
            image_url TEXT,
            discount_percentage INTEGER DEFAULT 0
        )
    ''')

    # Site Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Execute Default Data Seeding
    seed_default_data()

def seed_default_data():
    """Inserts essential admin account, store settings, and base inventory if database is fresh"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Ensure Permanent Admin User Exists
    admin_email = "zakir.ullah0004@gmail.com"
    cursor.execute("SELECT id FROM users WHERE email = ?", (admin_email,))
    if not cursor.fetchone():
        hashed_pass = generate_password_hash("admin123")
        cursor.execute('''
            INSERT INTO users (username, email, password, password_hash, role, is_verified)
            VALUES (?, ?, ?, ?, 'admin', 1)
        ''', ('Zakir Admin', admin_email, hashed_pass, hashed_pass))
        print("--> DEFAULT ADMIN ACCOUNT CREATED SUCCESSFULLY")

    # 2. Ensure Store CMS Settings Exist
    default_settings = {
        'store_title': 'Ihsan Ul Haq & Sons General Store',
        'primary_color': '#198754',
        'contact_phone': '+92 300 0000000',
        'contact_email': 'zakir.ullah0004@gmail.com',
        'contact_address': 'Main Market Road, City',
        'whatsapp_no': '923000000000',
        'about_text': 'Welcome to Ihsan Ul Haq & Sons General Store.'
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)", (k, v))

    # 3. Ensure Default Inventory Base Exists
    cursor.execute("SELECT COUNT(*) as cnt FROM products")
    if cursor.fetchone()['cnt'] == 0:
        base_products = [
            ('Sufi Cooking Oil 1L', 'Pure vegetable cooking oil', 520.00, 100, '', 'Essentials'),
            ('Basmati Rice 5kg', 'Premium long grain rice', 1450.00, 50, '', 'Grains'),
            ('Wheat Flour (Atta) 10kg', 'Whole wheat fresh flour', 1200.00, 40, '', 'Grains'),
            ('MilkPak 1L', 'UHT Pure Milk Pack', 290.00, 200, '', 'Dairy')
        ]
        for name, desc, price, stock, img, cat in base_products:
            cursor.execute('''
                INSERT INTO products (name, description, price, stock, image_url, category)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, desc, price, stock, img, cat))
        print("--> BASE INVENTORY SEEDED SUCCESSFULLY")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()