# utils/email_helper.py
from flask_mail import Message

def send_status_email(mail_instance, recipient_email, username, order_id, total_price, status, items_list=None):
    subject = f"Order #{order_id} Update - Ihsan Ul Haq & Sons General Store"
    
    if status == 'Pending':
        subject = f"Order Confirmed! Receipt for Order #{order_id}"
        items_html = ""
        if items_list:
            for item in items_list:
                items_html += f"<tr><td style='padding:8px; border:1px solid #ddd;'>{item['name']}</td><td style='padding:8px; border:1px solid #ddd; text-align:center;'>{item['qty']}</td><td style='padding:8px; border:1px solid #ddd;'>PKR {item['price']}</td></tr>"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #198754; text-align: center;">Thank You for Your Order!</h2>
                    <p>Dear {username},</p>
                    <p>Your order has been successfully placed at <strong>Ihsan Ul Haq & Sons General Store</strong>.</p>
                    <h3 style="border-bottom: 2px solid #198754; padding-bottom: 5px;">Order Receipt (ID: #{order_id})</h3>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th style="padding: 8px; border: 1px solid #ddd;">Item</th>
                                <th style="padding: 8px; border: 1px solid #ddd;">Qty</th>
                                <th style="padding: 8px; border: 1px solid #ddd;">Price</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>
                    <h4 style="text-align: right; color: #198754; margin-top: 15px;">Grand Total: PKR {total_price}</h4>
                </div>
            </body>
        </html>
        """
        
    elif status == 'Dispatched':
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #fd7e14; text-align: center;">Your Order is Dispatched! 🚚</h2>
                    <p>Dear {username},</p>
                    <p>Great news! Your package for <strong>Order #{order_id}</strong> has left our bay and is on its way.</p>
                    <p>Please keep this email ready as a valid receipt at the time of delivery hand-off.</p>
                    <h4 style="color: #fd7e14;">Cash to Collect: PKR {total_price}</h4>
                </div>
            </body>
        </html>
        """
        
    elif status == 'Completed':
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #198754; text-align: center;">Order Delivered Successfully! ✅</h2>
                    <p>Dear {username},</p>
                    <p>Your <strong>Order #{order_id}</strong> has been successfully delivered. This serves as your official digital Proof of Delivery.</p>
                    <p><strong>Total Amount Settled:</strong> PKR {total_price}</p>
                </div>
            </body>
        </html>
        """
    else:
        return

    try:
        msg = Message(subject=subject, recipients=[recipient_email])
        msg.html = html_body
        mail_instance.send(msg)
        print(f"[MAIL SUCCESS] Notification triggered successfully to {recipient_email} for Order #{order_id}")
    except Exception as e:
        print(f"[MAIL ERROR] SMTP Connection Failed: {str(e)}")