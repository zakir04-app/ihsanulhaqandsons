import os
import csv
import io
import sys
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, Response, send_file
from werkzeug.utils import secure_filename
from database.db_handler import get_db_connection

admin_bp = Blueprint('admin', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def is_admin():
    return session.get('role') == 'admin'

def send_status_notification_email(recipient_email, username, order_id, status):
    api_key = os.environ.get('BREVO_API_KEY', '')
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    if status == 'Dispatched':
        subject = f"🚚 Order #{order_id} Dispatched - Delivering Soon!"
        content_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px;">
            <h2 style="color: #0d6efd; text-align: center;">Ihsan Ul Haq & Sons General Store</h2>
            <hr>
            <h3>Assalam-o-Alaikum {username},</h3>
            <p style="font-size: 16px;">Aapka <b>Order #{order_id}</b> humne <b>Dispatched</b> kar diya hai!</p>
            <div style="background-color: #cff4fc; color: #055160; padding: 15px; border-radius: 5px; border-left: 4px solid #0dcaf0;">
                <p style="margin: 0;"><b>🚪 Next Step - Doorstep Delivery:</b> Meharbani karke apne order ka intizar kijye. Delivery rider jald hi aapke diye gaye address par pohochne wala hai.</p>
            </div>
            <p>Agar aapne COD (Cash on Delivery) chuna tha to rider ke liye cash ready rakhein.</p>
            <hr>
            <p style="font-size: 12px; color: #777; text-align: center;">Shukriya! Ihsan Store Team</p>
        </div>
        """
    elif status == 'Delivered':
        subject = f"🎉 Order #{order_id} Delivered - Thank You!"
        content_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px;">
            <h2 style="color: #198754; text-align: center;">Ihsan Ul Haq & Sons General Store</h2>
            <hr>
            <h3>Assalam-o-Alaikum {username},</h3>
            <p style="font-size: 16px;">Aapka <b>Order #{order_id} Mukamal (Delivered)</b> ho chuka hai! Ihsan Store se khareedari karne ka behad shukriya.</p>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #eee; margin: 20px 0;">
                <h4 style="margin-top: 0; color: #333;">Aapka Experience Kaisa Raha?</h4>
                <p style="color: #666; font-size: 14px;">Please niche diye gaye Rating Stars par click karke feedback dein:</p>
                <div style="font-size: 24px; letter-spacing: 5px;">
                    <a href="#" style="text-decoration: none;">⭐</a>
                    <a href="#" style="text-decoration: none;">⭐</a>
                    <a href="#" style="text-decoration: none;">⭐</a>
                    <a href="#" style="text-decoration: none;">⭐</a>
                    <a href="#" style="text-decoration: none;">⭐</a>
                </div>
            </div>
            <hr>
            <p style="font-size: 12px; color: #777; text-align: center;">Ihsan Store - Quality Grocery Delivered With Trust.</p>
        </div>
        """
    else:
        return False
        
    payload = {
        "sender": {"name": "Ihsan Grocery Store", "email": "zakir.ullah0004@gmail.com"},
        "to": [{"email": recipient_email}],
        "subject": subject,
        "htmlContent": content_html
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
            upload_folder = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'static', 'uploads'))
            os.makedirs(upload_folder, exist_ok=True)
            save_path = os.path.join(upload_folder, unique_name)
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
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        
        uploaded_img = handle_image_upload('product_file')
        fallback_url = request.form.get('image_url', '').strip()
        image_url = uploaded_img if uploaded_img else fallback_url
        
        selected_category = request.form.get('category_select', '').strip()
        custom_category = request.form.get('category_custom', '').strip()
        category = custom_category if custom_category else selected_category
        if not category: 
            category = "General"
            
        cursor.execute('''
            INSERT INTO products (name, description, price, stock, image_url, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, price, stock, image_url, category))
        conn.commit()
        flash(f'Product catalog mein category "{category}" ke sath add ho gaya!', 'success')
        return redirect(url_for('admin.dashboard'))
        
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT TRIM(category) as category FROM products WHERE category IS NOT NULL AND TRIM(category) != ''")
    categories = [r['category'] for r in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM banners ORDER BY id DESC")
    banners_raw = cursor.fetchall()
    
    banners = []
    for b in banners_raw:
        banner_dict = dict(b)
        cursor.execute("SELECT id, name, price FROM products WHERE banner_id = ?", (banner_dict['id'],))
        banner_dict['linked_products'] = cursor.fetchall()
        banners.append(banner_dict)
    
    cursor.execute('''
        SELECT orders.*, COALESCE(users.username, 'Guest') as username, COALESCE(users.email, 'N/A') as email
        FROM orders 
        LEFT JOIN users ON orders.user_id = users.id
        ORDER BY orders.id DESC
    ''')
    orders_raw = cursor.fetchall()
    
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
    
    # Live Badge Notification Counters
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'Placed Order'")
    total_orders = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM products WHERE stock < 10")
    low_stock_count = cursor.fetchone()['count']

    cursor.execute("SELECT id, username, email, role FROM users ORDER BY id DESC")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM site_settings")
    settings_rows = cursor.fetchall()
    site_settings = {row['key']: row['value'] for row in settings_rows}
    
    conn.close()
    return render_template(
        'admin_dashboard.html', 
        products=products, 
        categories=categories, 
        banners=banners, 
        orders=orders, 
        total_orders=total_orders, 
        low_stock_count=low_stock_count,
        users=users, 
        settings=site_settings
    )

@admin_bp.route('/product/edit/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    if not is_admin(): return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        conn.close()
        flash('Product nahi mila.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    price = float(request.form.get('price', product['price']))
    stock = int(request.form.get('stock', product['stock']))
    
    selected_category = request.form.get('category_select', '').strip()
    custom_category = request.form.get('category_custom', '').strip()
    category = custom_category if custom_category else selected_category
    if not category: 
        category = product['category'] or "General"
    
    uploaded_img = handle_image_upload('product_file')
    fallback_url = request.form.get('image_url', '').strip()
    image_url = uploaded_img if uploaded_img else (fallback_url if fallback_url else product['image_url'])
    
    cursor.execute('''
        UPDATE products 
        SET name = ?, description = ?, price = ?, stock = ?, category = ?, image_url = ?
        WHERE id = ?
    ''', (name, description, price, stock, category, image_url, product_id))
    
    conn.commit()
    conn.close()
    flash(f'Product #{product_id} ({name}) successfully update ho gaya!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/product/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if not is_admin(): return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash(f'Product #{product_id} catalog se delete ho gaya.', 'warning')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/banner/add', methods=['POST'])
def add_banner():
    if not is_admin(): return redirect(url_for('auth.login'))
    
    title = request.form.get('title', '').strip()
    offer_text = request.form.get('offer_text', '').strip()
    discount_percentage = int(request.form.get('discount_percentage', 0))
    selected_products = request.form.getlist('offer_products')
    target_category = request.form.get('target_category', '').strip()
    
    uploaded_banner = handle_image_upload('banner_file')
    fallback_url = request.form.get('image_url', '').strip()
    image_url = uploaded_banner if uploaded_banner else fallback_url
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO banners (title, offer_text, image_url, discount_percentage) VALUES (?, ?, ?, ?)', 
                       (title, offer_text, image_url, discount_percentage))
        banner_id = cursor.lastrowid
        
        if target_category and target_category != 'ALL':
            cursor.execute("UPDATE products SET banner_id = ? WHERE category = ?", (banner_id, target_category))
        elif target_category == 'ALL':
            cursor.execute("UPDATE products SET banner_id = ?", (banner_id,))
            
        if selected_products:
            for prod_id in selected_products:
                cursor.execute("UPDATE products SET banner_id = ? WHERE id = ?", (banner_id, prod_id))
                
        conn.commit()
        flash('Offer Banner Published & Items Linked Successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Banner Error: {str(e)}', 'error')
    finally:
        conn.close()
        
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
    flash('Banner and discount removed!', 'info')
    return redirect(url_for('admin.dashboard'))

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
    flash('CMS Theme, Address & Contact Email successfully updated and synced!', 'success')
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
        send_status_notification_email(customer_info['email'], customer_info['username'], order_id, status)
        
    flash(f"Order #{order_id} status updated to {status} & Notification sent!", 'success')
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