# config.py
import os

class Config:
    # Sessions aur encryption secure rakhne k liay secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ihsan_super_secret_key_2026_pakistan'
    
    # SQLite Database file configurations
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE = os.path.join(BASE_DIR, 'database.db')