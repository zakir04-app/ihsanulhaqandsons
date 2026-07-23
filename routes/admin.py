import os
import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, Response
from werkzeug.utils import secure_filename
from database.db_handler import get_db_connection

admin_bp = Blueprint('admin', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def is_admin():
    return session.get('role') == 'admin'

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
        flash('Product dynamic properties ke sath catalog me list ho gaya!', 'success')
        return redirect(url_for('admin.dashboard'))
        
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
    categories = [r['category'] for r in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM banners ORDER BY id DESC")
    banners = cursor.fetchall()
    
    cursor.execute('''
        SELECT orders.id, users.username, users.email, orders.total_price, orders.payment_method, orders.transaction_id, orders.status 
        FROM orders 
        JOIN users ON orders.user_id = users.id
        ORDER BY orders.id DESC
    ''')
    orders = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'Pending'")
    total_orders = cursor.fetchone()['count']

    # --- FETCH USER DATA FOR ADMIN MANAGEMENT ---
    cursor.execute("SELECT id, username, email, role, is_verified FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    
    conn.close()
    return render_template('admin_dashboard.html', products=products, categories=categories, banners=banners, orders=orders, total_orders=total_orders, users=users)

# --- ADVANCED CMS & STORE LAYOUT SETTINGS ---
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
        
    conn.commit()
    conn.close()
    flash('Website Layout, Theme Color & Dynamic Content successfully updated!', 'success')
    return redirect(url_for('admin.dashboard'))

# --- USER MANAGEMENT ROUTES ---
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
    
    flash(f"User #{user_id} account details successfully update ho gayi hain!", 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/user/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not is_admin(): return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    flash("User account successfully delete kar diya gaya hai!", 'warning')
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
    flash('Offer Banner added & Published!', 'success')
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
    flash('Banner removed successfully!', 'info')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/bulk-template', methods=['GET'])
def download_template():
    if not is_admin(): return redirect(url_for('auth.login'))
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'description', 'price', 'stock', 'image_url', 'category'])
    writer.writerow(['Sufi Sun Oil 1L', 'Pure cooking oil batch A', '520.00', '100', 'https://example.com/oil.jpg', 'Cooking Essentials'])
    writer.writerow(['Tapal Danedar 430g', 'Premium leaf strong tea', '680.00', '50', '', 'Beverages'])
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=sample_products_template.csv'
    return response

@admin_bp.route('/bulk-upload', methods=['POST'])
def bulk_upload():
    if not is_admin(): return redirect(url_for('auth.login'))
    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash('Meharbani karke sirf (.csv) extension waali file select karein.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    filepath = os.path.join('C:\\Windows\\Temp' if os.name == 'nt' else '/tmp', secure_filename(file.filename))
    file.save(filepath)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cat = row.get('category', 'General').strip()
                if not cat: cat = 'General'
                cursor.execute('''
                    INSERT INTO products (name, description, price, stock, image_url, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['name'].strip(), row.get('description', '').strip(), float(row['price']), int(row['stock']), row.get('image_url', '').strip(), cat))
                count += 1
        conn.commit()
        flash(f'Inventory synchronized! {count} products added via Bulk Upload.', 'success')
    except Exception as e:
        print("--> CSV PARSE EXCEPTION:", str(e))
        flash(f'CSV Format Parsing Error: {str(e)}.', 'error')
    finally:
        conn.close()
        if os.path.exists(filepath): os.remove(filepath)
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/order/status/<int:order_id>/<string:status>', methods=['POST'])
def update_order_status(order_id, status):
    if not is_admin(): return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()
    flash(f"Order #{order_id} status updated to {status}!", 'success')
    return redirect(url_for('admin.dashboard'))