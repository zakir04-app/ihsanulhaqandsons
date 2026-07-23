import os
import csv
import io
import sys
import requests
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, Response, send_file
from werkzeug.utils import secure_filename
from database.db_handler import get_db_connection

admin_bp = Blueprint('admin', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def is_admin():
    return session.get('role') == 'admin'

def send_status_email(recipient_email, username, order_id, status):
    """Sends status change notification to customer"""
    api_key = os.environ.get('BREVO_API_KEY', 'FyExk7nvDBS4POHM')
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    status_colors = {
        'Placed Order': '#ffc107',
        'Dispatched': '#0d6efd',
        'Delivered': '#198754'
    }
    color = status_colors.get(status, '#198754')
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px;">
        <h2 style="color: #198754; text-align: center;">Ihsan Ul Haq & Sons General Store</h2>
        <hr>
        <h3>Assalam-o-Alaikum {username},</h3>
        <p>Aapke <b>Order #{order_id}</b> ka status update ho chuka hai:</p>
        <p style="font-size: 18px; text-align: center; padding: 10px; background-color: {color}; color: white; border-radius: 5px; font-weight: bold;">
            {status}
        </p>
        <p>Aapke order ki tayari/delivery hamare standard schedule ke mutabiq jari hai. Kisi bhi query ke liye hum se rabta karein.</p>
        <hr>
        <p style="font-size: 12px; color: #777; text-align: center;">Shukriya! Ihsan Store Team</p>
    </div>
    """
    
    payload = {
        "sender": {"name": "Ihsan Grocery Store", "email": "zakir.ullah0004@gmail.com"},
        "to": [{"email": recipient_email}],
        "subject": f"Order #{order_id} Status Update: {status}",
        "htmlContent": html
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"--> STATUS EMAIL EXCEPTION: {str(e)}", file=sys.stderr)
        return False

def handle_image_upload(file_input_name):
    if file_input_name not in request.files:
        return None
    file = request.files[file_input_name]
    if file and file.filename != '':
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if ext in ALLOWED_EXTENSIONS:
            filename = secure_filename(file.filename)
            unique_name = f"upload_{os.urandom(4).hex()}_{filename}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
            file.save(save_path)
            return f"/static/uploads/{unique_name}"
    return None

@admin_bp.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not is_admin():
        flash('Aap is page ko access nahi kar sakte.', 'error')
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        name = request.form.get('name').strip()
        description = request.form.get('description').strip()
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        
        uploaded_img = handle_image_upload('product_file')
        fallback_url = request.form.get('image_url').strip()
        image_url = uploaded_img if uploaded_img else fallback_url
        
        selected_category = request.form.get('category_select')
        custom_category = request.form.get('category_custom').strip()
        category = custom_category if custom_category else selected_category
        if not category: category = "General"
            
        cursor.execute('''
            INSERT INTO products (name, description, price, stock, image_url, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, price, stock, image_url, category))
        conn.commit()
        flash('Product dynamic catalog me list ho gaya!', 'success')
        return redirect(url_for('admin.dashboard'))
        
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
    categories = [r['category'] for r in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM banners ORDER BY id DESC")
    banners = cursor.fetchall()
    
    cursor.execute('''
        SELECT orders.id, COALESCE(users.username, 'Guest') as username, COALESCE(users.email, 'N/A') as email, orders.total_price, orders.payment_method, orders.transaction_id, orders.status 
        FROM orders 
        LEFT JOIN users ON orders.user_id = users.id
        ORDER BY orders.id DESC
    ''')
    orders_raw = cursor.fetchall()
    
    # Using 'order_items_list' to resolve dict.items() Jinja2 method collision
    orders = []
    for ord_item in orders_raw:
        o = dict(ord_item)
        cursor.execute('''
            SELECT order_items.quantity, order_items.price, products.name 
            FROM order_items
            JOIN products ON order_items.product_id = products.id
            WHERE order_items.order_id = ?
        ''', (o['id'],))
        o['order_items_list'] = cursor.fetchall()
        orders.append(o)
    
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'Placed Order'")
    total_orders = cursor.fetchone()['count']

    cursor.execute("SELECT id, username, email, role, is_verified FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    
    conn.close()
    return render_template('admin_dashboard.html', products=products, categories=categories, banners=banners, orders=orders, total_orders=total_orders, users=users)

@admin_bp.route('/settings/update', methods=['POST'])
def update_settings():
    if not is_admin(): return redirect(url_for('auth.login'))
    
    store_title = request.form.get('store_title', '').strip()
    primary_color = request.form.get('primary_color', '#198754').strip()
    contact_phone = request.form.get('contact_phone', '').strip()
    contact_email = request.form.get('contact_email', '').strip()
    contact_address = request.form.get('contact_address', '').strip()
    whatsapp_no = request.form.get('whatsapp_no', '').strip()
    about_text = request.form.get('about_text', '').strip()
    
    uploaded_cover = handle_image_upload('cover_file')
    uploaded_logo = handle_image_upload('logo_file')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    settings_dict = {
        'store_title': store_title,
        'primary_color': primary_color,
        'contact_phone': contact_phone,
        'contact_email': contact_email,
        'contact_address': contact_address,
        'whatsapp_no': whatsapp_no,
        'about_text': about_text
    }
    
    for key, val in settings_dict.items():
        if val:
            cursor.execute("INSERT OR REPLACE INTO site_settings (key, value) VALUES (?, ?)", (key, val))
            
    if uploaded_cover:
        cursor.execute("INSERT OR REPLACE INTO site_settings (key, value) VALUES ('cover_image', ?)", (uploaded_cover,))
    if uploaded_logo:
        cursor.execute("INSERT OR REPLACE INTO site_settings (key, value) VALUES ('site_logo', ?)", (uploaded_logo,))
        
    conn.commit()
    conn.close()
    flash('Website Layout, Theme, Logo & Dynamic Content updated successfully!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/order/status/<int:order_id>/<string:status>', methods=['POST'])
def update_order_status(order_id, status):
    if not is_admin(): return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT users.email, users.username 
        FROM orders 
        LEFT JOIN users ON orders.user_id = users.id 
        WHERE orders.id = ?
    ''', (order_id,))
    customer_info = cursor.fetchone()
    
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()
    
    if customer_info and customer_info['email'] != 'N/A':
        send_status_email(customer_info['email'], customer_info['username'], order_id, status)
        
    flash(f"Order #{order_id} status updated to {status} aur customer ko notification bhej di gayi hai!", 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/user/edit/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    if not is_admin(): return redirect(url_for('auth.login'))
    username = request.form.get('username').strip()
    email = request.form.get('email').strip()
    role = request.form.get('role').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET username = ?, email = ?, role = ? WHERE id = ?", (username, email, role, user_id))
    conn.commit()
    conn.close()
    flash(f"User #{user_id} account details updated!", 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/user/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not is_admin(): return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User account deleted!", 'warning')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/banner/add', methods=['POST'])
def add_banner():
    if not is_admin(): return redirect(url_for('auth.login'))
    title = request.form.get('title').strip()
    offer_text = request.form.get('offer_text').strip()
    discount_percentage = int(request.form.get('discount_percentage', 0))
    selected_products = request.form.getlist('offer_products')
    uploaded_banner = handle_image_upload('banner_file')
    fallback_url = request.form.get('image_url').strip()
    image_url = uploaded_banner if uploaded_banner else fallback_url
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO banners (title, offer_text, image_url, discount_percentage) VALUES (?, ?, ?, ?)', (title, offer_text, image_url, discount_percentage))
    banner_id = cursor.lastrowid
    
    if selected_products:
        for prod_id in selected_products:
            cursor.execute("UPDATE products SET banner_id = ? WHERE id = ?", (banner_id, prod_id))
            
    conn.commit()
    conn.close()
    flash('Offer Banner Published!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/banner/edit/<int:banner_id>', methods=['POST'])
def edit_banner(banner_id):
    if not is_admin(): return redirect(url_for('auth.login'))
    new_discount = int(request.form.get('discount_percentage', 0))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE banners SET discount_percentage = ? WHERE id = ?", (new_discount, banner_id))
    conn.commit()
    conn.close()
    flash('Banner Discount updated!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/banner/delete/<int:banner_id>', methods=['POST'])
def delete_banner(banner_id):
    if not is_admin(): return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET banner_id = NULL WHERE banner_id = ?", (banner_id,))
    cursor.execute("DELETE FROM banners WHERE id = ?", (banner_id,))
    conn.commit()
    conn.close()
    flash('Banner removed!', 'info')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/bulk-template', methods=['GET'])
def download_template():
    if not is_admin(): return redirect(url_for('auth.login'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'description', 'price', 'stock', 'image_url', 'category'])
    writer.writerow(['Sufi Sun Oil 1L', 'Pure cooking oil', '520.00', '100', '', 'Essentials'])
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=sample_template.csv'
    return response

@admin_bp.route('/bulk-upload', methods=['POST'])
def bulk_upload():
    if not is_admin(): return redirect(url_for('auth.login'))
    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash('Sirf CSV file upload karein.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    filepath = os.path.join('/tmp', secure_filename(file.filename))
    file.save(filepath)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cat = row.get('category', 'General').strip() or 'General'
                cursor.execute('''
                    INSERT INTO products (name, description, price, stock, image_url, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['name'].strip(), row.get('description', '').strip(), float(row['price']), int(row['stock']), row.get('image_url', '').strip(), cat))
                count += 1
        conn.commit()
        flash(f'{count} products added successfully!', 'success')
    except Exception as e:
        flash(f'CSV Error: {str(e)}', 'error')
    finally:
        conn.close()
        if os.path.exists(filepath): os.remove(filepath)
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/db/backup', methods=['GET'])
def backup_database():
    if not is_admin(): return redirect(url_for('auth.login'))
    db_path = os.path.join(current_app.root_path, 'database.db')
    if os.path.exists(db_path):
        return send_file(
            db_path,
            as_attachment=True,
            download_name=f"IhsanStore_Backup_{os.urandom(2).hex()}.db",
            mimetype='application/x-sqlite3'
        )
    else:
        flash('Database file nahi mili.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/db/restore', methods=['POST'])
def restore_database():
    if not is_admin(): return redirect(url_for('auth.login'))
    file = request.files.get('backup_db_file')
    if not file or not file.filename.endswith('.db'):
        flash('Meharbani karke sirf (.db) backup file select karein.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    db_path = os.path.join(current_app.root_path, 'database.db')
    try:
        file.save(db_path)
        flash('Alhamdulillah! Aapki Hard Disk se Data Successfully Restore ho gaya hai.', 'success')
    except Exception as e:
        flash(f'Restore error: {str(e)}', 'error')
        
    return redirect(url_for('admin.dashboard'))