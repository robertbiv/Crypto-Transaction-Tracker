# Web UI User Guide

## 🌐 Crypto Tax Generator - Web Interface

A self-hosted, secure web interface for managing your cryptocurrency tax calculations with Material Design 3.

## 🔒 Security Features

### Encrypted API Operations
- **End-to-End Encryption**: All API requests and responses are encrypted using Fernet (symmetric encryption)
- **CSRF Protection**: Cross-Site Request Forgery protection on all endpoints
- **Request Signing**: HMAC-SHA256 signatures on write operations
- **Timestamp Validation**: Prevents replay attacks (5-minute window)
- **Same-Origin Policy**: API only accessible from the web UI (CORS disabled)
- **HTTPS**: Self-signed SSL certificates for encrypted transport

### Authentication
- **Bcrypt Password Hashing**: Industry-standard password security
- **Secure Sessions**: HTTP-only, secure cookies with SameSite protection
- **Session Expiry**: 24-hour session lifetime

### Data Protection
- **Encryption Key**: Automatically generated and stored securely
- **API Key Masking**: Sensitive keys are masked in the UI
- **File Permissions**: Encryption keys have restrictive permissions (0600)

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install Flask Flask-CORS bcrypt PyJWT cryptography
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

### 2. Start the Web Server

```bash
python3 start_web_ui.py
```

Or directly:

```bash
python3 web_server.py
```

### 3. Access the Web UI

The server will start on **https://localhost:5000**

**Note**: You'll need to accept the self-signed certificate warning in your browser.

### 4. Login

**Default Credentials:**
- **Username**: admin
- **Password**: admin123

**⚠️ IMPORTANT**: Change the default password immediately after first login!

## 📱 Features

### Dashboard
- Real-time statistics
- Quick action buttons
- System status overview
- Transaction summary

### Transactions
- View all transactions with pagination
- Search and filter by coin, action, or source
- Edit transaction details
- Delete transactions
- Encrypted data transmission

### Configuration
- Edit config.json (tax settings)
- Manage wallets.json (blockchain addresses)
- Update api_keys.json (exchange API keys)
- All changes encrypted in transit

### Warnings
- View tax review warnings by severity
- See suggestions for improvement
- Statistics dashboard
- Integration with Interactive Fixer

### Reports
- Download generated tax reports
- View gains/losses chart
- Upload CSV files
- Start new tax calculations
- Organized by year

### Settings
- Change password
- Run setup script
- View security status
- System information

## ⚙️ Configuration Guide

### Target Tax Year
The **Target Tax Year** setting controls which year the tax engine processes.

- **Auto-Current Year (Default)**: Leave the field **empty**.
  - The system automatically uses the current calendar year (e.g., 2025).
  - It also checks and finalizes the previous year (e.g., 2024) to ensure correct opening balances.
  - This is the recommended "set it and forget it" mode.

- **Specific Year**: Enter a year (e.g., `2024`).
  - The system forces the calculation to run for that specific year.
  - Useful for re-generating past reports or auditing historical data.
  - **Note**: Remember to clear this field to return to automatic mode.

### Accounting Method
- **FIFO (First In, First Out)**: Sells the oldest coins first.
- **HIFO (Highest In, First Out)**: Sells the most expensive coins first (often results in lower taxes).

## 🔐 Security Best Practices

### 1. Change Default Password
Immediately after first login:
1. Go to **Settings**
2. Enter current password: `admin123`
3. Set a strong new password (minimum 8 characters)

### 2. HTTPS Certificate
The web server automatically generates a self-signed SSL certificate. For production use:
- Accept the browser warning (one-time for self-hosted)
- Or install a trusted certificate in the `certs/` directory

### 3. Network Security
- The web UI is designed for **local/private network use**
- Do NOT expose to public internet without additional security (firewall, VPN, etc.)
- Use strong passwords
- Keep the encryption key (`web_encryption.key`) secure

### 4. API Security
- All database operations require authentication + CSRF token + request signature
- External API calls are blocked (same-origin only)
- Sensitive data is encrypted in transit
- API keys are masked in the UI

## 📁 Files Created

The web UI creates the following files:

```
/Your_Crypto_Tax_Folder
├── web_server.py              # Main server application
├── start_web_ui.py            # Startup script
├── web_users.json             # User accounts (gitignored)
├── web_encryption.key         # Encryption key (gitignored)
├── certs/                     # SSL certificates (gitignored)
│   ├── cert.pem
│   └── key.pem
├── web_templates/             # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── transactions.html
│   ├── config.html
│   ├── warnings.html
│   ├── reports.html
│   └── settings.html
└── web_static/                # Static assets (CSS, JS)
```

## 🛠️ Troubleshooting

### Certificate Errors
**Problem**: Browser shows SSL/HTTPS warning

**Solution**: This is expected with self-signed certificates. Click "Advanced" → "Proceed to localhost" (safe for self-hosted).

### Cannot Connect
**Problem**: "Connection refused" error

**Solution**: 
1. Ensure server is running: `python3 web_server.py`
2. Check the correct URL: `https://localhost:5000` (not http)
3. Check firewall settings

### Login Failed
**Problem**: Invalid credentials

**Solution**:
1. Use default: `admin` / `admin123`
2. If changed and forgotten, delete `web_users.json` to reset

### API Errors
**Problem**: "Invalid CSRF token" or "Invalid signature"

**Solution**:
1. Refresh the page to get a new CSRF token
2. Clear browser cache/cookies
3. Restart the web server

### Encryption Errors
**Problem**: "Invalid encrypted data"

**Solution**:
1. Restart the web server
2. If persistent, delete `web_encryption.key` (will regenerate)
3. You may need to re-enter API keys

## 🔄 Updating

When updating the web UI:

1. Backup your data:
```bash
cp web_users.json web_users.json.bak
cp web_encryption.key web_encryption.key.bak
```

2. Pull updates:
```bash
git pull
```

3. Restart the server:
```bash
python3 start_web_ui.py
```

## 📊 Mobile Support

The web UI is fully responsive and works on:
- Desktop browsers (Chrome, Firefox, Safari, Edge)
- Tablets (iPad, Android tablets)
- Mobile phones (iOS, Android)

## 🆘 Support

For issues or questions:
1. Check the logs in `outputs/logs/`
2. Review the troubleshooting section above
3. Open an issue on GitHub

## ⚖️ License

Same as the main Crypto Tax Generator project. This is provided "as is" with no warranties.

## 🎨 Customization

The web UI uses Material Design 3 and can be customized by editing:
- `web_templates/*.html` - HTML templates
- CSS within `<style>` blocks in templates
- Colors in CSS `:root` variables

## 🔒 Privacy

All data stays on your local machine:
- No telemetry
- No external API calls (except exchange/price APIs)
- No data sent to developers
- Fully self-hosted

---

**Version**: 1.0  
**Last Updated**: December 2024
