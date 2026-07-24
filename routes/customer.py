import os
import sys
import base64
import io
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db_handler import get_db_connection

# PDF Generation Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

customer_bp = Blueprint('customer', __name__)

ADMIN_NOTIFICATION_EMAIL = "zakir.ullah0004@gmail.com"

def generate_pdf_invoice_bytes(order_id, full_name, username, phone, address, city, payment_method, trx_id, cart_items, grand_total):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#198754'), alignment=1)
    normal_style = styles['Normal']
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontName='Helvetica-Bold')
    
    story.append(Paragraph("Ihsan Ul Haq & Sons General Store", title_style))
    story.append(Paragraph("OFFICIAL ORDER INVOICE", ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=12, alignment=1)))
    story.append(Spacer(1, 15))
    
    info_data = [
        [Paragraph(f"<b>Order ID:</b> #{order_id}", normal_style), Paragraph(f"<b>Customer Name:</b> {full_name} ({username})", normal_style)],
        [Paragraph(f"<b>Phone:</b> {phone}", normal_style), Paragraph(f"<b>City:</b> {city}", normal_style)],
        [Paragraph(f"<b>Address:</b> {address}", normal_style), Paragraph(f"<b>Payment Method:</b> {payment_method}", normal_style)],
        [Paragraph(f"<b>TRX ID:</b> {trx_id if trx_id else 'N/A'}", normal_style), Paragraph(f"<b>Status:</b> Placed Order", normal_style)]
    ]
    info_table = Table(info_data, colWidths=[270, 270])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd'))
    ]))
    story.append(info_table)
    story.append(Spacer(1, 15))
    
    table_data = [["Product Name", "Qty", "Unit Price", "Total (PKR)"]]
    for item in cart_items:
        table_data.append([
            item['name'],
            str(item['qty']),
            f"PKR {item['price']:.2f}",
            f"PKR {item['total']:.2f}"
        ])
    table_data.append(["", "", "Grand Total:", f"PKR {grand_total:.2f}"])
    
    items_table = Table(table_data, colWidths=[240, 60, 120, 120])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#198754')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor('#dddddd')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (2,-1), (-1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (3,-1), (3,-1), colors.HexColor('#198754'))
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    note_text = "<b>Note:</b> Agar aapne Cash on Delivery (COD) select kiya hai to delivery rider ke liye cash ready rakhein. Shukriya!"
    story.append(Paragraph(note_text, normal_style))
    
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def send_email_via_brevo(to_email, subject, html_content, pdf_bytes=None, pdf_filename="Invoice.pdf"):
    api_key = os.environ.get('BREVO_API_KEY', '')
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
    
    if pdf_bytes:
        encoded_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        payload["attachment"] = [{
            "content": encoded_pdf,
            "name": pdf_filename
        }]
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"--> BREVO EMAIL ERROR: {str(e)}", file=sys.stderr)
        return False

def generate_placed_order_html(username, full_name, phone, address, city, order_id, cart_items, grand_total, payment_method, trx_id):
    items_rows = ""
    for item in cart_items:
        items_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;"><b>{item['name']}</b></td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{item['qty']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">PKR {item['price']:.2f}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">PKR {item['total']:.2f}</td>
        </tr>
        """
        
    cash_note = """
    <div style="background-color: #fff3cd; color: #856404; padding: 12px; border-radius: 5px; margin-top: 15px; border-left: 4px solid #ffeba2;">
        <strong>💵 Cash Notice:</strong> Aapne Cash on Delivery (COD) chuna hai. Meharbani karke delivery rider ke aane par baraye raast exact cash <b>PKR {:.2f}</b> ready rakhein.
    </div>
    """.format(grand_total) if payment_method == 'COD' else """
    <div style="background-color: #d1e7dd; color: #0f5132; padding: 12px; border-radius: 5px; margin-top: 15px; border-left: 4px solid #badbcc;">
        <strong>💳 Payment Received:</strong> Aapki online payment successfully receive ho gayi hai. Shukriya!
    </div>
    """

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 650px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: #198754; color: white; padding: 20px; text-align: center;">
            <h2 style="margin: 0;">Ihsan Ul Haq & Sons General Store</h2>
            <p style="margin: 5px 0 0 0; font-size: 16px;">🎉 Aapka Order Successfully Place Ho Gaya Hai!</p>
        </div>
        
        <div style="padding: 20px;">
            <p>Mohtaram <b>{full_name}</b> ({username}),</p>
            <p>Assalam-o-Alaikum! Ihsan Grocery Store se khareedari karne ka shukriya. Aapka <b>Order #{order_id}</b> hum tak pohoch gaya hai.</p>
            
            <div style="background-color: #e8f5e9; padding: 12px; border-radius: 5px; margin-bottom: 15px;">
                <b>🚀 Next Step Status:</b> Aapka order currently <b>Processing</b> mein hai. Hamari team items pack kar rahi hai aur yeh jald hi <b>Dispatched</b> status par shift ho jayega.
            </div>

            {cash_note}

            <h4 style="color: #198754; margin-top: 20px;">Order Bill Breakdown</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 8px; text-align: left;">Item</th>
                        <th style="padding: 8px; text-align: center;">Qty</th>
                        <th style="padding: 8px; text-align: right;">Price</th>
                        <th style="padding: 8px; text-align: right;">Total</th>
                    </tr>
                </thead>
                <tbody>{items_rows}</tbody>
            </table>
            
            <div style="text-align: right; margin-top: 15px; font-size: 16px;">
                <p><b>Grand Total: <span style="color: #198754;">PKR {grand_total:.2f}</span></b></p>
            </div>

            <p style="font-size: 13px; color: #555;"><i>Aapke official record ke liye is email ke sath PDF Bill Attachment bhej di gayi hai.</i></p>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="font-size: 12px; color: #777; text-align: center;">Ihsan Store - Always Fresh & Genuine Grocery Delivered.</p>
        </div>
    </div>
    """
    return html

def process_product_discount(products_raw):
    products = []
    for p in products_raw:
        item = dict(p)
        disc = item.get('discount_percentage')
        if disc and disc > 0:
            item['discounted_price'] = round(item['price'] * (1 - disc / 100), 2)
        else:
            item['discounted_price'] = None
        products.append(item)
    return products

@customer_bp.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    category_filter = request.args.get('category', '').strip()
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
    elif category_filter and category_filter != 'ALL':
        query += " WHERE TRIM(products.category) = ? "
        params.append(category_filter)
        
    query += " ORDER BY products.id DESC"
    cursor.execute(query, params)
    products = process_product_discount(cursor.fetchall())

    cursor.execute('''
        SELECT products.*, banners.discount_percentage, SUM(order_items.quantity) as total_sold
        FROM order_items
        JOIN products ON order_items.product_id = products.id
        LEFT JOIN banners ON products.banner_id = banners.id
        GROUP BY products.id
        ORDER BY total_sold DESC
        LIMIT 4
    ''')
    best_sellers = process_product_discount(cursor.fetchall())

    cursor.execute('''
        SELECT DISTINCT products.*, banners.discount_percentage
        FROM order_items
        JOIN products ON order_items.product_id = products.id
        LEFT JOIN banners ON products.banner_id = banners.id
        ORDER BY order_items.id DESC
        LIMIT 4
    ''')
    recent_sales = process_product_discount(cursor.fetchall())

    cursor.execute("SELECT DISTINCT TRIM(category) as category FROM products WHERE category IS NOT NULL AND TRIM(category) != ''")
    categories = [r['category'] for r in cursor.fetchall()]
    
    conn.close()
    return render_template(
        'index.html', 
        products=products, 
        best_sellers=best_sellers,
        recent_sales=recent_sales,
        categories=categories, 
        banners=banners, 
        selected_category=category_filter, 
        selected_banner=banner_filter
    )

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
                del cart[pid]
        elif action == 'remove':
            del cart[pid]
            
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
            final_price = round(orig_price * (1 - disc_percent / 100), 2) if disc_percent > 0 else orig_price
            subtotal = round(final_price * qty, 2)
            grand_total += subtotal
            
            cart_items.append({
                'id': product['id'],
                'name': product['name'],
                'image_url': product['image_url'],
                'original_price': orig_price,
                'discount_percent': disc_percent,
                'price': final_price,
                'qty': qty,
                'total': subtotal
            })
            
    conn.close()
    return render_template('cart.html', items=cart_items, total=round(grand_total, 2))

@customer_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Checkout karne ke liye pehle login karein.', 'warning')
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
            final_price = round(orig_price * (1 - disc_percent / 100), 2) if disc_percent > 0 else orig_price
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
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', 'Lahore').strip()
        payment_method = request.form.get('payment_method')
        trx_id = request.form.get('transaction_id', '').strip()
        
        if not full_name or not phone_number or not address:
            flash('Delivery Naam, Phone Number aur Address likhna lazmi hai.', 'error')
            conn.close()
            return redirect(url_for('customer.checkout'))

        try:
            cursor.execute('''
                INSERT INTO orders (user_id, full_name, phone_number, address, city, total_price, payment_method, transaction_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Placed Order')
            ''', (session['user_id'], full_name, phone_number, address, city, grand_total, payment_method, trx_id if trx_id else None))
            
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
                # 1. Generate PDF Invoice
                pdf_bytes = generate_pdf_invoice_bytes(order_id, full_name, user_info['username'], phone_number, address, city, payment_method, trx_id, cart_items, grand_total)
                
                # 2. Customer Placed Order Notification with PDF Attachment
                cust_html = generate_placed_order_html(user_info['username'], full_name, phone_number, address, city, order_id, cart_items, grand_total, payment_method, trx_id)
                send_email_via_brevo(user_info['email'], f"Order Placed Successfully #{order_id} - Ihsan Store", cust_html, pdf_bytes, f"Invoice_Order_{order_id}.pdf")
                
                # 3. Admin Alert Email
                admin_html = f"<h2>New Order #{order_id} Received!</h2><p>Customer: {full_name} ({phone_number})<br>Total Amount: PKR {grand_total:.2f}</p>"
                send_email_via_brevo(ADMIN_NOTIFICATION_EMAIL, f"NEW ORDER #{order_id} - Call {phone_number}", admin_html, pdf_bytes, f"Admin_Invoice_{order_id}.pdf")
            
            session.pop('cart', None)
            flash(f'Alhamdulillah! Apka order submit ho gaya hai. Order ID: #{order_id}', 'success')
            return redirect(url_for('customer.home'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Order placement error: {str(e)}', 'error')
        finally:
            conn.close()
            
    conn.close()
    return render_template('checkout.html', cart_items=cart_items, grand_total=grand_total)