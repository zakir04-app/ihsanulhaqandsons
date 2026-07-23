from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db_handler import get_db_connection

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    category_filter = request.args.get('category')
    
    # Banners Order
    cursor.execute("SELECT * FROM banners ORDER BY id DESC")
    banners = cursor.fetchall()
    
    if category_filter:
        cursor.execute("SELECT * FROM products WHERE category = ? ORDER BY id DESC", (category_filter,))
    else:
        cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
    categories = [r['category'] for r in cursor.fetchall()]
    
    cursor.execute("SELECT id, discount_percentage FROM banners")
    banner_discounts = {b['id']: b['discount_percentage'] for b in cursor.fetchall()}
    
    conn.close()
    return render_template('index.html', products=products, categories=categories, banners=banners, banner_discounts=banner_discounts, selected_category=category_filter)

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
                'price': price,
                'qty': qty,
                'total': subtotal
            })
            verified_cart_session[pid] = qty
            
    session['cart'] = verified_cart_session
    session.modified = True
    conn.close()
    
    return render_template('cart.html', items=cart_items, total=grand_total)

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
    
    grand_total = 0
    for pid, qty in list(cart.items()):
        cursor.execute('''
            SELECT products.price, banners.discount_percentage 
            FROM products 
            LEFT JOIN banners ON products.banner_id = banners.id 
            WHERE products.id = ?
        ''', (int(pid),))
        prod = cursor.fetchone()
        if prod:
            price = prod['price']
            if prod['discount_percentage']:
                price = price * (1 - prod['discount_percentage'] / 100)
            grand_total += (price * qty)
            
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
            
            for pid, qty in cart.items():
                cursor.execute('SELECT price FROM products WHERE id = ?', (int(pid),))
                item_fetched = cursor.fetchone()
                if item_fetched:
                    base_p = item_fetched['price']
                    cursor.execute('''
                        INSERT INTO order_items (order_id, product_id, quantity, price)
                        VALUES (?, ?, ?, ?)
                    ''', (order_id, int(pid), qty, base_p))
                    
                    cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (qty, int(pid)))
                
            conn.commit()
            session.pop('cart', None)
            flash(f'Alhamdulillah! Apka order successfully submit ho gaya hai. Order ID: #{order_id}', 'success')
            return redirect(url_for('customer.home'))
            
        except Exception as e:
            conn.rollback()
            print("--> INVOICE PROCESSING ERROR:", str(e))
            flash(f'Order placement ke dauran error aya: {str(e)}', 'error')
        finally:
            conn.close()
            
    else:
        conn.close()
        
    return render_template('checkout.html', grand_total=grand_total)