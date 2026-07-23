import os
import socket
from flask import Flask, session
from flask_mail import Mail
from database.db_handler import init_db, get_db_connection
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.customer import customer_bp

# Network socket timeout to prevent server hanging on failed connections
socket.setdefaulttimeout(10)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secure_secret_key_ihsan_grocery')

# --- SECURITY UPLOAD DIRECTORY SYSTEM ---
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB file size limit

# --- CLEAN & ACCURATE MAIL CONFIGURATION ---
# Clean env string in case extra spaces/quotes exist in Render config
raw_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com').strip().replace("'", "").replace('"', '')
app.config['MAIL_SERVER'] = raw_server if raw_server and not raw_server.isdigit() else 'smtp.gmail.com'

try:
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
except ValueError:
    app.config['MAIL_PORT'] = 587

# Auto-align TLS and SSL based on Port to avoid SSL/TLS conflicts
if app.config['MAIL_PORT'] == 465:
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True
else:
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False

app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'zakir.ullah0004@gmail.com').strip()
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'xjetasdhvhunlogy').strip()
app.config['MAIL_DEFAULT_SENDER'] = ('Ihsan Ul Haq & Sons General Store', app.config['MAIL_USERNAME'])
app.config['MAIL_TIMEOUT'] = 10

mail = Mail(app)
app.extensions['mail'] = mail

# GLOBAL CONTEXT PROCESSOR: Injecting cart counter and site global parameters dynamically
@app.context_processor
def inject_global_site_data():
    cart = session.get('cart', {})
    total_count = sum(cart.values()) if cart else 0
    
    # Load dynamic brand metrics safely
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings")
        settings = {r['key']: r['value'] for r in cursor.fetchall()}
        conn.close()
    except Exception as e:
        settings = {}
    
    return dict(
        cart_count=total_count,
        site_title=settings.get('store_title', 'Ihsan Grocery Shop'),
        site_cover=settings.get('cover_image', '')
    )

# Database Initialization
init_db()

# Blueprints Registration
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(customer_bp)

if __name__ == '__main__':
    app.run(debug=True)