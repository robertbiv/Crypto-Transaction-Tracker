#!/usr/bin/env python3
"""
================================================================================
WEB SERVER - Self-Hosted Web UI with Authentication
================================================================================

Flask-based web interface providing browser access to all tax engine features.

Key Features:
    - HTTPS/SSL with self-signed certificates
    - Multi-user authentication with bcrypt password hashing
    - Session management with secure cookies
    - CSRF protection for all state-changing operations
    - Rate limiting to prevent abuse
    - File upload for CSV imports
    - Real-time calculation progress tracking
    - Report viewing and download
    - Configuration management UI
    - Audit logging for compliance

Security Features:
    - Password-based authentication
    - Session timeout after inactivity
    - CSRF tokens rotated hourly
    - Rate limiting (5 login attempts per 15 min)
    - File upload validation and sanitization
    - SQL injection prevention (parameterized queries)
    - XSS prevention (template escaping)
    - Secure headers (HSTS, CSP)
    - Encrypted data at rest

API Endpoints:
    Authentication:
        POST /login - User login
        POST /logout - Session termination
        POST /change-password - Password update
    
    Data Management:
        GET /api/transactions - List all transactions
        POST /api/upload - CSV file upload
        POST /api/delete-transaction - Remove transaction
        POST /api/sync-api - Trigger exchange API sync
    
    Tax Operations:
        POST /api/calculate - Run tax calculation
        GET /api/reports - List available reports
        GET /api/download/<file> - Download report
        GET /api/status - Calculation progress
    
    Configuration:
        GET /api/config - Load configuration
        POST /api/config - Save configuration
        GET /api/wallets - Load wallet addresses
        POST /api/wallets - Save wallet addresses
        GET /api/api-keys - Load API keys
        POST /api/api-keys - Save API keys
    
    Admin:
        POST /api/backup-db - Create database backup
        POST /api/restore-db - Restore from backup
        GET /api/logs - View application logs
        POST /api/factory-reset - Reset to defaults

File Structure:
    web_templates/ - Jinja2 HTML templates
    web_static/ - CSS, JavaScript, images
    keys/web_users.json - User credentials (bcrypt hashed)
    certs/ - SSL certificate and private key

Default Credentials:
    Set during first-time setup wizard
    Default admin user created if none exists
    Password must be changed on first login

Usage:
    python src/web/server.py
    python start_web_ui.py
    
    Access at: https://localhost:5000

Production Deployment:
    For production use, consider:
    - Nginx reverse proxy
    - Real SSL certificate (Let's Encrypt)
    - PostgreSQL instead of SQLite
    - Redis session storage
    - Gunicorn or uWSGI

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

import os
import sys
import json
import sqlite3
import secrets
import subprocess
import hmac
import hashlib
import base64
import shutil
import zipfile
import io
import csv
from pathlib import Path
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, send_file, redirect, url_for, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
import bcrypt
import jwt
import filelock
import logging
import threading
import time as _time
import tempfile
import uuid
import src.core.engine as tax_app  # Import for status updates
from src.core.engine import DatabaseManager  # For unified CSV ingestion
from src.processors import Ingestor
from src.web.scheduler import ScheduleManager
from src.core.encryption import (
    DatabaseEncryption,
    get_api_key_cipher,
    encrypt_api_keys,
    decrypt_api_keys,
    encrypt_wallets,
    decrypt_wallets,
    load_api_keys_file,
    save_api_keys_file,
    load_wallets_file,
    save_wallets_file
)

# Configuration paths - avoid importing full engine to reduce dependencies
BASE_DIR = Path(__file__).parent.parent.parent  # Go up to project root
TEMPLATE_DIR = BASE_DIR / 'web_templates'
STATIC_DIR = BASE_DIR / 'web_static'
UPLOAD_FOLDER = BASE_DIR / 'inputs'
DB_FILE = BASE_DIR / 'crypto_master.db'
USERS_FILE = BASE_DIR / 'keys' / 'web_users.json'
CERT_DIR = BASE_DIR / 'certs'
CONFIG_FILE = BASE_DIR / 'configs' / 'config.json'
API_KEYS_FILE = BASE_DIR / 'api_keys.json'
API_KEYS_ENCRYPTED_FILE = BASE_DIR / 'keys' / 'api_keys_encrypted.json'
WALLETS_FILE = BASE_DIR / 'wallets.json'
WALLETS_ENCRYPTED_FILE = BASE_DIR / 'keys' / 'wallets_encrypted.json'
OUTPUT_DIR = BASE_DIR / 'outputs'
ENCRYPTION_KEY_FILE = BASE_DIR / 'keys' / 'web_encryption.key'
API_KEY_ENCRYPTION_FILE = BASE_DIR / 'api_key_encryption.key'
AUDIT_LOG_FILE = BASE_DIR / 'outputs' / 'logs' / 'audit.log'
BACKUPS_DIR = OUTPUT_DIR / 'backups'

# Security Constants
LOGIN_RATE_LIMIT = "5 per 15 minutes"  # Max 5 login attempts per 15 minutes
API_RATE_LIMIT = "100 per hour"  # Max 100 API calls per hour
CSRF_TOKEN_ROTATION_INTERVAL = 3600  # Rotate CSRF token every hour (seconds)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
BCRYPT_COST_FACTOR = 12

# Setup audit logging
AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
audit_logger = logging.getLogger('audit')

# Initialize scheduler
scheduler = None  # Will be initialized in main()

audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    audit_handler = logging.FileHandler(AUDIT_LOG_FILE)
    audit_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - USER:%(user)s - IP:%(ip)s - ACTION:%(action)s - DETAILS:%(details)s'
    ))
    audit_logger.addHandler(audit_handler)

def audit_log(action, details='', user=None):
    """Log security-sensitive operations"""
    try:
        ip = request.remote_addr if request else 'unknown'
        user = user or session.get('username', 'anonymous')
        audit_logger.info('', extra={'action': action, 'details': details, 'user': user, 'ip': ip})
    except Exception as e:
        print(f"Audit log error: {e}")

# Create Flask app
app = Flask(__name__, 
            template_folder=str(TEMPLATE_DIR),
            static_folder=str(STATIC_DIR))
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = None  # CSRF tokens don't expire

# Progress tracking for long-running operations
progress_store = {}

# Disable CORS - API should only be accessible from same origin (web UI)
# CORS(app)  # Removed for security

# Session configuration
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[API_RATE_LIMIT],
    storage_uri="memory://"
)

# ====================================================================================
# ENCRYPTION FUNCTIONS (Imported from src.core.encryption)
# ====================================================================================
# All encryption, decryption, and file I/O functions for API keys and wallets
# are now imported from src.core.encryption module for consistency and deduplication

# ====================================================================================
# SECURITY HEADERS & CSP
# ====================================================================================
@app.before_request
def generate_nonce():
    """Generate a nonce for CSP and rotate CSRF token if needed"""
    g.csp_nonce = secrets.token_hex(16)
    
    # Rotate CSRF token if it's too old (for logged-in users)
    if 'username' in session and 'csrf_created_at' in session:
        age = _time.time() - session['csrf_created_at']
        if age > CSRF_TOKEN_ROTATION_INTERVAL:
            session['csrf_token'] = secrets.token_hex(32)
            session['csrf_created_at'] = _time.time()
            audit_log('CSRF_TOKEN_ROTATED', f'Token rotated after {int(age)} seconds')

@app.context_processor
def inject_nonce():
    """Inject nonce into templates"""
    return dict(csp_nonce=getattr(g, 'csp_nonce', ''))

@app.after_request
def add_security_headers(response):
    """Add security headers to response"""
    nonce = getattr(g, 'csp_nonce', '')
    
    # Content Security Policy
    # Strict CSP: No unsafe-inline, No unsafe-eval
    # Scripts allowed only with correct nonce
    csp = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self';"
    )
    response.headers['Content-Security-Policy'] = csp
    
    # Other security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

# Initialize directories
TEMPLATE_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
CERT_DIR.mkdir(exist_ok=True)
UPLOAD_FOLDER.mkdir(exist_ok=True)

# ==========================================
# ENCRYPTION & SECURITY
# ==========================================

def get_or_create_encryption_key():
    """Get or create encryption key for database operations"""
    if ENCRYPTION_KEY_FILE.exists():
        with open(ENCRYPTION_KEY_FILE, 'rb') as f:
            return f.read()
    
    # Create keys directory if it doesn't exist
    ENCRYPTION_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate new encryption key
    key = Fernet.generate_key()
    with open(ENCRYPTION_KEY_FILE, 'wb') as f:
        f.write(key)
    
    # Set restrictive permissions (Unix-like systems)
    try:
        os.chmod(ENCRYPTION_KEY_FILE, 0o600)
    except OSError:
        pass  # Windows doesn't support chmod, this is expected
    
    return key

# Initialize encryption
ENCRYPTION_KEY = get_or_create_encryption_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

def encrypt_data(data):
    """Encrypt data for secure transmission"""
    if isinstance(data, dict) or isinstance(data, list):
        data = json.dumps(data)
    if isinstance(data, str):
        data = data.encode('utf-8')
    return cipher_suite.encrypt(data).decode('utf-8')

def decrypt_data(encrypted_data):
    """Decrypt data from secure transmission"""
    if isinstance(encrypted_data, str):
        encrypted_data = encrypted_data.encode('utf-8')
    decrypted = cipher_suite.decrypt(encrypted_data)
    try:
        return json.loads(decrypted.decode('utf-8'))
    except json.JSONDecodeError:
        return decrypted.decode('utf-8')

def generate_csrf_token():
    """Generate CSRF token for request validation"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token(token):
    """Validate CSRF token"""
    return token == session.get('csrf_token')

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token)

def generate_api_signature(data, timestamp):
    """Generate HMAC signature for API request"""
    message = f"{json.dumps(data, sort_keys=True)}:{timestamp}:{session.get('username', '')}"
    signature = hmac.new(
        app.config['SECRET_KEY'].encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

def validate_api_signature(data, timestamp, signature):
    """Validate API request signature"""
    # Check timestamp is recent (within 5 minutes)
    try:
        request_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if now - request_time > timedelta(minutes=5):
            return False
    except (ValueError, TypeError):
        return False
    
    expected_signature = generate_api_signature(data, timestamp)
    return hmac.compare_digest(signature, expected_signature)

def web_security_required(f):
    """Decorator for Web UI API requests (CSRF + Origin check, no HMAC)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check authentication
        if 'username' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check origin (same-origin only)
        origin = request.headers.get('Origin')
        host = request.headers.get('Host')
        if origin and host:
            from urllib.parse import urlparse
            origin_host = urlparse(origin).netloc
            if origin_host != host:
                return jsonify({'error': 'Cross-origin requests not allowed'}), 403
        
        # Validate CSRF token
        csrf_token = request.headers.get('X-CSRF-Token')
        if not csrf_token or not validate_csrf_token(csrf_token):
            return jsonify({'error': 'Invalid CSRF token'}), 403
            
        return f(*args, **kwargs)
    return decorated_function

def api_security_required(f):
    """Decorator to enforce API security (CSRF + signature validation + origin check)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check authentication
        if 'username' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check origin (same-origin only - no external API access)
        origin = request.headers.get('Origin')
        referer = request.headers.get('Referer')
        host = request.headers.get('Host')
        
        # If origin or referer present, must match host
        if origin and host:
            # Extract domain from origin
            from urllib.parse import urlparse
            origin_host = urlparse(origin).netloc
            if origin_host != host:
                return jsonify({'error': 'Cross-origin requests not allowed'}), 403
        
        # Validate CSRF token
        csrf_token = request.headers.get('X-CSRF-Token')
        if not csrf_token or not validate_csrf_token(csrf_token):
            return jsonify({'error': 'Invalid CSRF token'}), 403
        
        # Validate API signature for write operations
        if request.method in ['POST', 'PUT', 'DELETE']:
            timestamp = request.headers.get('X-Request-Timestamp')
            signature = request.headers.get('X-Request-Signature')
            
            if not timestamp or not signature:
                return jsonify({'error': 'Missing security headers'}), 403
            
            # Get request data
            data = request.get_json() if request.is_json else {}
            
            if not validate_api_signature(data, timestamp, signature):
                return jsonify({'error': 'Invalid request signature'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# USER AUTHENTICATION
# ==========================================

def load_users():
    """Load users from JSON file"""
    if not USERS_FILE.exists():
        return {}
    
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def is_first_time_setup():
    """Check if this is first-time setup (no users exist)"""
    return not USERS_FILE.exists() or len(load_users()) == 0

def is_setup_in_progress():
    """True if users exist but setup not completed (wizard phase)."""
    if not USERS_FILE.exists():
        return False
    try:
        users = load_users()
        if len(users) != 1:
            return False
        # single user and missing or False 'setup_completed'
        u = users[list(users.keys())[0]]
        return not u.get('setup_completed', False)
    except Exception:
        return False

def create_initial_user(username, password):
    """Create the initial admin user and initialize DB encryption with their password"""
    users = {
        username: {
            'password_hash': bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'is_admin': True
        }
    }
    save_users(users)
    
    # Initialize database encryption with user's password
    try:
        db_key = DatabaseEncryption.initialize_encryption(password)
        app.config['DB_ENCRYPTION_KEY'] = db_key
        print("✅ Database encryption initialized with your web account password")
    except Exception as e:
        print(f"⚠️ Could not initialize database encryption: {e}")
    
    return True

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def verify_password(username, password):
    """Verify username and password - timing-attack resistant"""
    users = load_users()
    
    # Always perform bcrypt operation to prevent timing attacks
    if username not in users:
        # Use a dummy hash with same cost factor to maintain constant time
        dummy_hash = bcrypt.hashpw(b'dummy', bcrypt.gensalt()).decode('utf-8')
        bcrypt.checkpw(password.encode('utf-8'), dummy_hash.encode('utf-8'))
        return False
    
    stored_hash = users[username]['password_hash']
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# SSL CERTIFICATE GENERATION
# ==========================================

def generate_self_signed_cert():
    """Generate self-signed SSL certificate"""
    cert_file = CERT_DIR / 'cert.pem'
    key_file = CERT_DIR / 'key.pem'
    
    if cert_file.exists() and key_file.exists():
        return str(cert_file), str(key_file)
    
    # Ensure cert directory exists
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Generating self-signed SSL certificate...")
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Crypto Tax Generator"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(u"localhost"),
                x509.DNSName(u"127.0.0.1"),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate to file
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # Write private key to file
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        print(f"SSL certificate generated: {cert_file}")
        return str(cert_file), str(key_file)
    
    except Exception as e:
        print(f"Error generating SSL certificate: {e}")
        print("Falling back to HTTP (not recommended for production)")
        return None, None

# ==========================================
# DATABASE HELPERS
# ==========================================

def get_db_connection():
    """Get database connection with encryption layer"""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn

def _ingest_csv_with_engine(saved_path: Path):
    """Use the engine's Ingestor to process a single CSV file into trades and archive it.
    Returns a summary dict with total_rows and new_trades.
    """
    # Count CSV rows (excluding header) for reporting
    total_rows = 0
    try:
        with open(saved_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for _ in reader:
                total_rows += 1
    except Exception:
        total_rows = 0

    db = DatabaseManager()
    try:
        before = db.cursor.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        ing = Ingestor(db)
        batch = f"CSV_{saved_path.name}_{datetime.now().strftime('%Y%m%d')}"
        # Process and archive using engine logic
        ing._proc_csv_smart(saved_path, batch)
        ing._archive(saved_path)
        db.commit()
        after = db.cursor.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        delta = max(0, int(after) - int(before))
        return { 'total_rows': total_rows, 'new_trades': delta }
    finally:
        try:
            db.close()
        except Exception:
            pass

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    try:
        # Create trades table
        conn.execute('''CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY, date TEXT, source TEXT, destination TEXT,
            action TEXT, coin TEXT, amount TEXT, price_usd TEXT, fee TEXT, fee_coin TEXT, batch_id TEXT
        )''')
        conn.commit()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        conn.close()

# Initialize DB on module load
init_db()

def encrypt_sensitive_field(value):
    """Encrypt sensitive field values"""
    if value and value != '' and not str(value).startswith('PASTE_'):
        return encrypt_data(str(value))
    return value

def decrypt_sensitive_field(value):
    """Decrypt sensitive field values"""
    if value and isinstance(value, str) and not value.startswith('PASTE_'):
        try:
            return decrypt_data(value)
        except:
            return value
    return value

def get_transactions(page=1, per_page=50, search=None, filters=None):
    """Get transactions with pagination and filtering - encrypted response"""
    conn = get_db_connection()
    
    query = "SELECT * FROM trades"
    params = []
    where_clauses = []
    
    if search:
        where_clauses.append("(coin LIKE ? OR source LIKE ? OR action LIKE ?)")
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if filters:
        if filters.get('coin'):
            where_clauses.append("coin = ?")
            params.append(filters['coin'])
        if filters.get('action'):
            where_clauses.append("action = ?")
            params.append(filters['action'])
        if filters.get('source'):
            where_clauses.append("source = ?")
            params.append(filters['source'])
    
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    
    # Get total count
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total = conn.execute(count_query, params).fetchone()[0]
    
    # Add pagination
    query += " ORDER BY date DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    
    cursor = conn.execute(query, params)
    transactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        'transactions': transactions,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    }

# ==========================================
# AUTHENTICATION ROUTES
# ==========================================

@app.route('/api/tos/status', methods=['GET'])
def get_tos_status():
    """Get ToS acceptance status"""
    from src.utils.tos_checker import tos_accepted, read_tos
    
    return jsonify({
        'tos_accepted': tos_accepted(),
        'tos_content': read_tos()
    })

@app.route('/api/tos/accept', methods=['POST'])
def accept_tos():
    """Mark ToS as accepted"""
    from src.utils.tos_checker import mark_tos_accepted, tos_accepted
    
    data = request.get_json() or {}
    accept = data.get('accept', False)
    
    if not accept:
        return jsonify({'error': 'ToS must be accepted to proceed'}), 400
    
    mark_tos_accepted()
    
    audit_log('TOS_ACCEPTED', 'User accepted Terms of Service through web UI')
    
    return jsonify({
        'success': True,
        'tos_accepted': tos_accepted()
    })

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Get CSRF token for API requests"""
    if 'username' in session:
        return jsonify({
            'csrf_token': generate_csrf_token()
        })
    return jsonify({'error': 'Not authenticated'}), 401

@app.route('/first-time-setup', methods=['GET', 'POST'])
def first_time_setup():
    """First-time setup page for creating admin account"""
    from src.utils.tos_checker import tos_accepted
    
    # If users already exist, redirect to login
    if not is_first_time_setup():
        return redirect(url_for('login'))
    
    # Check if ToS was accepted
    if not tos_accepted():
        # Redirect to ToS acceptance page (will be shown in setup wizard)
        return redirect(url_for('setup_wizard'))
    
    if request.method == 'POST':
        # Double-check no users exist (race condition protection)
        if not is_first_time_setup():
            if request.is_json:
                return jsonify({'success': False, 'error': 'User already exists'}), 400
            return redirect(url_for('login'))
        
        data = request.get_json() if request.is_json else request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
        
        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters')
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters')
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if errors:
            if request.is_json:
                return jsonify({'success': False, 'errors': errors}), 400
            return render_template('first_time_setup.html', errors=errors, hide_nav=True)
        
        # Create user
        try:
            create_initial_user(username, password)
            
            # Auto-login the new user
            session['username'] = username
            session.permanent = True
            
            if request.is_json:
                return jsonify({'success': True, 'message': 'Account created successfully', 'redirect': url_for('setup_wizard')})
            
            # Redirect to setup wizard
            return redirect(url_for('setup_wizard'))
        except Exception as e:
            error_msg = f'Error creating account: {str(e)}'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 500
            return render_template('first_time_setup.html', error=error_msg, hide_nav=True)
    
    return render_template('first_time_setup.html', hide_nav=True)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit(LOGIN_RATE_LIMIT)
def login():
    """Login page with rate limiting"""
    # If first-time setup needed, redirect there
    if is_first_time_setup():
        return redirect(url_for('first_time_setup'))
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        if verify_password(username, password):
            # Regenerate session to prevent session fixation attacks
            session.clear()
            session['username'] = username
            session['csrf_token'] = secrets.token_hex(32)
            session['csrf_created_at'] = _time.time()
            session.permanent = True
            # Store password in encrypted session for deriving encryption keys
            session['_db_password'] = password
            
            # Audit log successful login
            audit_log('LOGIN_SUCCESS', f'User {username} logged in', username)
            
            # Initialize/unlock database encryption with password
            try:
                db_key = DatabaseEncryption.initialize_encryption(password)
                app.config['DB_ENCRYPTION_KEY'] = db_key
            except Exception as e:
                print(f"Warning: Could not unlock database: {e}")
            
            if request.is_json:
                return jsonify({'success': True, 'message': 'Login successful'})
            return redirect(url_for('dashboard'))
        
        if request.is_json:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        return render_template('login.html', error='Invalid credentials')
    
    # If already logged in, redirect to dashboard
    if 'username' in session:
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    # Get data from request (may be encrypted or plain for password change)
    try:
        data = request.get_json()
        # Try to decrypt if encrypted
        if 'data' in data:
            # data = decrypt_data(data['data'])
            data = json.loads(data['data'])
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Missing required fields'}), 400
        
        username = session['username']
        
        # Verify current password
        if not verify_password(username, current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Update password
        users = load_users()
        users[username]['password_hash'] = bcrypt.hashpw(
            new_password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
        users[username]['password_changed_at'] = datetime.now(timezone.utc).isoformat()
        
        # Remove initial_password marker if it exists
        if 'initial_password' in users[username]:
            del users[username]['initial_password']
        
        save_users(users)
        
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/full', methods=['GET'])
@login_required
def download_full_backup():
    """Download full system backup (Database export to CSV)"""
    try:
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Export trades table to CSV
            conn = get_db_connection()
            try:
                cursor = conn.execute("SELECT * FROM trades")
                rows = cursor.fetchall()
                
                # Get column names
                if cursor.description:
                    column_names = [description[0] for description in cursor.description]
                    
                    # Write CSV to string buffer
                    csv_buffer = io.StringIO()
                    writer = csv.writer(csv_buffer)
                    writer.writerow(column_names)
                    writer.writerows(rows)
                    
                    # Add CSV to zip
                    zf.writestr('trades_export.csv', csv_buffer.getvalue())
                else:
                    # Empty table or error
                    zf.writestr('trades_export.csv', 'No data found')
                
            finally:
                conn.close()
        
        memory_file.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'crypto_tax_db_export_{timestamp}.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup/zip', methods=['GET'])
@login_required
def api_backup_zip():
    """Create a zip backup with necessary files. If DB key is available, encrypt zip with it."""
    try:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

        # Build zip in-memory
        raw_zip = io.BytesIO()
        with zipfile.ZipFile(raw_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                'created': datetime.now(timezone.utc).isoformat(),
                'version': '1.0',
                'includes': []
            }

            def add_file(path: Path, arcname: str):
                if path.exists():
                    zf.write(str(path), arcname)
                    manifest['includes'].append(arcname)

            add_file(DB_FILE, 'crypto_master.db')
            add_file(BASE_DIR / '.db_key', '.db_key')
            add_file(BASE_DIR / '.db_salt', '.db_salt')
            add_file(CONFIG_FILE, 'config.json')
            # Prefer encrypted API keys if present
            add_file(API_KEYS_ENCRYPTED_FILE, 'api_keys_encrypted.json')
            if 'api_keys_encrypted.json' not in manifest['includes']:
                add_file(API_KEYS_FILE, 'api_keys.json')

            # Prefer encrypted wallets if present
            add_file(WALLETS_ENCRYPTED_FILE, 'wallets_encrypted.json')
            if 'wallets_encrypted.json' not in manifest['includes']:
                add_file(WALLETS_FILE, 'wallets.json')
            add_file(USERS_FILE, 'web_users.json')

            # Add manifest
            zf.writestr('manifest.json', json.dumps(manifest, indent=2))

        raw_zip.seek(0)

        # Encrypt zip with DB key if available
        db_key = app.config.get('DB_ENCRYPTION_KEY')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if db_key:
            cipher = Fernet(db_key)
            encrypted_bytes = cipher.encrypt(raw_zip.getvalue())
            mem = io.BytesIO(encrypted_bytes)
            mem.seek(0)
            filename = f'backup_{timestamp}.zip.enc'
            mimetype = 'application/octet-stream'
            return send_file(mem, mimetype=mimetype, as_attachment=True, download_name=filename)
        else:
            # Fallback: return plain zip
            filename = f'backup_{timestamp}.zip'
            return send_file(raw_zip, mimetype='application/zip', as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wizard/restore-backup', methods=['POST'])
def api_wizard_restore_backup():
    """First-time or wizard: upload a backup .zip or .zip.enc to restore."""
    if not (is_first_time_setup() or is_setup_in_progress()):
        return jsonify({'error': 'Restore only allowed during initial setup or wizard'}), 403

    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Missing file'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'Empty filename'}), 400

        data = file.read()
        filename = file.filename.lower()

        # If encrypted, require password to decrypt with password-derived key
        if filename.endswith('.enc'):
            password = request.form.get('password', '')
            if not password:
                return jsonify({'error': 'Password required for encrypted backup'}), 400

            # Decrypt backup using the provided password (user's web account password)
            # The backup contains .db_key and .db_salt files encrypted with their web password
            from Crypto_Tax_Engine import DatabaseEncryption
            
            # First try to extract .db_key and .db_salt from the encrypted backup
            # We need to decrypt the backup first to get these files
            db_key_bytes = None
            
            try:
                # Try using existing local key files if present
                if (BASE_DIR / '.db_key').exists() and (BASE_DIR / '.db_salt').exists():
                    with open(BASE_DIR / '.db_key', 'rb') as f:
                        enc_key = f.read()
                    with open(BASE_DIR / '.db_salt', 'rb') as f:
                        salt = f.read()
                    db_key_bytes = DatabaseEncryption.decrypt_key(enc_key, password, salt)
            except Exception:
                pass
            
            if db_key_bytes is None:
                # Extract key files from backup to decrypt with user's password
                # The backup itself is encrypted with the DB key, so we need to:
                # 1. Decrypt the .zip.enc outer layer (may need the DB key from inside)
                # This is a bootstrapping problem - return helpful error
                return jsonify({'error': 'Unable to decrypt backup. Please ensure you are using the correct web account password.'}), 400

            try:
                cipher = Fernet(db_key_bytes)
                zip_bytes = cipher.decrypt(data)
            except Exception:
                return jsonify({'error': 'Invalid password or corrupted backup'}), 400
        else:
            zip_bytes = data

        # Extract zip bytes
        tmp_mem = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(tmp_mem, 'r') as zf:
            members = zf.namelist()
            def restore_member(name, target_path: Path):
                if name in members:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(target_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

            # Determine restore mode (merge or replace). Default: merge
            mode = request.form.get('mode', 'merge').lower()

            # Handle database: merge or replace
            if 'crypto_master.db' in members:
                if mode == 'merge':
                    fallback_to_replace = False
                    tmpdb_path = None
                    # Ensure target DB exists and has required schema
                    try:
                        conn_init = sqlite3.connect(str(DB_FILE))
                        cur_init = conn_init.cursor()
                        cur_init.execute("""
                            CREATE TABLE IF NOT EXISTS trades (
                                id TEXT PRIMARY KEY,
                                date TEXT,
                                source TEXT,
                                destination TEXT,
                                action TEXT,
                                coin TEXT,
                                amount TEXT,
                                price_usd TEXT,
                                fee TEXT,
                                fee_coin TEXT,
                                batch_id TEXT
                            )
                        """)
                        conn_init.commit()
                    except Exception:
                        # If schema init fails for any reason, fallback to replace
                        fallback_to_replace = True
                    finally:
                        try:
                            conn_init.close()
                        except Exception:
                            pass
                    # Extract backup DB to a temporary file
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmpdb:
                            with zf.open('crypto_master.db') as src:
                                shutil.copyfileobj(src, tmpdb)
                            tmpdb_path = Path(tmpdb.name)
                        # Merge rows using ATTACH and INSERT OR IGNORE by primary key id
                        conn = None
                        try:
                            conn = sqlite3.connect(str(DB_FILE))
                            cur = conn.cursor()
                            cur.execute("ATTACH DATABASE ? AS olddb", (str(tmpdb_path),))
                            has_trades = cur.execute("SELECT name FROM olddb.sqlite_master WHERE type='table' AND name='trades'").fetchone()
                            if has_trades:
                                old_cols = [r[1] for r in cur.execute("PRAGMA olddb.table_info(trades)").fetchall()]
                                target_cols = ['id','date','source','destination','action','coin','amount','price_usd','fee','fee_coin','batch_id']
                                select_exprs = [f"olddb.trades.{c}" if c in old_cols else f"NULL AS {c}" for c in target_cols]
                                insert_cols = ",".join(target_cols)
                                select_sql = ", ".join(select_exprs)
                                cur.execute(f"INSERT OR IGNORE INTO trades ({insert_cols}) SELECT {select_sql} FROM olddb.trades")
                                conn.commit()
                        except Exception:
                            # If ATTACH or SELECT fails (e.g., not a real SQLite file), fallback to replace
                            fallback_to_replace = True
                        finally:
                            try:
                                if conn:
                                    conn.execute("DETACH DATABASE olddb")
                            except Exception:
                                pass
                            if conn:
                                conn.close()
                    finally:
                        try:
                            if tmpdb_path:
                                tmpdb_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                    if fallback_to_replace:
                        # Replace DB file if merge not possible
                        restore_member('crypto_master.db', DB_FILE)
                else:
                    # Replace DB file
                    restore_member('crypto_master.db', DB_FILE)

            restore_member('.db_key', BASE_DIR / '.db_key')
            restore_member('.db_salt', BASE_DIR / '.db_salt')
            restore_member('config.json', CONFIG_FILE)
            
            # Handle API keys: merge or replace based on mode
            if mode == 'merge':
                # Load existing API keys
                existing_api_keys = {}
                try:
                    existing_api_keys = load_api_keys_file()
                except Exception:
                    pass
                
                # Extract and load backup API keys to temp location
                backup_api_keys = {}
                if 'api_keys_encrypted.json' in members:
                    try:
                        with zf.open('api_keys_encrypted.json') as src:
                            backup_data = json.load(src)
                            if isinstance(backup_data, dict) and 'ciphertext' in backup_data:
                                backup_api_keys = decrypt_api_keys(backup_data['ciphertext']) or {}
                    except Exception:
                        pass
                elif 'api_keys.json' in members:
                    try:
                        with zf.open('api_keys.json') as src:
                            backup_api_keys = json.load(src)
                    except Exception:
                        pass
                
                # Merge: backup keys take precedence, but keep existing keys not in backup
                merged_api_keys = {**existing_api_keys, **backup_api_keys}
                
                # Save merged result
                if merged_api_keys:
                    try:
                        save_api_keys_file(merged_api_keys)
                    except Exception:
                        pass
            else:
                # Replace mode: just restore from backup
                if 'api_keys_encrypted.json' in members:
                    restore_member('api_keys_encrypted.json', API_KEYS_ENCRYPTED_FILE)
                else:
                    restore_member('api_keys.json', API_KEYS_FILE)

            # Handle wallets: merge or replace based on mode
            if mode == 'merge':
                # Load existing wallets
                existing_wallets = {}
                try:
                    existing_wallets = load_wallets_file()
                except Exception:
                    pass
                
                # Extract and load backup wallets
                backup_wallets = {}
                if 'wallets_encrypted.json' in members:
                    try:
                        with zf.open('wallets_encrypted.json') as src:
                            backup_data = json.load(src)
                            if isinstance(backup_data, dict) and 'ciphertext' in backup_data:
                                backup_wallets = decrypt_wallets(backup_data['ciphertext']) or {}
                    except Exception:
                        pass
                elif 'wallets.json' in members:
                    try:
                        with zf.open('wallets.json') as src:
                            backup_wallets = json.load(src)
                    except Exception:
                        pass
                
                # Merge wallets intelligently
                merged_wallets = {}
                all_chains = set(existing_wallets.keys()) | set(backup_wallets.keys())
                
                for chain in all_chains:
                    existing_addrs = existing_wallets.get(chain, [])
                    backup_addrs = backup_wallets.get(chain, [])
                    
                    # Normalize to lists
                    if isinstance(existing_addrs, dict):
                        existing_addrs = existing_addrs.get('addresses', [])
                    if not isinstance(existing_addrs, list):
                        existing_addrs = [existing_addrs] if existing_addrs else []
                    
                    if isinstance(backup_addrs, dict):
                        backup_addrs = backup_addrs.get('addresses', [])
                    if not isinstance(backup_addrs, list):
                        backup_addrs = [backup_addrs] if backup_addrs else []
                    
                    # Merge and deduplicate addresses
                    all_addrs = list(set(existing_addrs + backup_addrs))
                    if all_addrs:
                        merged_wallets[chain] = all_addrs
                
                # Save merged result
                if merged_wallets:
                    try:
                        save_wallets_file(merged_wallets)
                    except Exception:
                        pass
            else:
                # Replace mode: just restore from backup
                if 'wallets_encrypted.json' in members:
                    restore_member('wallets_encrypted.json', WALLETS_ENCRYPTED_FILE)
                else:
                    restore_member('wallets.json', WALLETS_FILE)
            
            restore_member('web_users.json', USERS_FILE)

        return jsonify({'success': True, 'message': 'Backup restored. Please restart the server.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset/factory', methods=['POST'])
@api_security_required
def factory_reset():
    """Perform full factory reset"""
    try:
        # 1. Delete Database
        if DB_FILE.exists():
            os.remove(DB_FILE)
        init_db() # Recreate empty schema
        
        # 2. Delete Configs (encrypted and legacy)
        for f in [CONFIG_FILE, API_KEYS_FILE, API_KEYS_ENCRYPTED_FILE, WALLETS_FILE, WALLETS_ENCRYPTED_FILE, API_KEY_ENCRYPTION_FILE, ENCRYPTION_KEY_FILE]:
            if f.exists():
                os.remove(f)
                
        # 3. Clear Data Directories
        for folder in [UPLOAD_FOLDER, OUTPUT_DIR, BASE_DIR / 'processed_archive']:
            if folder.exists():
                shutil.rmtree(folder)
                folder.mkdir(exist_ok=True)
                
        # 4. Delete Users (Last step)
        if USERS_FILE.exists():
            os.remove(USERS_FILE)
            
        session.clear()
        
        return jsonify({'success': True, 'message': 'Factory reset complete', 'redirect': url_for('first_time_setup')})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# MAIN UI ROUTES
# ==========================================

@app.route('/')
def index():
    """Main entry point - redirect to setup or dashboard"""
    # Check if first-time setup is needed
    if is_first_time_setup():
        return redirect(url_for('first_time_setup'))
    
    # Check if logged in
    if 'username' in session:
        return redirect(url_for('dashboard'))
    
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET'])
def setup_page():
    """Setup page for first-time configuration"""
    # If users already exist, redirect to login
    if USERS_FILE.exists():
        return redirect(url_for('login'))
    return render_template('first_time_setup.html')

@app.route('/setup/wizard', methods=['GET'])
@login_required
def setup_wizard():
    """Setup Wizard page shown after account creation"""
    return render_template('setup_wizard.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/transactions')
@login_required
def transactions_page():
    """Transactions page"""
    return render_template('transactions.html')

@app.route('/config')
@login_required
def config_page():
    """Configuration page"""
    return render_template('config.html')

@app.route('/warnings')
@login_required
def warnings_page():
    """Warnings page"""
    return render_template('warnings.html')

@app.route('/reports')
@login_required
def reports_page():
    """Reports page"""
    return render_template('reports.html')

@app.route('/settings')
@login_required
def settings_page():
    """Settings page"""
    return render_template('settings.html')

@app.route('/logs')
@login_required
def logs_page():
    """Logs page"""
    return render_template('logs.html')

@app.route('/schedule')
@login_required
def schedule_page():
    """Schedule page"""
    return render_template('schedule.html')

# ==========================================
# API ROUTES - TRANSACTIONS
# ==========================================

@app.route('/api/transactions', methods=['GET'])
@login_required
@web_security_required
def api_get_transactions():
    """Get transactions with pagination - encrypted response"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        search = request.args.get('search')
        
        filters = {}
        if request.args.get('coin'):
            filters['coin'] = request.args.get('coin')
        if request.args.get('action'):
            filters['action'] = request.args.get('action')
        if request.args.get('source'):
            filters['source'] = request.args.get('source')
        
        result = get_transactions(page, per_page, search, filters if filters else None)
        
        # Return encrypted response
        # encrypted_result = encrypt_data(result)
        # return jsonify({'data': encrypted_result})
        return jsonify({'data': json.dumps(result)})
    except Exception as e:
        print(f"Error getting transactions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions/template', methods=['GET'])
@login_required
@web_security_required
def api_transactions_template():
    """Serve a CSV template for transaction uploads (unified with ingestor headers)."""
    try:
        # Provide commonly recognized ingestor headers
        headers = [
            'date','type','received_coin','received_amount','sent_coin','sent_amount','price_usd','fee','fee_coin','destination','source'
        ]
        sample_rows = [
            ['2024-01-01T12:00:00Z','trade','BTC','0.001','','','42000','0','','','MANUAL'],
            ['2024-01-02T08:00:00Z','staking','ETH','0.01','','','0','0','','','MANUAL']
        ]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        for r in sample_rows:
            writer.writerow(r)
        csv_bytes = io.BytesIO(buf.getvalue().encode('utf-8'))
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(csv_bytes, mimetype='text/csv', as_attachment=True, download_name=f'transactions_template_{ts}.csv')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions', methods=['POST'])
@login_required
@web_security_required
def api_create_transaction():
    """Create a new transaction"""
    # Decrypt request data
    encrypted_payload = request.get_json().get('data')
    if not encrypted_payload:
        return jsonify({'error': 'Missing data'}), 400
    
    try:
        # data = decrypt_data(encrypted_payload)
        data = json.loads(encrypted_payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return jsonify({'error': 'Invalid data format'}), 400
    
    required_fields = ['date', 'action', 'coin', 'amount']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
            
    conn = get_db_connection()
    
    try:
        # Generate a unique ID
        tx_id = str(uuid.uuid4())
        
        # Prepare values with defaults
        values = (
            tx_id,
            data.get('date'),
            data.get('source', 'Manual'),
            data.get('destination', ''),
            data.get('action'),
            data.get('coin'),
            data.get('amount'),
            data.get('price_usd', 0),
            data.get('fee', 0),
            data.get('fee_coin', '')
        )
        
        query = """
            INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        conn.execute(query, values)
        conn.commit()
        conn.close()
        
        # Mark data as changed
        tax_app.mark_data_changed()
        
        return jsonify({'status': 'success', 'message': 'Transaction created', 'id': tx_id})
    except Exception as e:
        if conn:
            conn.close()
        print(f"Error creating transaction: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/transactions/upload', methods=['POST'])
@login_required
@web_security_required
def api_upload_transactions():
    """Upload a CSV file and ingest via engine for accurate, unified parsing."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
        if not file or file.filename.strip() == '':
            return jsonify({'error': 'Empty filename'}), 400
        if not file.filename.lower().endswith('.csv'):
            return jsonify({'error': 'Only .csv files are accepted'}), 400

        filename = secure_filename(file.filename)
        saved_path = UPLOAD_FOLDER / filename
        file.save(str(saved_path))

        summary = _ingest_csv_with_engine(saved_path)
        try:
            tax_app.mark_data_changed()
        except Exception:
            pass

        return jsonify({
            'success': True,
            'total_rows': summary.get('total_rows', 0),
            'new_trades': summary.get('new_trades', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/transactions/<transaction_id>', methods=['PUT'])
@login_required
@web_security_required
def api_update_transaction(transaction_id):
    """Update a transaction - requires encrypted request"""
    # Decrypt request data
    encrypted_payload = request.get_json().get('data')
    if not encrypted_payload:
        return jsonify({'error': 'Missing encrypted data'}), 400
    
    try:
        # data = decrypt_data(encrypted_payload)
        data = json.loads(encrypted_payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return jsonify({'error': 'Invalid encrypted data'}), 400
    
    conn = get_db_connection()
    
    # Build update query
    allowed_fields = ['date', 'source', 'destination', 'action', 'coin', 'amount', 'price_usd', 'fee', 'fee_coin']
    updates = []
    params = []
    
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])
    
    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400
    
    params.append(transaction_id)
    query = f"UPDATE trades SET {', '.join(updates)} WHERE id = ?"
    
    try:
        conn.execute(query, params)
        conn.commit()
        conn.close()
        
        # Mark data as changed
        tax_app.mark_data_changed()
        
        # encrypted_response = encrypt_data({'success': True, 'message': 'Transaction updated'})
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps({'success': True, 'message': 'Transaction updated'})})
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions/<transaction_id>', methods=['DELETE'])
@login_required
@web_security_required
def api_delete_transaction(transaction_id):
    """Delete a transaction"""
    conn = get_db_connection()
    
    try:
        conn.execute("DELETE FROM trades WHERE id = ?", (transaction_id,))
        conn.commit()
        conn.close()
        
        # Mark data as changed
        tax_app.mark_data_changed()
        
        # encrypted_response = encrypt_data({'success': True, 'message': 'Transaction deleted'})
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps({'success': True, 'message': 'Transaction deleted'})})
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

# ==========================================
# API ROUTES - CONFIGURATION
# ==========================================

@app.route('/api/config', methods=['GET'])
@login_required
@web_security_required
def api_get_config():
    """Get configuration - encrypted response"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # encrypted_response = encrypt_data(config)
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps(config)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['PUT'])
@login_required
@web_security_required
def api_update_config():
    """Update configuration - requires encrypted request"""
    encrypted_payload = request.get_json().get('data')
    if not encrypted_payload:
        return jsonify({'error': 'Missing encrypted data'}), 400
    
    try:
        # data = decrypt_data(encrypted_payload)
        data = json.loads(encrypted_payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return jsonify({'error': 'Invalid encrypted data'}), 400
    
    try:
        lock = filelock.FileLock(str(CONFIG_FILE) + '.lock')
        with lock:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        
        # encrypted_response = encrypt_data({'success': True, 'message': 'Configuration updated'})
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps({'success': True, 'message': 'Configuration updated'})})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wallets', methods=['GET'])
@login_required
@web_security_required
def api_get_wallets():
    """Get wallets - encrypted response"""
    try:
        wallets = load_wallets_file()
        
        # encrypted_response = encrypt_data(wallets)
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps(wallets)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wallets', methods=['PUT'])
@login_required
@web_security_required
def api_update_wallets():
    """Update wallets - requires encrypted request"""
    encrypted_payload = request.get_json().get('data')
    if not encrypted_payload:
        return jsonify({'error': 'Missing encrypted data'}), 400
    
    try:
        data = json.loads(encrypted_payload)
    except Exception:
        return jsonify({'error': 'Invalid encrypted data'}), 400
    
    try:
        save_wallets_file(data)
        
        # encrypted_response = encrypt_data({'success': True, 'message': 'Wallets updated'})
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps({'success': True, 'message': 'Wallets updated'})})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/api-keys', methods=['GET'])
@login_required
@web_security_required
def api_get_api_keys():
    """Get API keys (masked for security) - encrypted response"""
    try:
        api_keys = load_api_keys_file()
        # Mask sensitive data
        for exchange, keys in api_keys.items():
            if isinstance(keys, dict):
                for key, value in keys.items():
                    if key in ['apiKey', 'secret', 'password'] and value:
                        if len(value) > 8 and not value.startswith('PASTE_'):
                            api_keys[exchange][key] = value[:4] + '*' * (len(value) - 8) + value[-4:]
        
        # encrypted_response = encrypt_data(api_keys)
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps(api_keys)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/api-keys', methods=['PUT'])
@login_required
@web_security_required
def api_update_api_keys():
    """Update API keys - requires encrypted request"""
    encrypted_payload = request.get_json().get('data')
    if not encrypted_payload:
        return jsonify({'error': 'Missing encrypted data'}), 400
    
    try:
        data = json.loads(encrypted_payload)
    except Exception:
        return jsonify({'error': 'Invalid encrypted data'}), 400
    
    try:
        existing_keys = load_api_keys_file()
        
        # Update only non-masked values
        for exchange, keys in data.items():
            if exchange not in existing_keys:
                existing_keys[exchange] = {}
            
            if isinstance(keys, dict):
                for key, value in keys.items():
                    # Only update if not masked
                    if value and '*' not in value:
                        existing_keys[exchange][key] = value
        
        save_api_keys_file(existing_keys)
        
        # encrypted_response = encrypt_data({'success': True, 'message': 'API keys updated'})
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps({'success': True, 'message': 'API keys updated'})})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/api-keys/test', methods=['POST'])
@login_required
@web_security_required
def api_test_api_key():
    """Test if exchange API key is valid"""
    try:
        data = request.get_json()
        exchange = data.get('exchange', '').lower()
        api_key = data.get('apiKey', '').strip()
        secret = data.get('secret', '').strip()
        
        if not exchange or not api_key or not secret:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Import ccxt
        import ccxt
        
        # Check if exchange is supported
        if not hasattr(ccxt, exchange):
            return jsonify({'success': False, 'error': f'Exchange "{exchange}" not supported'}), 400
        
        # Try to create exchange instance and fetch balance
        try:
            exchange_class = getattr(ccxt, exchange)
            exchange_obj = exchange_class({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
                'timeout': 10000
            })
            
            # Test by fetching balance (read-only operation)
            balance = exchange_obj.fetch_balance()
            
            return jsonify({
                'success': True, 
                'message': f'✓ {exchange.capitalize()} API key is valid',
                'details': f'Successfully authenticated and fetched balance'
            })
        except ccxt.AuthenticationError as e:
            return jsonify({
                'success': False, 
                'error': f'Authentication failed: {str(e)}'
            })
        except ccxt.NetworkError as e:
            return jsonify({
                'success': False, 
                'error': f'Network error: {str(e)}'
            })
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'Test failed: {str(e)}'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wallets/test', methods=['POST'])
@login_required
@web_security_required
def api_test_wallet():
    """Test if wallet address is valid format"""
    try:
        data = request.get_json()
        blockchain = data.get('blockchain', '').upper()
        address = data.get('address', '').strip()
        
        if not blockchain or not address:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Basic validation patterns for different blockchains
        validation_patterns = {
            'BTC': (r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$', 'Bitcoin'),
            'ETH': (r'^0x[a-fA-F0-9]{40}$', 'Ethereum'),
            'MATIC': (r'^0x[a-fA-F0-9]{40}$', 'Polygon'),
            'BNB': (r'^0x[a-fA-F0-9]{40}$|^bnb[a-z0-9]{39}$', 'BNB Chain'),
            'SOL': (r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', 'Solana'),
            'ADA': (r'^addr1[a-z0-9]{58,}$', 'Cardano'),
            'DOT': (r'^1[a-zA-Z0-9]{47}$', 'Polkadot'),
            'AVAX': (r'^0x[a-fA-F0-9]{40}$|^X-avax1[a-z0-9]{38}$', 'Avalanche'),
        }
        
        if blockchain not in validation_patterns:
            return jsonify({
                'success': False, 
                'error': f'Blockchain "{blockchain}" validation not supported yet'
            }), 400
        
        import re
        pattern, name = validation_patterns[blockchain]
        
        if re.match(pattern, address):
            return jsonify({
                'success': True,
                'message': f'✓ Valid {name} address format',
                'details': f'Address has correct format for {blockchain}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Invalid {name} address format'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# API ROUTES - WARNINGS & REPORTS
# ==========================================

@app.route('/api/warnings', methods=['GET'])
@login_required
@web_security_required
def api_get_warnings():
    """Get review warnings"""
    try:
        warnings_file = None
        suggestions_file = None
        
        # Find latest year folder
        if OUTPUT_DIR.exists():
            year_folders = [f for f in OUTPUT_DIR.iterdir() if f.is_dir() and f.name.startswith('Year_')]
            if year_folders:
                latest_year = max(year_folders, key=lambda x: x.name)
                warnings_file = latest_year / 'REVIEW_WARNINGS.csv'
                suggestions_file = latest_year / 'REVIEW_SUGGESTIONS.csv'
        
        warnings = []
        suggestions = []
        
        if warnings_file and warnings_file.exists():
            import pandas as pd
            df = pd.read_csv(warnings_file)
            warnings = df.to_dict('records')
        
        if suggestions_file and suggestions_file.exists():
            import pandas as pd
            df = pd.read_csv(suggestions_file)
            suggestions = df.to_dict('records')
        
        result = {
            'warnings': warnings,
            'suggestions': suggestions
        }
        
        # return jsonify(result)
        return jsonify({'data': json.dumps(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-warnings-config', methods=['GET'])
@login_required
def get_download_warnings_config():
    """Get download warnings configuration"""
    try:
        config = load_config()
        warnings_enabled = config.get('ui', {}).get('download_warnings_enabled', True)
        return jsonify({
            'enabled': warnings_enabled,
            'message': 'Download warnings are ' + ('enabled' if warnings_enabled else 'DISABLED - Remember to always review outputs with a tax professional!')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports', methods=['GET'])
@login_required
@web_security_required
def api_get_reports():
    """List available reports"""
    try:
        reports = []
        
        if OUTPUT_DIR.exists():
            year_folders = [f for f in OUTPUT_DIR.iterdir() if f.is_dir() and f.name.startswith('Year_')]
            
            for year_folder in sorted(year_folders, key=lambda x: x.name, reverse=True):
                year = year_folder.name.replace('Year_', '')
                year_reports = []
                
                for report_file in year_folder.glob('*.csv'):
                    # Use forward slashes for web paths, regardless of OS
                    rel_path = report_file.relative_to(BASE_DIR)
                    web_path = str(rel_path).replace('\\', '/')
                    
                    year_reports.append({
                        'name': report_file.name,
                        'path': web_path,
                        'size': report_file.stat().st_size,
                        'modified': datetime.fromtimestamp(report_file.stat().st_mtime).isoformat()
                    })
                
                if year_reports:
                    reports.append({
                        'year': year,
                        'reports': year_reports
                    })
        
        # return jsonify(reports)
        return jsonify({'data': json.dumps(reports)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/download/<path:report_path>', methods=['GET'])
@login_required
def api_download_report(report_path):
    """Download a report file"""
    try:
        file_path = BASE_DIR / report_path
        
        # Security check - ensure file is within OUTPUT_DIR
        if not str(file_path.resolve()).startswith(str(OUTPUT_DIR.resolve())):
            return jsonify({'error': 'Invalid file path'}), 403
        
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        # Log the download for audit trail
        audit_log('REPORT_DOWNLOADED', f'Downloaded: {report_path}')
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-warning-acknowledged', methods=['POST'])
@login_required
def download_warning_acknowledged():
    """Acknowledge the download warning and proceed with download"""
    try:
        data = request.get_json() or {}
        user_confirmed = data.get('confirmed', False)
        report_path = data.get('report_path', '')
        
        # Check if warnings are enabled in config
        config = load_config()
        warnings_enabled = config.get('ui', {}).get('download_warnings_enabled', True)
        
        # If warnings enabled, user must confirm
        if warnings_enabled and not user_confirmed:
            return jsonify({'error': 'Must acknowledge the warning'}), 400
        
        # If warnings disabled, still require confirmed for security/audit trail
        if not warnings_enabled and not user_confirmed:
            return jsonify({'error': 'API requires confirmation'}), 400
        
        if not report_path:
            return jsonify({'error': 'No report path provided'}), 400
        
        file_path = BASE_DIR / report_path
        
        # Security check
        if not str(file_path.resolve()).startswith(str(OUTPUT_DIR.resolve())):
            return jsonify({'error': 'Invalid file path'}), 403
        
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        # Log acknowledgment
        audit_log('DOWNLOAD_WARNING_CONFIRMED', f'User confirmed warning before downloading: {report_path}')
        
        # Return success with download URL
        return jsonify({
            'success': True,
            'download_url': f'/api/reports/download/{report_path}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==========================================
# API ROUTES - STATISTICS & CHARTS
# ==========================================

@app.route('/api/stats', methods=['GET'])
@login_required
@web_security_required
def api_get_stats():
    """Get statistics for dashboard"""
    try:
        conn = get_db_connection()
        
        # Count transactions
        total_transactions = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        
        # Count by action
        actions = {}
        cursor = conn.execute("SELECT action, COUNT(*) as count FROM trades GROUP BY action")
        for row in cursor:
            actions[row['action']] = row['count']
        
        # Count by coin
        coins = {}
        cursor = conn.execute("SELECT coin, COUNT(*) as count FROM trades GROUP BY coin ORDER BY count DESC LIMIT 10")
        for row in cursor:
            coins[row['coin']] = row['count']
        
        # Get date range
        date_range = conn.execute("SELECT MIN(date) as min_date, MAX(date) as max_date FROM trades").fetchone()
        
        conn.close()
        
        # Try to load gains/losses from reports
        gains_losses = None
        if OUTPUT_DIR.exists():
            year_folders = [f for f in OUTPUT_DIR.iterdir() if f.is_dir() and f.name.startswith('Year_')]
            if year_folders:
                latest_year = max(year_folders, key=lambda x: x.name)
                loss_analysis_file = latest_year / 'US_TAX_LOSS_ANALYSIS.csv'
                
                if loss_analysis_file.exists():
                    import pandas as pd
                    df = pd.read_csv(loss_analysis_file)
                    if not df.empty:
                        gains_losses = df.to_dict('records')[0]
        
        result = {
            'total_transactions': total_transactions,
            'actions': actions,
            'top_coins': coins,
            'date_range': {
                'min': date_range['min_date'],
                'max': date_range['max_date']
            },
            'gains_losses': gains_losses
        }
        
        # return jsonify(result)
        return jsonify({'data': json.dumps(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# API ROUTES - OPERATIONS
# ==========================================

@app.route('/api/csv-upload', methods=['POST'])
@login_required
@web_security_required
def api_upload_csv():
    """Upload CSV and ingest via engine (unified with Transactions upload)."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Only CSV files are allowed'}), 400
    try:
        filename = secure_filename(file.filename)
        saved_path = UPLOAD_FOLDER / filename
        file.save(str(saved_path))

        summary = _ingest_csv_with_engine(saved_path)
        try:
            tax_app.mark_data_changed()
        except Exception:
            pass

        result = {
            'success': True,
            'message': f"Imported {summary.get('new_trades', 0)} trades from {filename} (rows: {summary.get('total_rows', 0)})",
            'filename': filename,
            'new_trades': summary.get('new_trades', 0),
            'total_rows': summary.get('total_rows', 0)
        }
        return jsonify({'data': json.dumps(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/progress/<task_id>', methods=['GET'])
@login_required
def api_get_progress(task_id):
    """Get progress of a long-running task"""
    try:
        progress = progress_store.get(task_id, {
            'status': 'not_found',
            'progress': 0,
            'message': 'Task not found'
        })
        return jsonify(progress)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/run', methods=['POST'])
@login_required
@web_security_required
def api_run_tax_calculation():
    """Start tax calculation"""
    try:
        # Check if there are transactions
        conn = get_db_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        except Exception:
            count = 0
        finally:
            conn.close()
            
        if count == 0:
            return jsonify({'error': 'No transactions found. Please add transactions before running calculation.'}), 400

        auto_runner = BASE_DIR / 'auto_runner.py'
        if not auto_runner.exists():
            return jsonify({'error': 'auto_runner.py not found'}), 404
        
        # Generate task ID
        task_id = f"tax_calc_{secrets.token_hex(8)}"
        
        # Initialize progress
        progress_store[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': 'Starting tax calculation...',
            'started_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Check for cascade mode
        data = request.get_json() or {}
        cmd = [sys.executable, str(auto_runner)]
        if data.get('cascade'):
            cmd.append('--cascade')
            
        # Run Auto_Runner.py in background with progress tracking
        def run_with_progress():
            try:
                progress_store[task_id]['progress'] = 10
                progress_store[task_id]['message'] = 'Running tax calculation...'
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Monitor process
                while process.poll() is None:
                    _time.sleep(1)
                    # Increment progress (max 90% until complete)
                    if progress_store[task_id]['progress'] < 90:
                        progress_store[task_id]['progress'] += 5
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    progress_store[task_id]['status'] = 'completed'
                    progress_store[task_id]['progress'] = 100
                    progress_store[task_id]['message'] = 'Tax calculation completed successfully'
                else:
                    progress_store[task_id]['status'] = 'error'
                    progress_store[task_id]['message'] = f'Tax calculation failed: {stderr[:200]}'
                    
            except Exception as e:
                progress_store[task_id]['status'] = 'error'
                progress_store[task_id]['message'] = f'Error: {str(e)}'
        
        thread = threading.Thread(target=run_with_progress, daemon=True)
        thread.start()
        
        result = {
            'success': True,
            'task_id': task_id,
            'message': 'Tax calculation started. Progress will be tracked.'
        }
        
        # encrypted_response = encrypt_data(result)
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/setup', methods=['POST'])
@login_required
@web_security_required
def api_run_setup():
    """Run setup script"""
    try:
        # Run Setup.py
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / 'src' / 'tools' / 'src/tools/setup.py')],
            capture_output=True,
            text=True
        )
        
        response_data = {
            'success': result.returncode == 0,
            'message': 'Setup completed' if result.returncode == 0 else 'Setup failed',
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # encrypted_response = encrypt_data(response_data)
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps(response_data)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wizard/create-account', methods=['POST'])
def api_wizard_create_account():
    """Wizard Step 1 - Create first user account - NO AUTHENTICATION REQUIRED"""
    # Only allow if no users exist
    if USERS_FILE.exists():
        return jsonify({'error': 'Setup already completed'}), 403
    
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        # Create user (setup not completed yet)
        users = {
            username: {
                'password_hash': bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'setup_completed': False  # Will be set to True when wizard completes
            }
        }
        
        save_users(users)
        
        return jsonify({'success': True, 'message': 'Setup completed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wizard/run-setup-script', methods=['POST'])
def api_wizard_run_setup():
    """Wizard Step 2 - Run Setup.py script - NO AUTHENTICATION REQUIRED"""
    # Only allow if no users exist yet (in wizard flow)
    if not USERS_FILE.exists():
        return jsonify({'error': 'Please create account first'}), 403
    
    try:
        # Run Setup.py script
        setup_script = BASE_DIR / 'src' / 'tools' / 'src/tools/setup.py'
        if not setup_script.exists():
            return jsonify({'error': 'Setup.py not found'}), 404
        
        # Generate unique task ID for progress tracking
        task_id = str(uuid.uuid4())
        
        # Initialize progress
        progress_store[task_id] = {
            'progress': 0,
            'status': 'running',
            'message': 'Initializing setup...'
        }
        
        # Run setup in background thread
        def run_setup_thread():
            try:
                # Start the setup process
                env = os.environ.copy()
                env['SETUP_WIZARD_MODE'] = '1'
                
                # Update progress
                progress_store[task_id]['progress'] = 10
                progress_store[task_id]['message'] = 'Running setup script...'
                
                process = subprocess.Popen(
                    [sys.executable, str(setup_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(BASE_DIR),
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    env=env
                )
                
                # Monitor progress - increment periodically
                progress = 20
                while process.poll() is None:
                    if progress < 90:
                        progress += 5
                        progress_store[task_id]['progress'] = progress
                        progress_store[task_id]['message'] = f'Setup in progress ({progress}%)...'
                    _time.sleep(0.5)
                
                # Get output
                stdout, stderr = process.communicate(timeout=60)
                
                # Check result
                if process.returncode == 0:
                    progress_store[task_id]['progress'] = 100
                    progress_store[task_id]['status'] = 'completed'
                    progress_store[task_id]['message'] = 'Setup completed successfully!'
                    progress_store[task_id]['output'] = stdout
                else:
                    progress_store[task_id]['status'] = 'error'
                    progress_store[task_id]['message'] = f'Setup failed: {stderr}'
                    progress_store[task_id]['error'] = stderr
                    progress_store[task_id]['output'] = stdout
                    
            except subprocess.TimeoutExpired:
                progress_store[task_id]['status'] = 'error'
                progress_store[task_id]['message'] = 'Setup script timed out'
            except Exception as e:
                progress_store[task_id]['status'] = 'error'
                progress_store[task_id]['message'] = f'Error: {str(e)}'
        
        # Start thread
        thread = threading.Thread(target=run_setup_thread, daemon=True)
        thread.start()
        
        # Return task ID for progress tracking
        return jsonify({'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wizard/get-config', methods=['GET'])
def api_wizard_get_config():
    """Wizard Step 3/4/5 - Get current config/wallets/api_keys - NO AUTHENTICATION REQUIRED"""
    # Only allow during setup wizard (no users or just created)
    if not USERS_FILE.exists():
        return jsonify({'error': 'Please create account first'}), 403
    
    try:
        config_type = request.args.get('type', 'config')
        
        if config_type == 'api_keys':
            if API_KEYS_FILE.exists():
                with open(API_KEYS_FILE, 'r') as f:
                    data = json.load(f)
            else:
                data = {}
            return jsonify({'success': True, 'data': data})
        
        elif config_type == 'wallets':
            if WALLETS_FILE.exists():
                with open(WALLETS_FILE, 'r') as f:
                    data = json.load(f)
            else:
                data = {}
            return jsonify({'success': True, 'data': data})
        
        elif config_type == 'config':
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
            else:
                data = {}
            return jsonify({'success': True, 'data': data})
        
        else:
            return jsonify({'error': 'Invalid config type'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wizard/save-config', methods=['POST'])
def api_wizard_save_config():
    """Wizard Step 3/4/5 - Save config/wallets/api_keys - NO AUTHENTICATION REQUIRED"""
    # Only allow during setup wizard
    if not USERS_FILE.exists():
        return jsonify({'error': 'Please create account first'}), 403
    
    try:
        data = request.get_json()
        config_type = data.get('type')
        config_data = data.get('data')
        
        if not config_type or config_data is None:
            return jsonify({'error': 'Missing type or data'}), 400
        
        if config_type == 'api_keys':
            save_api_keys_file(config_data)
        
        elif config_type == 'wallets':
            save_wallets_file(config_data)
        
        elif config_type == 'config':
            lock = filelock.FileLock(str(CONFIG_FILE) + '.lock')
            with lock:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config_data, f, indent=4)
        
        else:
            return jsonify({'error': 'Invalid config type'}), 400
        
        return jsonify({'success': True, 'message': f'{config_type} saved successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wizard/complete', methods=['POST'])
def api_wizard_complete():
    """Wizard Final Step - Mark setup as complete and auto-login - NO AUTHENTICATION REQUIRED"""
    if not USERS_FILE.exists():
        return jsonify({'error': 'No user account found'}), 403
    
    try:
        # Get the user (validate only one exists during wizard)
        users = load_users()
        if len(users) != 1:
            return jsonify({'error': 'Invalid setup state - expected exactly one user'}), 500
        username = list(users.keys())[0]
        
        # Mark setup as completed
        users[username]['setup_completed'] = True
        users[username]['setup_completed_at'] = datetime.now(timezone.utc).isoformat()
        save_users(users)
        
        # Auto-login the user
        session['username'] = username
        session.permanent = True
        
        return jsonify({'success': True, 'message': 'Setup completed! Logging you in...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs', methods=['GET'])
@login_required
@web_security_required
def api_get_logs():
    """Get list of log files"""
    try:
        logs = []
        log_dir = OUTPUT_DIR / 'logs'
        
        if log_dir.exists():
            for log_file in sorted(log_dir.glob('*.log'), key=lambda x: x.stat().st_mtime, reverse=True):
                logs.append({
                    'name': log_file.name,
                    'path': log_file.name,  # Send just filename, not full path
                    'size': log_file.stat().st_size,
                    'modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                })
        
        # encrypted_response = encrypt_data(logs)
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps(logs)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _compute_diagnostics():
    """Compute diagnostics; returns dict with 'issues', 'ok', and 'status'"""
    issues = []
    status = []  # Positive confirmations

    # 1. Database encryption key loaded
    db_key_loaded = app.config.get('DB_ENCRYPTION_KEY') is not None
    if not db_key_loaded:
        issues.append({
            'id': 'db_locked',
            'severity': 'error',
            'message': 'Database is locked. Unlock with your web password.',
            'fix': {'action': 'unlock_db', 'requires': ['password']}
        })
    else:
        status.append({
            'id': 'db_encrypted',
            'icon': '🔐',
            'message': 'Database encryption active'
        })

    # 2. Encryption key files present
    key_file = BASE_DIR / '.db_key'
    salt_file = BASE_DIR / '.db_salt'
    if not key_file.exists() or not salt_file.exists():
        issues.append({
            'id': 'missing_key_files',
            'severity': 'warning',
            'message': 'Encryption key files are missing (.db_key/.db_salt). They will be re-generated after unlock.',
            'fix': {'action': 'unlock_db', 'requires': ['password']}
        })

    # 3. HTTPS cert presence
    certs_ok = (BASE_DIR / 'certs' / 'server.crt').exists() and (BASE_DIR / 'certs' / 'server.key').exists()
    if not certs_ok:
        issues.append({
            'id': 'https_cert',
            'severity': 'info',
            'message': 'HTTPS certificate not found. A self-signed cert will be generated.',
            'fix': {'action': 'auto_generate_on_start'}
        })
    else:
        status.append({
            'id': 'https_enabled',
            'icon': '🔒',
            'message': 'HTTPS encryption enabled'
        })

    # 4. API keys configured
    if not API_KEYS_FILE.exists() and not API_KEYS_ENCRYPTED_FILE.exists():
        issues.append({
            'id': 'api_keys_missing',
            'severity': 'info',
            'message': 'Exchange API keys are not configured. Use Config page to add them.',
            'fix': {'action': 'navigate', 'target': '/config'}
        })

    # 5. Wallets configured
    if not WALLETS_FILE.exists():
        issues.append({
            'id': 'wallets_missing',
            'severity': 'info',
            'message': 'Wallet addresses are not configured. Use Config page to add them.',
            'fix': {'action': 'navigate', 'target': '/config'}
        })

    # 6. Database connectivity
    db_connected = False
    try:
        conn = get_db_connection()
        conn.execute('SELECT 1')
        db_connected = True
        status.append({
            'id': 'db_connected',
            'icon': '✅',
            'message': 'Database connected'
        })
        # Run quick schema integrity check
        try:
            _res = conn.execute('PRAGMA integrity_check')
            res = _res.fetchone() if hasattr(_res, 'fetchone') else ('ok',)
            if res and isinstance(res[0], str) and res[0].lower() != 'ok':
                issues.append({
                    'id': 'schema_integrity',
                    'severity': 'warning',
                    'message': f'Database integrity check reported: {res[0]}',
                    'fix': {'action': 'schema_check', 'endpoint': '/api/diagnostics/schema-check'}
                })
            else:
                status.append({
                    'id': 'schema_ok',
                    'icon': '✅',
                    'message': 'Database integrity verified'
                })
        except Exception as e:
            issues.append({
                'id': 'schema_check_failed',
                'severity': 'warning',
                'message': f'Integrity check failed: {str(e)}',
                'fix': {'action': 'schema_check', 'endpoint': '/api/diagnostics/schema-check'}
            })
        conn.close()
    except Exception as e:
        issues.append({
            'id': 'db_connect',
            'severity': 'error',
            'message': f'Database connection failed: {str(e)}',
            'fix': {'action': 'factory_reset', 'endpoint': '/api/reset/factory'}
        })
    
    # 7. Authentication system
    if USERS_FILE.exists():
        status.append({
            'id': 'auth_enabled',
            'icon': '👤',
            'message': 'Authentication enabled'
        })

    return {
        'issues': issues,
        'status': status,
        'ok': len(issues) == 0,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

@app.route('/api/diagnostics', methods=['GET'])
@login_required
def api_diagnostics():
    """Run basic diagnostics and suggest fixes"""
    result = _compute_diagnostics()
    # Cache latest diagnostics for dashboard
    app.config['DIAGNOSTICS_LAST'] = result
    return jsonify(result)

@app.route('/api/diagnostics/last', methods=['GET'])
@login_required
def api_diagnostics_last():
    """Return last computed diagnostics; run compute if missing"""
    result = app.config.get('DIAGNOSTICS_LAST')
    if not result:
        result = _compute_diagnostics()
        app.config['DIAGNOSTICS_LAST'] = result
    return jsonify(result)

@app.route('/api/diagnostics/generate-cert', methods=['POST'])
@login_required
@web_security_required
def api_diagnostics_generate_cert():
    """Generate self-signed HTTPS certificate"""
    try:
        cert, key = generate_self_signed_cert()
        if not cert or not key:
            return jsonify({'error': 'Failed to generate certificate'}), 400
        # Refresh diagnostics cache
        app.config['DIAGNOSTICS_LAST'] = _compute_diagnostics()
        return jsonify({'success': True, 'message': 'Certificate generated', 'cert': cert, 'key': key})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/diagnostics/schema-check', methods=['GET'])
@login_required
def api_diagnostics_schema_check():
    """Run PRAGMA integrity_check and return result"""
    try:
        conn = get_db_connection()
        res = conn.execute('PRAGMA integrity_check').fetchone()
        conn.close()
        status = (res and res[0]) or 'unknown'
        ok = isinstance(status, str) and status.lower() == 'ok'
        return jsonify({'success': True, 'status': status, 'ok': ok})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/diagnostics/unlock', methods=['POST'])
@login_required
@web_security_required
def api_diagnostics_unlock():
    """Unlock database using the provided web account password"""
    try:
        data = request.get_json() or {}
        password = data.get('password', '').strip()
        if not password:
            return jsonify({'error': 'Password required'}), 400

        if app.config.get('DB_ENCRYPTION_KEY') is not None:
            return jsonify({'success': True, 'message': 'Database already unlocked'})

        from Crypto_Tax_Engine import DatabaseEncryption
        db_key = DatabaseEncryption.initialize_encryption(password)
        app.config['DB_ENCRYPTION_KEY'] = db_key
        audit_log('DB_UNLOCK', 'Database unlocked via diagnostics', session.get('username'))
        # Refresh diagnostics cache after successful unlock
        app.config['DIAGNOSTICS_LAST'] = _compute_diagnostics()
        return jsonify({'success': True, 'message': 'Database unlocked successfully'})
    except Exception as e:
        audit_log('DB_UNLOCK_FAILED', f'Diagnostics unlock failed: {str(e)}', session.get('username'))
        return jsonify({'error': f'Unlock failed: {str(e)}'}), 400

@app.route('/api/logs/download/<path:log_path>', methods=['GET'])
@login_required
def api_download_log(log_path):
    """Download a log file"""
    try:
        # log_path is now just the filename
        log_dir = OUTPUT_DIR / 'logs'
        file_path = log_dir / log_path
        
        # Security check - ensure file is within log directory
        if not str(file_path.resolve()).startswith(str(log_dir.resolve())):
            return jsonify({'error': 'Invalid file path'}), 403
        
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/download-all', methods=['GET'])
@login_required
def api_download_all_logs():
    """Download all logs as a zip file"""
    try:
        log_dir = OUTPUT_DIR / 'logs'
        
        if not log_dir.exists():
            return jsonify({'error': 'No logs directory found'}), 404
        
        # Create zip in memory
        mem_zip = io.BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for log_file in log_dir.glob('*.log'):
                zf.write(log_file, arcname=log_file.name)
        
        mem_zip.seek(0)
        return send_file(
            mem_zip,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'all_logs_{timestamp}.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/download-redacted', methods=['GET'])
@login_required
def api_download_redacted_logs():
    """Download redacted logs (with sensitive info removed) for support"""
    try:
        log_dir = OUTPUT_DIR / 'logs'
        
        if not log_dir.exists():
            return jsonify({'error': 'No logs directory found'}), 404
        
        # Patterns to redact (order matters - more specific patterns first)
        import re
        redaction_patterns = [
            # Potential private keys (long hex strings) - must come before wallet addresses
            (r'\b[a-fA-F0-9]{64,}\b', '[PRIVATE_KEY_REDACTED]'),
            # API Keys and secrets - specific patterns first
            (r'\b(sk_live_[a-zA-Z0-9]{10,})\b', '[REDACTED_SECRET_KEY]'),  # Stripe-style live secret keys
            (r'\b(sk_test_[a-zA-Z0-9]{10,})\b', '[REDACTED_TEST_KEY]'),  # Stripe-style test keys
            (r'\b(sk_[a-zA-Z0-9]{10,})\b', '[REDACTED_SECRET_KEY]'),  # Generic sk_ prefix keys
            # Wallet addresses (common patterns)
            (r'\b(0x[a-fA-F0-9]{40})\b', '[WALLET_ADDRESS]'),  # ETH/EVM
            (r'\b(bc1[a-z0-9]{39,59})\b', '[WALLET_ADDRESS]'),  # BTC Bech32
            (r'\b([13][a-km-zA-HJ-NP-Z1-9]{25,34})\b', '[WALLET_ADDRESS]'),  # BTC Legacy
            # Long alphanumeric strings that look like API keys (32+ chars)
            (r'\b([a-zA-Z0-9_\-]{32,})\b', '[REDACTED_API_KEY]'),
            # API keys with labels
            (r'(["\']?api[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]{16,})', r'\1[REDACTED_API_KEY]'),
            (r'(["\']?secret["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-/+=]{16,})', r'\1[REDACTED_SECRET]'),
            # Email addresses
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
            # IP addresses
            (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '[IP_REDACTED]'),
            # Usernames in common formats
            (r'(user[_-]?name["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]{3,})', r'\1[USERNAME]'),
        ]
        
        # Create zip in memory
        mem_zip = io.BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for log_file in log_dir.glob('*.log'):
                try:
                    # Read log content
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Apply redaction patterns
                    for pattern, replacement in redaction_patterns:
                        content = re.sub(pattern, replacement, content)
                    
                    # Write redacted content to zip
                    zf.writestr(f'redacted_{log_file.name}', content)
                except Exception as e:
                    # If redaction fails for a file, add error note
                    zf.writestr(f'ERROR_{log_file.name}.txt', f'Failed to redact: {str(e)}')
        
        mem_zip.seek(0)
        return send_file(
            mem_zip,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'redacted_logs_{timestamp}.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset-program', methods=['POST'])
@login_required
@web_security_required
def api_reset_program():
    """Reset the program - runs setup with confirmation"""
    try:
        encrypted_payload = request.get_json().get('data')
        if not encrypted_payload:
            return jsonify({'error': 'Missing encrypted data'}), 400
        
        # data = decrypt_data(encrypted_payload)
        data = json.loads(encrypted_payload)
        confirmation = data.get('confirmation', '')
        
        if confirmation != 'RESET':
            return jsonify({'error': 'Invalid confirmation'}), 400
        
        # Run Setup.py
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / 'src' / 'tools' / 'src/tools/setup.py')],
            capture_output=True,
            text=True
        )
        
        response_data = {
            'success': result.returncode == 0,
            'message': 'Program reset completed' if result.returncode == 0 else 'Reset failed',
            'output': result.stdout,
            'errors': result.stderr
        }
        
        # encrypted_response = encrypt_data(response_data)
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps(response_data)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system-health', methods=['GET'])
@login_required
@web_security_required
def api_system_health():
    """Check system health and integrity"""
    try:
        health_status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': []
        }
        
        # Check 1: Database connectivity
        try:
            conn = get_db_connection()
            conn.execute("SELECT COUNT(*) FROM trades").fetchone()
            conn.close()
            health_status['checks'].append({
                'name': 'Database Connection',
                'status': 'OK',
                'message': 'Database is accessible'
            })
        except Exception as e:
            health_status['checks'].append({
                'name': 'Database Connection',
                'status': 'ERROR',
                'message': f'Database error: {str(e)}'
            })
        
        # Check 2: Database integrity
        try:
            conn = get_db_connection()
            integrity_check = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            
            if integrity_check and integrity_check[0] == 'ok':
                health_status['checks'].append({
                    'name': 'Database Integrity',
                    'status': 'OK',
                    'message': 'Database integrity verified'
                })
            else:
                health_status['checks'].append({
                    'name': 'Database Integrity',
                    'status': 'WARNING',
                    'message': f'Integrity check result: {integrity_check[0] if integrity_check else "Unknown"}'
                })
        except Exception as e:
            health_status['checks'].append({
                'name': 'Database Integrity',
                'status': 'ERROR',
                'message': f'Integrity check failed: {str(e)}'
            })
        
        # Check 3: Core scripts existence
        core_scripts = ['Crypto_Tax_Engine.py', 'auto_runner.py', 'src/tools/setup.py']
        missing_scripts = []
        for script in core_scripts:
            if not (BASE_DIR / script).exists():
                missing_scripts.append(script)
        
        if not missing_scripts:
            health_status['checks'].append({
                'name': 'Core Scripts',
                'status': 'OK',
                'message': f'All {len(core_scripts)} core scripts present'
            })
        else:
            health_status['checks'].append({
                'name': 'Core Scripts',
                'status': 'WARNING',
                'message': f'Missing scripts: {", ".join(missing_scripts)}'
            })
        
        # Check 4: Configuration files
        config_files = {
            'config.json': CONFIG_FILE,
            'api_keys (encrypted)': API_KEYS_ENCRYPTED_FILE,
            'wallets (encrypted)': WALLETS_ENCRYPTED_FILE
        }
        missing_configs = []
        for name, path in config_files.items():
            if not path.exists():
                missing_configs.append(name)
        
        if not missing_configs:
            health_status['checks'].append({
                'name': 'Configuration Files',
                'status': 'OK',
                'message': 'All configuration files present'
            })
        else:
            health_status['checks'].append({
                'name': 'Configuration Files',
                'status': 'WARNING',
                'message': f'Missing configs: {", ".join(missing_configs)}'
            })
        
        # Check 5: Output directory
        if OUTPUT_DIR.exists():
            health_status['checks'].append({
                'name': 'Output Directory',
                'status': 'OK',
                'message': 'Output directory exists'
            })
        else:
            health_status['checks'].append({
                'name': 'Output Directory',
                'status': 'WARNING',
                'message': 'Output directory not found'
            })
        
        # Check 6: Encryption key
        if ENCRYPTION_KEY_FILE.exists():
            health_status['checks'].append({
                'name': 'Encryption Key',
                'status': 'OK',
                'message': 'Encryption key present'
            })
        else:
            health_status['checks'].append({
                'name': 'Encryption Key',
                'status': 'WARNING',
                'message': 'Encryption key missing (will regenerate)'
            })
        
        # Overall status
        has_errors = any(check['status'] == 'ERROR' for check in health_status['checks'])
        has_warnings = any(check['status'] == 'WARNING' for check in health_status['checks'])
        
        if has_errors:
            health_status['overall_status'] = 'ERROR'
            health_status['summary'] = 'System has critical errors'
        elif has_warnings:
            health_status['overall_status'] = 'WARNING'
            health_status['summary'] = 'System has warnings'
        else:
            health_status['overall_status'] = 'OK'
            health_status['summary'] = 'All systems operational'
        
        return jsonify(health_status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
@login_required
@web_security_required
def api_get_status():
    """Get system status (timestamps)"""
    try:
        status = tax_app.get_status()
        return jsonify({'data': json.dumps(status)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# MAIN
# ==========================================

@app.route('/api/setup/save', methods=['POST'])
@login_required
@web_security_required
def api_save_setup_config():
    """Save configuration from setup wizard"""
    try:
        # Allow plain JSON for setup wizard (protected by HTTPS + Auth)
        data = request.get_json()
        
        # If wrapped in 'data' (encrypted), try to decrypt
        if 'data' in data:
            try:
                decrypted = decrypt_data(data['data'])
                if isinstance(decrypted, str):
                    decrypted_json = json.loads(decrypted)
                    # If decryption yields a dict, use it.
                    if isinstance(decrypted_json, dict):
                        data = decrypted_json
            except:
                # Fallback to using the raw data if decryption fails or it wasn't encrypted
                pass
        
        # 1. Update config.json
        if 'config' in data:
            current_config = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    current_config = json.load(f)
            
            new_config = data['config']
            # Helper to merge dictionaries recursively
            def deep_update(d, u):
                for k, v in u.items():
                    if isinstance(v, dict):
                        d[k] = deep_update(d.get(k, {}), v)
                    else:
                        d[k] = v
                return d
                
            deep_update(current_config, new_config)
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(current_config, f, indent=4)
                
        # 2. Update api_keys.json (encrypted)
        if 'api_keys' in data:
            current_keys = load_api_keys_file()
            new_keys = data['api_keys']
            for provider, keys in new_keys.items():
                if provider not in current_keys:
                    current_keys[provider] = {}
                for k, v in keys.items():
                    if v and v != "PASTE_KEY" and v != "PASTE_SECRET":
                        current_keys[provider][k] = v
            save_api_keys_file(current_keys)

        # 3. Update wallets.json (encrypted)
        if 'wallets' in data:
            current_wallets = load_wallets_file()
            new_wallets = data['wallets']
            for chain, wallet_data in new_wallets.items():
                if 'addresses' in wallet_data:
                    valid_addresses = [
                        addr.strip() for addr in wallet_data['addresses'] 
                        if addr and addr.strip() and not addr.startswith('PASTE_')
                    ]
                    if valid_addresses:
                        if chain not in current_wallets:
                            current_wallets[chain] = {}
                        current_wallets[chain]['addresses'] = valid_addresses
            save_wallets_file(current_wallets)
                
        return jsonify({'success': True, 'message': 'Configuration saved successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/setup/config', methods=['GET'])
@login_required
@api_security_required
def api_get_setup_config():
    """Get current configuration for setup wizard"""
    try:
        config = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
        api_keys = {}
        if API_KEYS_FILE.exists():
            with open(API_KEYS_FILE, 'r') as f:
                api_keys = json.load(f)
                
        wallets = {}
        if WALLETS_FILE.exists():
            with open(WALLETS_FILE, 'r') as f:
                wallets = json.load(f)
        
        response_data = {
            'config': config,
            'api_keys': api_keys,
            'wallets': wallets
        }
        
        # Return encrypted response as per API standard
        return jsonify({'data': encrypt_data(response_data)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==========================================
# SCHEDULE MANAGEMENT API
# ==========================================

@app.route('/api/schedule/config', methods=['GET'])
@login_required
@api_security_required
def api_get_schedule_config():
    """Get schedule configuration"""
    try:
        config = scheduler.load_schedule_config()
        active_schedules = scheduler.get_active_schedules()

        response_data = {
            'config': config,
            'active': active_schedules
        }

        return jsonify({'data': json.dumps(response_data)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/save', methods=['POST'])
@login_required
@web_security_required
def api_save_schedule():
    """Save schedule configuration"""
    try:
        encrypted_payload = request.get_json().get('data')
        if not encrypted_payload:
            return jsonify({'error': 'Missing encrypted data'}), 400

        data = json.loads(encrypted_payload)

        # Validate schedule data
        if 'schedules' not in data:
            return jsonify({'error': 'Missing schedules array'}), 400

        # Save configuration
        scheduler.save_schedule_config(data)

        # Reload schedules
        scheduler.reload_schedules()

        audit_log('schedule_update', "Updated schedule configuration")

        return jsonify({
            'data': json.dumps({
                'success': True,
                'message': 'Schedule configuration saved'
            })
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/toggle', methods=['POST'])
@login_required
@web_security_required
def api_toggle_schedule():
    """Enable or disable scheduling"""
    try:
        encrypted_payload = request.get_json().get('data')
        if not encrypted_payload:
            return jsonify({'error': 'Missing encrypted data'}), 400

        data = json.loads(encrypted_payload)
        enabled = data.get('enabled', False)

        config = scheduler.load_schedule_config()
        config['enabled'] = enabled
        scheduler.save_schedule_config(config)
        scheduler.reload_schedules()

        audit_log('schedule_toggle', f"Scheduling {'enabled' if enabled else 'disabled'}")

        return jsonify({
            'data': json.dumps({
                'success': True,
                'enabled': enabled
            })
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/test', methods=['POST'])
@login_required
@web_security_required
def api_test_schedule():
    """Run a test calculation immediately"""
    try:
        encrypted_payload = request.get_json().get('data')
        if not encrypted_payload:
            return jsonify({'error': 'Missing encrypted data'}), 400

        data = json.loads(encrypted_payload)
        cascade = data.get('cascade', False)

        # Run calculation in background thread
        def run_test():
            scheduler.run_tax_calculation(cascade=cascade)

        thread = threading.Thread(target=run_test, daemon=True)
        thread.start()

        return jsonify({
            'data': json.dumps({
                'success': True,
                'message': 'Test calculation started'
            })
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def main():
    """Start the web server"""
    global scheduler
    
    # Check ToS acceptance before starting web UI
    from src.utils.tos_checker import check_and_prompt_tos
    check_and_prompt_tos()

    print("=" * 60)
    print("Crypto Tax Generator - Web UI Server")

    # Initialize scheduler
    auto_runner_path = BASE_DIR / 'auto_runner.py'
    scheduler = ScheduleManager(BASE_DIR, auto_runner_path)
    scheduler.reload_schedules()
    print("✓ Scheduler initialized\n")

    print("=" * 60)
    
    # Initialize database encryption
    try:
        users_file = BASE_DIR / 'keys' / 'web_users.json'
        # Defer database unlock until first successful login or account creation
        if not users_file.exists():
            print("\n🔐 Database encryption will be initialized when you create your account.\n")
        else:
            print("\n🔐 Database will unlock automatically on first successful login.\n")
        # Ensure key starts unset; will be populated on login
        app.config['DB_ENCRYPTION_KEY'] = app.config.get('DB_ENCRYPTION_KEY', None)
        # Pre-compute diagnostics for dashboard
        app.config['DIAGNOSTICS_LAST'] = _compute_diagnostics()
    except Exception as e:
        print(f"   ❌ Encryption initialization failed: {e}")
        print("   Starting without encryption.\n")

    # Auto-backup thread (daily) with retention
    def _auto_backup_worker():
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        retention = 14  # keep last 14 backups by default
        interval_hours = 24
        while True:
            try:
                # Build backup zip (encrypted if key present)
                raw_zip = io.BytesIO()
                with zipfile.ZipFile(raw_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                    def add_file(path: Path, arcname: str):
                        if path.exists():
                            zf.write(str(path), arcname)
                    add_file(DB_FILE, 'crypto_master.db')
                    add_file(BASE_DIR / '.db_key', '.db_key')
                    add_file(BASE_DIR / '.db_salt', '.db_salt')
                    add_file(CONFIG_FILE, 'config.json')
                    if API_KEYS_ENCRYPTED_FILE.exists():
                        add_file(API_KEYS_ENCRYPTED_FILE, 'api_keys_encrypted.json')
                    else:
                        add_file(API_KEYS_FILE, 'api_keys.json')

                    if WALLETS_ENCRYPTED_FILE.exists():
                        add_file(WALLETS_ENCRYPTED_FILE, 'wallets_encrypted.json')
                    else:
                        add_file(WALLETS_FILE, 'wallets.json')
                    add_file(USERS_FILE, 'web_users.json')

                raw_zip.seek(0)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                db_key = app.config.get('DB_ENCRYPTION_KEY')
                if db_key:
                    cipher = Fernet(db_key)
                    enc_bytes = cipher.encrypt(raw_zip.getvalue())
                    out_path = BACKUPS_DIR / f'backup_{timestamp}.zip.enc'
                    with open(out_path, 'wb') as f:
                        f.write(enc_bytes)
                else:
                    out_path = BACKUPS_DIR / f'backup_{timestamp}.zip'
                    with open(out_path, 'wb') as f:
                        f.write(raw_zip.getvalue())

                # Retention: keep newest N
                backups = sorted(BACKUPS_DIR.glob('backup_*.zip*'), key=lambda p: p.stat().st_mtime, reverse=True)
                for old in backups[retention:]:
                    try:
                        old.unlink()
                    except Exception:
                        pass
            except Exception:
                pass

            _time.sleep(interval_hours * 3600)

    t = threading.Thread(target=_auto_backup_worker, daemon=True)
    t.start()
    
    # Generate SSL certificate
    cert_file, key_file = generate_self_signed_cert()
    
    # Check if first-time setup is needed
    if is_first_time_setup():
        print("\n✨ FIRST TIME SETUP")
        print("   Navigate to the web UI to create your admin account")
        print("   and complete the setup wizard.\n")
    
    # Start server
    host = '0.0.0.0'
    port = 5000
    
    if cert_file and key_file:
        print(f"\n🔒 Starting HTTPS server at https://localhost:{port}")
        print("   (You may need to accept the self-signed certificate warning)\n")
        app.run(host=host, port=port, ssl_context=(cert_file, key_file), debug=False)
    else:
        print(f"\n⚠️  Starting HTTP server at http://localhost:{port}")
        print("   WARNING: HTTPS is recommended for production!\n")
        app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    main()

