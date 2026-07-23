# set_admin.py
import sqlite3
from config import Config

def make_user_admin(email_address):
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    
    # Pehle check karte hain k kya yeh user database main exist karta hai
    cursor.execute("SELECT * FROM users WHERE email = ?", (email_address,))
    user = cursor.fetchone()
    
    if user:
        # Parameterized query se role permanently admin update kar rahe hain
        cursor.execute("UPDATE users SET role='admin' WHERE email=?", (email_address,))
        conn.commit()
        print(f"Success: {email_address} ko permanently Admin bana diya gaya hai!")
    else:
        print(f"Error: Email '{email_address}' database main nahi mili. Pehle website par ja kar is email se Sign Up/Register karein.")
        
    conn.close()

if __name__ == '__main__':
    # Aapki specific email ko lock kar diya hai
    make_user_admin('zakir.ullah0004@gmail.com')