#!/usr/bin/env python3
"""
Crypto Tax Generator Web UI Server
Self-hosted web interface with HTTPS, authentication, and full feature set
Encrypted API with CSRF protection - only accessible through web UI
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
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
import bcrypt
import jwt
import Crypto_Tax_Engine as tax_app  # Import for status updates

# Configuration paths - avoid importing full engine to reduce dependencies
BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / 'web_templates'
STATIC_DIR = BASE_DIR / 'web_static'
UPLOAD_FOLDER = BASE_DIR / 'inputs'
DB_FILE = BASE_DIR / 'crypto_master.db'
USERS_FILE = BASE_DIR / 'web_users.json'
CERT_DIR = BASE_DIR / 'certs'
CONFIG_FILE = BASE_DIR / 'config.json'
API_KEYS_FILE = BASE_DIR / 'api_keys.json'
WALLETS_FILE = BASE_DIR / 'wallets.json'
OUTPUT_DIR = BASE_DIR / 'outputs'
ENCRYPTION_KEY_FILE = BASE_DIR / 'web_encryption.key'

# Create Flask app
app = Flask(__name__, 
            template_folder=str(TEMPLATE_DIR),
            static_folder=str(STATIC_DIR))
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = None  # CSRF tokens don't expire

# Disable CORS - API should only be accessible from same origin (web UI)
# CORS(app)  # Removed for security

# Session configuration
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

@app.before_request
def generate_nonce():
    """Generate a nonce for CSP"""
    g.csp_nonce = secrets.token_hex(16)

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
    
    # Generate new encryption key
    key = Fernet.generate_key()
    with open(ENCRYPTION_KEY_FILE, 'wb') as f:
        f.write(key)
    
    # Set restrictive permissions (Unix-like systems)
    try:
        os.chmod(ENCRYPTION_KEY_FILE, 0o600)
    except:
        pass
    
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
    except:
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
    except:
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

def create_initial_user(username, password):
    """Create the initial admin user"""
    users = {
        username: {
            'password_hash': bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'is_admin': True
        }
    }
    save_users(users)
    return True

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def verify_password(username, password):
    """Verify username and password"""
    users = load_users()
    if username not in users:
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
    # If users already exist, redirect to login
    if not is_first_time_setup():
        return redirect(url_for('login'))
    
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
def login():
    """Login page"""
    # If first-time setup needed, redirect there
    if is_first_time_setup():
        return redirect(url_for('first_time_setup'))
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        if verify_password(username, password):
            session['username'] = username
            session.permanent = True
            
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

@app.route('/api/reset/factory', methods=['POST'])
@api_security_required
def factory_reset():
    """Perform full factory reset"""
    try:
        # 1. Delete Database
        if DB_FILE.exists():
            os.remove(DB_FILE)
        init_db() # Recreate empty schema
        
        # 2. Delete Configs
        for f in [CONFIG_FILE, API_KEYS_FILE, WALLETS_FILE]:
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
    except:
        return jsonify({'error': 'Invalid data format'}), 400
    
    required_fields = ['date', 'action', 'coin', 'amount']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
            
    conn = get_db_connection()
    
    try:
        # Generate a unique ID
        import uuid
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
    except:
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
    except:
        return jsonify({'error': 'Invalid encrypted data'}), 400
    
    try:
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
        if WALLETS_FILE.exists():
            with open(WALLETS_FILE, 'r') as f:
                wallets = json.load(f)
        else:
            wallets = {}
        
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
        # data = decrypt_data(encrypted_payload)
        data = json.loads(encrypted_payload)
    except:
        return jsonify({'error': 'Invalid encrypted data'}), 400
    
    try:
        with open(WALLETS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        
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
        if API_KEYS_FILE.exists():
            with open(API_KEYS_FILE, 'r') as f:
                api_keys = json.load(f)
            
            # Mask sensitive data
            for exchange, keys in api_keys.items():
                if isinstance(keys, dict):
                    for key, value in keys.items():
                        if key in ['apiKey', 'secret', 'password'] and value:
                            if len(value) > 8 and not value.startswith('PASTE_'):
                                api_keys[exchange][key] = value[:4] + '*' * (len(value) - 8) + value[-4:]
        else:
            api_keys = {}
        
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
        # data = decrypt_data(encrypted_payload)
        data = json.loads(encrypted_payload)
    except:
        return jsonify({'error': 'Invalid encrypted data'}), 400
    
    try:
        # Load existing keys
        if API_KEYS_FILE.exists():
            with open(API_KEYS_FILE, 'r') as f:
                existing_keys = json.load(f)
        else:
            existing_keys = {}
        
        # Update only non-masked values
        for exchange, keys in data.items():
            if exchange not in existing_keys:
                existing_keys[exchange] = {}
            
            if isinstance(keys, dict):
                for key, value in keys.items():
                    # Only update if not masked
                    if value and '*' not in value:
                        existing_keys[exchange][key] = value
        
        with open(API_KEYS_FILE, 'w') as f:
            json.dump(existing_keys, f, indent=4)
        
        # encrypted_response = encrypt_data({'success': True, 'message': 'API keys updated'})
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps({'success': True, 'message': 'API keys updated'})})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        
        return send_file(file_path, as_attachment=True)
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
    """Upload CSV files"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Only CSV files are allowed'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = UPLOAD_FOLDER / filename
        file.save(str(filepath))
        
        # Mark data as changed
        tax_app.mark_data_changed()
        
        result = {
            'success': True,
            'message': f'File {filename} uploaded successfully',
            'filename': filename
        }
        
        # encrypted_response = encrypt_data(result)
        # return jsonify({'data': encrypted_response})
        return jsonify({'data': json.dumps(result)})
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

        auto_runner = BASE_DIR / 'Auto_Runner.py'
        if not auto_runner.exists():
            return jsonify({'error': 'Auto_Runner.py not found'}), 404
        
        # Check for cascade mode
        data = request.get_json() or {}
        cmd = [sys.executable, str(auto_runner)]
        if data.get('cascade'):
            cmd.append('--cascade')
            
        # Run Auto_Runner.py in background
        subprocess.Popen(cmd)
        
        result = {
            'success': True,
            'message': 'Tax calculation started. Check reports page for results.'
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
            [sys.executable, str(BASE_DIR / 'Setup.py')],
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
        setup_script = BASE_DIR / 'Setup.py'
        if not setup_script.exists():
            return jsonify({'error': 'Setup.py not found'}), 404
        
        # Run the script and capture output (shell=False for security)
        env = os.environ.copy()
        env['SETUP_WIZARD_MODE'] = '1'
        
        result = subprocess.run(
            [sys.executable, str(setup_script)],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
            timeout=60,
            shell=False,  # Explicitly set for security
            stdin=subprocess.DEVNULL, # Prevent interactive prompts
            env=env
        )
        
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr if result.returncode != 0 else None
        })
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Setup script timed out'}), 500
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
            with open(API_KEYS_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
        
        elif config_type == 'wallets':
            with open(WALLETS_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
        
        elif config_type == 'config':
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
            [sys.executable, str(BASE_DIR / 'Setup.py')],
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
        core_scripts = ['Crypto_Tax_Engine.py', 'Auto_Runner.py', 'Setup.py']
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
        config_files = {'config.json': CONFIG_FILE, 'api_keys.json': API_KEYS_FILE, 'wallets.json': WALLETS_FILE}
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
                
        # 2. Update api_keys.json
        if 'api_keys' in data:
            current_keys = {}
            if API_KEYS_FILE.exists():
                with open(API_KEYS_FILE, 'r') as f:
                    current_keys = json.load(f)
            
            new_keys = data['api_keys']
            for provider, keys in new_keys.items():
                if provider not in current_keys:
                    current_keys[provider] = {}
                for k, v in keys.items():
                    if v and v != "PASTE_KEY" and v != "PASTE_SECRET":
                        current_keys[provider][k] = v
                        
            with open(API_KEYS_FILE, 'w') as f:
                json.dump(current_keys, f, indent=4)

        # 3. Update wallets.json
        if 'wallets' in data:
            current_wallets = {}
            if WALLETS_FILE.exists():
                with open(WALLETS_FILE, 'r') as f:
                    current_wallets = json.load(f)
            
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
                        
            with open(WALLETS_FILE, 'w') as f:
                json.dump(current_wallets, f, indent=4)
                
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

def main():
    """Start the web server"""
    print("=" * 60)
    print("Crypto Tax Generator - Web UI Server")
    print("=" * 60)
    
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
