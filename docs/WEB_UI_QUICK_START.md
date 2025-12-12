# 🚀 Web UI Quick Start Guide

Get your encrypted web interface up and running in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install Flask Flask-CORS bcrypt PyJWT cryptography
```

Or install all project dependencies:

```bash
pip install -r requirements.txt
```

## Step 2: Start the Web Server

```bash
python3 start_web_ui.py
```

Or directly:

```bash
python3 web_server.py
```

You should see:

```
============================================================
Crypto Tax Generator - Web UI Server
============================================================
Generating self-signed SSL certificate...
SSL certificate generated: /path/to/certs/cert.pem

⚠️  WARNING: Default admin password detected!
   Username: admin
   Password: admin123
   CHANGE THIS IMMEDIATELY after logging in!

🔒 Starting HTTPS server at https://localhost:5000
   (You may need to accept the self-signed certificate warning)
```

## Step 3: Access the Web UI

1. Open your browser and navigate to:
   ```
   https://localhost:5000
   ```

2. **Accept the certificate warning** (this is safe for self-hosted applications)
   - Chrome: Click "Advanced" → "Proceed to localhost"
   - Firefox: Click "Advanced" → "Accept the Risk and Continue"
   - Safari: Click "Show Details" → "visit this website"

## Step 4: Login

Use the default credentials:
- **Username**: `admin`
- **Password**: `admin123`

## Step 5: Change Your Password! 🔐

**IMPORTANT**: Change the default password immediately!

1. Click on **Settings** in the navigation bar
2. Enter current password: `admin123`
3. Enter your new secure password (minimum 8 characters)
4. Click "Change Password"

## Step 6: Explore the Features

### Dashboard
- View transaction statistics
- See gains/losses summary
- Quick actions (Run calculation, upload CSV, etc.)

### Transactions
- Browse all your crypto transactions
- Search and filter by coin, action, or source
- Edit or delete transactions
- **All operations are encrypted end-to-end**

### Configuration
- **General Settings**: Edit config.json (tax settings, FIFO/HIFO, etc.)
- **Wallets**: Add blockchain wallet addresses for auditing
- **API Keys**: Add exchange API keys (read-only recommended)
- **All data encrypted in transit**

### Warnings
- View tax review warnings by severity
- See audit risk suggestions
- Integration with Interactive Fixer

### Reports
- Download generated tax reports by year
- View gains/losses chart
- Upload CSV files
- Start new tax calculations

### Settings
- Change your password
- Run setup script
- View security status
- System information

## 🔒 Security Features

Your web UI includes military-grade security:

✅ **End-to-End Encryption** - All API operations encrypted with Fernet  
✅ **CSRF Protection** - Cross-Site Request Forgery prevention  
✅ **Request Signing** - HMAC-SHA256 signatures on write operations  
✅ **HTTPS** - Self-signed SSL certificates  
✅ **Secure Sessions** - 24-hour lifetime, HTTP-only cookies  
✅ **Password Hashing** - Bcrypt with cost factor 12  
✅ **Same-Origin API** - Cannot be accessed externally  

## 📱 Mobile Access

The web UI is fully responsive! Access it from:
- **Desktop**: Chrome, Firefox, Safari, Edge
- **Tablet**: iPad, Android tablets
- **Mobile**: iOS, Android phones

## 🛠️ Troubleshooting

### "Connection Refused"
- Ensure the server is running: `python3 web_server.py`
- Check you're using HTTPS (not HTTP): `https://localhost:5000`
- Check firewall settings

### "Certificate Error"
- This is normal for self-signed certificates
- Click "Advanced" → "Proceed" (safe for self-hosted)
- The connection is still encrypted

### "Invalid CSRF Token"
- Refresh the page to get a new token
- Clear browser cache and cookies
- Restart the web server

### "Login Failed"
- Use default credentials: `admin` / `admin123`
- If you changed it and forgot, delete `web_users.json` to reset

## 🎯 Next Steps

1. ✅ Change default password
2. ✅ Add your API keys (Configuration → API Keys)
3. ✅ Add your wallet addresses (Configuration → Wallets)
4. ✅ Adjust tax settings (Configuration → General Settings)
5. ✅ Upload any manual CSV files (Reports → Upload CSV)
6. ✅ Run tax calculation (Dashboard → Run Tax Calculation)
7. ✅ Download your reports (Reports page)

## 📚 Documentation

For detailed information, see:
- [Web UI User Guide](WEB_UI_GUIDE.md) - Complete documentation
- [Main README](../README.md) - Overall project documentation

## 🆘 Need Help?

- Check the logs in `outputs/logs/`
- Review [WEB_UI_GUIDE.md](WEB_UI_GUIDE.md) troubleshooting section
- Open an issue on GitHub

---

**🎉 Enjoy your secure, self-hosted crypto tax web interface!**

*Your data never leaves your machine. Complete privacy guaranteed.*
