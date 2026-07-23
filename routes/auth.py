import random
import sys
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from database.db_handler import get_db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password')
        
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
                INSERT INTO users (username, email, password_hash, role, is_verified, otp_code)
                VALUES (?, ?, ?, 'customer', 0, ?)
            ''', (username, email, password_hash, otp))
            conn.commit()
            
            # --- DIRECT EMAIL DISPATCH ENGINE ---
            try:
                mail = current_app.extensions.get('mail')
                msg = Message("Ihsan Grocery Shop - Email Verification Code", recipients=[email])
                msg.body = f"Assalam-o-Alaikum {username},\n\nApka 6-Digit Verification OTP Code yeh hai: {otp}\n\nApna account verify karne ke liye yeh code website par enter karein."
                mail.send(msg)
                print(f"--> SUCCESS: OTP sent via email to {email}", file=sys.stderr)
                flash('Verification code aapke Email inbox par bhej diya gaya hai.', 'info')
            except Exception as mail_error:
                print(f"--> SMTP MAIL ERROR: {str(mail_error)}", file=sys.stderr)
                flash('Email sending mein masla aaya hai. Kripya app password check karein.', 'error')

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
        input_otp = request.form.get('otp').strip()
        
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
        email = request.form.get('email').strip()
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            if not user['is_verified']:
                session['verify_email'] = user['email']
                
                new_otp = str(random.randint(100000, 999999))
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET otp_code = ? WHERE email = ?", (new_otp, user['email']))
                conn.commit()
                conn.close()
                
                try:
                    mail = current_app.extensions.get('mail')
                    msg = Message("Ihsan Grocery Shop - New Verification Code", recipients=[user['email']])
                    msg.body = f"Assalam-o-Alaikum {user['username']},\n\nApka naya 6-Digit Verification OTP Code yeh hai: {new_otp}"
                    mail.send(msg)
                    flash('Apka email verified nahi hai. Naya OTP aapki email par bhej diya gaya hai.', 'warning')
                except Exception as mail_err:
                    print(f"--> LOGIN SMTP ERROR: {str(mail_err)}", file=sys.stderr)
                    flash('Email send nahi ho saka. App Password check karein.', 'error')
                
                return redirect(url_for('auth.verify_otp'))
                
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role'] 
            
            flash(f"Khush Aamdeed, {user['username']}!", 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('customer.home'))
        else:
            flash('Ghalat Email ya Password, dobara koshish karein.', 'error')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Aap successfully logout ho chuke hain.', 'info')
    return redirect(url_for('customer.home'))