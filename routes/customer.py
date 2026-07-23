import os
import sys
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db_handler import get_db_connection

customer_bp = Blueprint('customer', __name__)

def send_invoice_email(recipient_email, username, order_id, cart_items, grand_total, payment_method, trx_id):
    """Sends Complete HTML Itemized Bill / Invoice to Customer via Brevo API"""
    api_key = os.environ.get('BREVO_API_KEY', 'FyExk7nvDBS4POHM')
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    # Build HTML Table Rows for Items
    items_rows = ""
    for item in cart_items:
        items_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{item['name']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">{item['qty']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">PKR {item['price']:.2f}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right; font-weight: bold;">PKR {item['total']:.2f}</td>
        </tr>
        """
        
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; padding: 20px; rounded-corner: 10px;">
        <h2 style="color: #198754; text-align: center;">Ihsan Ul Haq & Sons General Store</h2>
        <h4 style="text-align: center; color: #555;">Order Confirmation & Official Bill</h4>
        <hr>
        <p><b>Customer Name:</b> {username}</p>
        <p><b>Order ID:</b> #{order_id}</p>
        <p><b>Payment Gateway:</b> {payment_method} {f'(TRX: {trx_id})' if trx_id else ''}</p>
        
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 8px; text-align: left; border-bottom: 2px solid #ddd;">Item Description</th>
                    <th style="padding: 8px; text-align: center; border-bottom: 2px solid #ddd;">Qty</th>
                    <th style="padding: 8px; text-align: right; border-bottom: 2px solid #ddd;">Unit Price</th>
                    <th style="padding: 8px; text-align: right; border-bottom: 2px solid #ddd;">Subtotal</th>
                </tr>
            </thead>
            <tbody>
                {items_rows}
            </tbody>
        </table>
        
        <div style="text-align: right; margin-top: 20px; font-size: 18px;">
            <p><b>Grand Total Payable: <span style="color: #198754;">PKR {grand_total:.2f}</span></b></p>
        </div>
        <hr>
        <p style="font-size: 12px; color: #777; text-align: center;">Hum se khareedari karne ka shukriya!</p>
    </div>
    """
    
    payload = {
        "sender": {"name": "Ihsan Grocery Store", "email": "zakir.ullah0004@gmail.com"},
        "to": [{"email": recipient_email}],
        "subject": f"Official Invoice & Order Receipt #{order_id} - Ihsan Store",
        "htmlContent": html_content
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"--> INVOICE EMAIL EXCEPTION: {str(e)}", file=sys.stderr)
        return False

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
    grand_total = 0
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
            price = product['price']
            if product['discount_percentage']:
                price = price * (1 - product['discount_percentage'] / 100)
                
            subtotal = price * qty
            grand_total += subtotal
            
            cart_items.append({
                'id': product['id'],
                'name': product['name'],
                'price': round(price, 2),
                'qty': qty,
                'total': round(subtotal, 2)
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
            price = prod['price']
            if prod['discount_percentage']:
                price = price * (1 - prod['discount_percentage'] / 100)
            
            price = round(price, 2)
            subtotal = round(price * qty, 2)
            grand_total += subtotal
            
            cart_items.append({
                'id': prod['id'],
                'name': prod['name'],
                'price': price,
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
                VALUES (?, ?, ?, ?, 'Pending')
            ''', (session['user_id'], grand_total, payment_method, trx_id if trx_id else None))
            
            order_id = cursor.lastrowid
            
            for item in cart_items:
                cursor.execute('''
                    INSERT INTO order_items (order_id, product_id, quantity, price)
                    VALUES (?, ?, ?, ?)
                ''', (order_id, item['id'], item['qty'], item['price']))
                
                cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (item['qty'], item['id']))
                
            conn.commit()
            
            # Fetch User details for sending Email
            cursor.execute("SELECT username, email FROM users WHERE id = ?", (session['user_id'],))
            user_info = cursor.fetchone()
            
            if user_info:
                send_invoice_email(user_info['email'], user_info['username'], order_id, cart_items, grand_total, payment_method, trx_id)
            
            session.pop('cart', None)
            flash(f'Alhamdulillah! Apka order successfully submit ho gaya hai. Bill email par bhej diya gaya hai. Order ID: #{order_id}', 'success')
            return redirect(url_for('customer.home'))
            
        except Exception as e:
            conn.rollback()
            print("--> INVOICE PROCESSING ERROR:", str(e))
            flash(f'Order placement ke dauran error aya: {str(e)}', 'error')
        finally:
            conn.close()
            
    else:
        conn.close()
        
    return render_template('checkout.html', cart_items=cart_items, grand_total=grand_total)