import os
import socket
from flask import Flask, session
from flask_mail import Mail
from database.db_handler import init_db, get_db_connection
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.customer import customer_bp

socket.setdefaulttimeout(15)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ihsan_grocery_secret_key_2026')

# --- SECURITY UPLOAD DIRECTORY SYSTEM ---
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# --- MAIL CONFIGURATION ---
raw_server = os.environ.get('MAIL_SERVER', 'smtp-relay.brevo.com').strip().replace("'", "").replace('"', '')
app.config['MAIL_SERVER'] = raw_server if raw_server and not raw_server.isdigit() else 'smtp-relay.brevo.com'

try:
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
except (ValueError, TypeError):
    app.config['MAIL_PORT'] = 587

raw_tls = os.environ.get('MAIL_USE_TLS', 'True').strip().lower()
raw_ssl = os.environ.get('MAIL_USE_SSL', 'False').strip().lower()

if app.config['MAIL_PORT'] == 465:
    app.config['MAIL_USE_SSL'] = True
    app.config['MAIL_USE_TLS'] = False
else:
    app.config['MAIL_USE_SSL'] = (raw_ssl == 'true')
    app.config['MAIL_USE_TLS'] = (raw_tls == 'true')

app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'b305f2001@smtp-brevo.com').strip()
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'FyExk7nvDBS4POHM').strip()
app.config['MAIL_DEFAULT_SENDER'] = ('Ihsan Ul Haq & Sons General Store', 'zakir.ullah0004@gmail.com')
app.config['MAIL_TIMEOUT'] = 15

mail = Mail(app)
app.extensions['mail'] = mail

# GLOBAL CONTEXT PROCESSOR: Injecting Store Theme, Contact Details & CMS Values
@app.context_processor
def inject_global_site_data():
    cart = session.get('cart', {})
    total_count = sum(cart.values()) if cart else 0
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM site_settings")
        settings = {r['key']: r['value'] for r in cursor.fetchall()}
        conn.close()
    except Exception:
        settings = {}
    
    return dict(
        cart_count=total_count,
        site_title=settings.get('store_title', 'Ihsan Grocery Shop'),
        site_cover=settings.get('cover_image', ''),
        primary_color=settings.get('primary_color', '#198754'),
        contact_phone=settings.get('contact_phone', '+92 300 0000000'),
        contact_email=settings.get('contact_email', 'info@ihsangrocery.com'),
        contact_address=settings.get('contact_address', 'Main Bazar, City'),
        whatsapp_no=settings.get('whatsapp_no', '923000000000'),
        about_text=settings.get('about_text', 'Welcome to Ihsan Ul Haq & Sons General Store.')
    )

init_db()

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(customer_bp)

if __name__ == '__main__':
    app.run(debug=True)