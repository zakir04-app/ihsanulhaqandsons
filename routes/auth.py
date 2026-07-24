import random
import sys
import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from database.db_handler import get_db_connection

auth_bp = Blueprint('auth', __name__)

def send_email_via_brevo_api(recipient_email, username, otp_code):
    """Sends OTP using Brevo HTTPS API on Port 443 (Bypasses Render SMTP Blocks)"""
    api_key = os.environ.get('BREVO_API_KEY', 'FyExk7nvDBS4POHM')
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    payload = {
        "sender": {"name": "Ihsan Grocery Shop", "email": "zakir.ullah0004@gmail.com"},
        "to": [{"email": recipient_email}],
        "subject": "Ihsan Grocery Shop - Verification Code",
        "htmlContent": f"<h3>Assalam-o-Alaikum {username},</h3><p>Apka 6-Digit Verification OTP Code: <b>{otp_code}</b></p>"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201, 202]:
            print(f"--> SUCCESS: Brevo API sent OTP to {recipient_email}", file=sys.stderr)
            return True
        else:
            print(f"--> BREVO API ERROR: {response.status_code} - {response.text}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"--> API REQUEST EXCEPTION: {str(e)}", file=sys.stderr)
        return False

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        if not username or not email or not password:
            flash('Tamam fields fill karna lazmi hain.', 'error')
            return redirect(url_for('auth.register'))
            
        otp = str(random.randint(100000, 999999))
        password_hash = generate_password_hash(password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            conn.close()
            flash('Yeh Email pehle se register hai. Meharbani karke login karein.', 'error')
            return redirect(url_for('auth.register'))
            
        try:
            cursor.execute('''
                INSERT INTO users (username, email, password, password_hash, role, is_verified, otp_code)
                VALUES (?, ?, ?, ?, 'customer', 0, ?)
            ''', (username, email, password_hash, password_hash, otp))
            conn.commit()
            
            # --- EMAIL DISPATCH VIA HTTPS API ---
            sent = send_email_via_brevo_api(email, username, otp)
            if sent:
                flash('Verification code aapke Email inbox par bhej diya gaya hai.', 'info')
            else:
                flash(f'Email send nahi ho saka. (Testing OTP Code: {otp})', 'warning')

            session['verify_email'] = email
            return redirect(url_for('auth.verify_otp'))
            
        except Exception as db_error:
            print(f"--> DATABASE ERROR: {str(db_error)}", file=sys.stderr)
            flash('Registration ke dauran koi database error aya hai.', 'error')
        finally:
            conn.close()
            
    return render_template('register.html')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('verify_email')
    if not email:
        flash('Pehle register ya login karein taake OTP process shuru ho.', 'error')
        return redirect(url_for('auth.register'))
        
    if request.method == 'POST':
        input_otp = request.form.get('otp', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if user:
            print(f"--> VERIFYING: DB_OTP={user['otp_code']}, INPUT_OTP={input_otp}", file=sys.stderr)
            
            if str(user['otp_code']) == str(input_otp):
                cursor.execute("UPDATE users SET is_verified = 1, otp_code = NULL WHERE email = ?", (email,))
                conn.commit()
                conn.close()
                session.pop('verify_email', None)
                flash('Email kamyabi se verify ho gaya hai! Ab login karein.', 'success')
                return redirect(url_for('auth.login'))
        
        conn.close()
        flash('Ghalat OTP Code enter kiya hai. Dobara check karke enter karein.', 'error')
        return redirect(url_for('auth.verify_otp'))
            
    return render_template('verify_otp.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            stored_hash = user['password_hash'] if 'password_hash' in user.keys() and user['password_hash'] else user['password']
            
            if check_password_hash(stored_hash, password) or user['password'] == password:
                if not user['is_verified']:
                    session['verify_email'] = user['email']
                    
                    new_otp = str(random.randint(100000, 999999))
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET otp_code = ? WHERE email = ?", (new_otp, user['email']))
                    conn.commit()
                    conn.close()
                    
                    sent = send_email_via_brevo_api(user['email'], user['username'], new_otp)
                    if sent:
                        flash('Apka email verified nahi hai. Naya OTP aapki email par bhej diya gaya hai.', 'warning')
                    else:
                        flash(f'Email send nahi ho saka. (Testing OTP Code: {new_otp})', 'warning')
                    
                    return redirect(url_for('auth.verify_otp'))
                    
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                session['role'] = user['role'] 
                
                flash(f"Khush Aamdeed, {user['username']}!", 'success')
                if user['role'] == 'admin':
                    return redirect(url_for('admin.dashboard'))
                return redirect(url_for('customer.home'))
                
        flash('Ghalat Email ya Password, dobara koshish karein.', 'error')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Aap successfully logout ho chuke hain.', 'info')
    return redirect(url_for('customer.home'))