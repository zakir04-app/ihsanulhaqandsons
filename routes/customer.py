import os
import sys
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db_handler import get_db_connection

customer_bp = Blueprint('customer', __name__)

ADMIN_NOTIFICATION_EMAIL = "zakir.ullah0004@gmail.com"

def send_email_via_brevo(to_email, subject, html_content):
    """Generic function to send transactional emails via Brevo HTTPS API"""
    api_key = os.environ.get('BREVO_API_KEY', 'FyExk7nvDBS4POHM')
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    payload = {
        "sender": {"name": "Ihsan Grocery Store", "email": ADMIN_NOTIFICATION_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"--> BREVO EMAIL ERROR: {str(e)}", file=sys.stderr)
        return False

def generate_invoice_html(username, order_id, cart_items, grand_total, payment_method, trx_id, is_admin_copy=False):
    """Generates a professional HTML invoice table with Original Price, Offers, and Quantities"""
    
    items_rows = ""
    for item in cart_items:
        offer_info = f"<br><small style='color: #d9534f;'>Discount: {item['discount_percent']}% OFF (Orig: PKR {item['original_price']:.2f})</small>" if item['discount_percent'] > 0 else ""
        
        items_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">
                <b>{item['name']}</b> {offer_info}
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">{item['qty']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">PKR {item['price']:.2f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">PKR {item['total']:.2f}</td>
        </tr>
        """
        
    header_title = "NEW ORDER RECEIVED!" if is_admin_copy else "Order Confirmation & Official Bill"
    header_bg = "#0d6efd" if is_admin_copy else "#198754"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 650px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: {header_bg}; color: white; padding: 15px; text-align: center;">
            <h2 style="margin: 0;">Ihsan Ul Haq & Sons General Store</h2>
            <p style="margin: 5px 0 0 0;">{header_title}</p>
        </div>
        
        <div style="padding: 20px;">
            <table style="width: 100%; margin-bottom: 15px; font-size: 14px;">
                <tr><td><b>Customer Name:</b> {username}</td><td style="text-align: right;"><b>Order ID:</b> #{order_id}</td></tr>
                <tr><td><b>Payment Method:</b> {payment_method}</td><td style="text-align: right;"><b>TRX ID:</b> {trx_id if trx_id else 'N/A'}</td></tr>
            </table>
            
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Item Details</th>
                        <th style="padding: 10px; text-align: center; border-bottom: 2px solid #ddd;">Qty</th>
                        <th style="padding: 10px; text-align: right; border-bottom: 2px solid #ddd;">Final Unit Price</th>
                        <th style="padding: 10px; text-align: right; border-bottom: 2px solid #ddd;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {items_rows}
                </tbody>
            </table>
            
            <div style="text-align: right; margin-top: 20px; font-size: 18px;">
                <p><b>Grand Total Payable: <span style="color: #198754;">PKR {grand_total:.2f}</span></b></p>
            </div>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="font-size: 12px; color: #777; text-align: center;">Ihsan Store - Quality Products Delivered with Trust.</p>
        </div>
    </div>
    """
    return html_content

@customer_bp.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    category_filter = request.args.get('category')
    banner_filter = request.args.get('banner_id')
    
    cursor.execute("SELECT * FROM banners ORDER BY id DESC")
    banners = cursor.fetchall()
    
    query = '''
        SELECT products.*, banners.discount_percentage 
        FROM products 
        LEFT JOIN banners ON products.banner_id = banners.id
    '''
    params = []
    
    if banner_filter:
        query += " WHERE products.banner_id = ? "
        params.append(banner_filter)
    elif category_filter:
        query += " WHERE products.category = ? "
        params.append(category_filter)
        
    query += " ORDER BY products.id DESC"
    cursor.execute(query, params)
    products_raw = cursor.fetchall()
    
    products = []
    for p in products_raw:
        item = dict(p)
        if item['discount_percentage'] and item['discount_percentage'] > 0:
            item['discounted_price'] = round(item['price'] * (1 - item['discount_percentage'] / 100), 2)
        else:
            item['discounted_price'] = None
        products.append(item)
    
    # Best Sellers
    cursor.execute('''
        SELECT products.*, banners.discount_percentage, SUM(order_items.quantity) as total_sold
        FROM order_items
        JOIN products ON order_items.product_id = products.id
        LEFT JOIN banners ON products.banner_id = banners.id
        GROUP BY products.id
        ORDER BY total_sold DESC
        LIMIT 4
    ''')
    best_sellers_raw = cursor.fetchall()
    best_sellers = []
    for p in best_sellers_raw:
        item = dict(p)
        if item['discount_percentage'] and item['discount_percentage'] > 0:
            item['discounted_price'] = round(item['price'] * (1 - item['discount_percentage'] / 100), 2)
        else:
            item['discounted_price'] = None
        best_sellers.append(item)

    # Recent Sales
    cursor.execute('''
        SELECT DISTINCT products.*, banners.discount_percentage, orders.id as order_id
        FROM order_items
        JOIN orders ON order_items.order_id = orders.id
        JOIN products ON order_items.product_id = products.id
        LEFT JOIN banners ON products.banner_id = banners.id
        ORDER BY orders.id DESC
        LIMIT 4
    ''')
    recent_sales_raw = cursor.fetchall()
    recent_sales = []
    for p in recent_sales_raw:
        item = dict(p)
        if item['discount_percentage'] and item['discount_percentage'] > 0:
            item['discounted_price'] = round(item['price'] * (1 - item['discount_percentage'] / 100), 2)
        else:
            item['discounted_price'] = None
        recent_sales.append(item)

    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
    categories = [r['category'] for r in cursor.fetchall()]
    
    conn.close()
    return render_template('index.html', products=products, categories=categories, banners=banners, best_sellers=best_sellers, recent_sales=recent_sales, selected_category=category_filter, selected_banner=banner_filter)

@customer_bp.route('/about')
def about():
    return render_template('about.html')

@customer_bp.route('/contact')
def contact():
    return render_template('contact.html')

@customer_bp.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    cart = session.get('cart', {})
    pid = str(product_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM products WHERE id = ?", (product_id,))
    product_exists = cursor.fetchone()
    conn.close()
    
    if not product_exists:
        flash('Maazrat, yeh product inventory mein available nahi hai.', 'error')
        return redirect(request.referrer or url_for('customer.home'))
        
    cart[pid] = cart.get(pid, 0) + 1
    session['cart'] = cart
    session.modified = True
    
    flash('Item trolley mein add ho gaya.', 'success')
    return redirect(request.referrer or url_for('customer.home'))

@customer_bp.route('/cart/adjust/<int:product_id>/<string:action>', methods=['POST'])
def adjust_cart(product_id, action):
    cart = session.get('cart', {})
    pid = str(product_id)
    
    if pid in cart:
        if action == 'increase':
            cart[pid] += 1
        elif action == 'decrease':
            cart[pid] -= 1
            if cart[pid] <= 0:
                cart.pop(pid)
        elif action == 'remove':
            cart.pop(pid, None)
                
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('customer.view_cart'))

@customer_bp.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cart_items = []
    grand_total = 0.0
    verified_cart_session = {}
    
    for pid, qty in list(cart.items()):
        cursor.execute('''
            SELECT products.*, banners.discount_percentage 
            FROM products 
            LEFT JOIN banners ON products.banner_id = banners.id 
            WHERE products.id = ?
        ''', (int(pid),))
        product = cursor.fetchone()
        
        if product:
            orig_price = round(product['price'], 2)
            disc_percent = product['discount_percentage'] if product['discount_percentage'] else 0
            
            final_price = orig_price * (1 - disc_percent / 100) if disc_percent > 0 else orig_price
            final_price = round(final_price, 2)
            subtotal = round(final_price * qty, 2)
            grand_total += subtotal
            
            cart_items.append({
                'id': product['id'],
                'name': product['name'],
                'original_price': orig_price,
                'discount_percent': disc_percent,
                'price': final_price,
                'qty': qty,
                'total': subtotal
            })
            verified_cart_session[pid] = qty
            
    session['cart'] = verified_cart_session
    session.modified = True
    conn.close()
    
    return render_template('cart.html', items=cart_items, total=round(grand_total, 2))

@customer_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Checkout karne ke liye pehle login karna zaroori hai.', 'warning')
        return redirect(url_for('auth.login'))
        
    cart = session.get('cart', {})
    if not cart:
        flash('Apki trolley khaali hai.', 'error')
        return redirect(url_for('customer.home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cart_items = []
    grand_total = 0.0
    
    for pid, qty in list(cart.items()):
        cursor.execute('''
            SELECT products.*, banners.discount_percentage 
            FROM products 
            LEFT JOIN banners ON products.banner_id = banners.id 
            WHERE products.id = ?
        ''', (int(pid),))
        prod = cursor.fetchone()
        if prod:
            orig_price = round(prod['price'], 2)
            disc_percent = prod['discount_percentage'] if prod['discount_percentage'] else 0
            
            final_price = orig_price * (1 - disc_percent / 100) if disc_percent > 0 else orig_price
            final_price = round(final_price, 2)
            subtotal = round(final_price * qty, 2)
            grand_total += subtotal
            
            cart_items.append({
                'id': prod['id'],
                'name': prod['name'],
                'original_price': orig_price,
                'discount_percent': disc_percent,
                'price': final_price,
                'qty': qty,
                'total': subtotal
            })
            
    grand_total = round(grand_total, 2)
            
    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        trx_id = request.form.get('transaction_id', '').strip()
        
        if payment_method in ['EasyPaisa', 'JazzCash'] and not trx_id:
            flash('Mobile account transaction ke liye valid TRX ID code likhna lazmi hai.', 'error')
            conn.close()
            return redirect(url_for('customer.checkout'))
            
        try:
            cursor.execute('''
                INSERT INTO orders (user_id, total_price, payment_method, transaction_id, status)
                VALUES (?, ?, ?, ?, 'Placed Order')
            ''', (session['user_id'], grand_total, payment_method, trx_id if trx_id else None))
            
            order_id = cursor.lastrowid
            
            for item in cart_items:
                cursor.execute('''
                    INSERT INTO order_items (order_id, product_id, quantity, price)
                    VALUES (?, ?, ?, ?)
                ''', (order_id, item['id'], item['qty'], item['price']))
                
                cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (item['qty'], item['id']))
                
            conn.commit()
            
            cursor.execute("SELECT username, email FROM users WHERE id = ?", (session['user_id'],))
            user_info = cursor.fetchone()
            
            if user_info:
                # 1. Send Bill to Customer
                cust_html = generate_invoice_html(user_info['username'], order_id, cart_items, grand_total, payment_method, trx_id, is_admin_copy=False)
                send_email_via_brevo(user_info['email'], f"Order Confirmation #{order_id} - Ihsan Store", cust_html)
                
                # 2. Send Alert to Admin
                admin_html = generate_invoice_html(user_info['username'], order_id, cart_items, grand_total, payment_method, trx_id, is_admin_copy=True)
                send_email_via_brevo(ADMIN_NOTIFICATION_EMAIL, f"ACTION REQUIRED: New Order #{order_id} Received from {user_info['username']}", admin_html)
            
            session.pop('cart', None)
            flash(f'Alhamdulillah! Apka order submit ho gaya hai. Bill email par bhej diya gaya hai. Order ID: #{order_id}', 'success')
            return redirect(url_for('customer.home'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Order placement error: {str(e)}', 'error')
        finally:
            conn.close()
            
    else:
        conn.close()
        
    return render_template('checkout.html', cart_items=cart_items, grand_total=grand_total)