# 🚀 Setup Wizard - User Guide

## Overview

The Crypto Tax Generator now features a **professional 5-step setup wizard** that appears automatically on first start. No more searching for passwords in console logs or manually editing JSON files!

## Key Features

- ✅ **Unlocked First Start** - No authentication required for setup
- ✅ **No Console Passwords** - Create account directly in web UI
- ✅ **Automated Setup Script** - Runs Setup.py with real-time output
- ✅ **Guided Configuration** - Step-by-step API keys, wallets, settings
- ✅ **Auto-Login** - Seamlessly logs you in after completion
- ✅ **Material Design 3** - Professional, modern interface
- ✅ **Mobile Responsive** - Works on all devices

## Getting Started

### 1. Install Dependencies

```bash
pip install Flask Flask-CORS bcrypt PyJWT cryptography
```

### 2. Start the Server

```bash
python3 start_web_ui.py
```

### 3. Open Your Browser

Navigate to:
```
https://localhost:5000
```

Accept the self-signed certificate warning (safe for local use).

### 4. Complete the Setup Wizard

The wizard will appear automatically - no login needed!

## Setup Wizard Steps

### 📝 Step 1: Create Your Account

**What it does:**
- Create your username and password
- Real-time password strength indicator
- Security reminders displayed

**Tips:**
- Use a strong, unique password
- Don't reuse passwords from other services
- Consider using a password manager

**Required:**
- Username (any valid username)
- Password (minimum 8 characters)
- Password confirmation

---

### ⚙️ Step 2: Initialize System

**What it does:**
- Automatically runs `Setup.py` script
- Creates required folders (inputs, outputs, logs)
- Checks for dependencies
- Generates configuration templates
- Shows real-time output

**What you'll see:**
- Terminal-style output box
- Progress messages
- Success/error indicators

**No action required** - this step runs automatically!

---

### 🔑 Step 3: Configure API Keys (Optional)

**What it does:**
- Guides you through adding exchange API keys
- Adds blockchain provider keys (Moralis, Blockchair)
- Organizes keys by category

**Supported Exchanges:**
- Binance, Binance US
- Coinbase, Coinbase Pro
- KuCoin, Gate.io
- Bybit, OKX
- And 20+ more!

**Blockchain Providers:**
- **Moralis** (Required for EVM/Solana blockchain audits)
- **Blockchair** (Optional for Bitcoin/UTXO chains)

**Tips:**
- Always use **READ-ONLY** API keys
- Never give write permissions
- You can skip this and add keys later in Settings
- Moralis is highly recommended for accurate blockchain data

**Can be skipped** - configure later via Settings page

---

### 💼 Step 4: Add Wallet Addresses (Optional)

**What it does:**
- Add cryptocurrency wallet addresses for tracking
- Support for multiple addresses per currency
- Easy add/remove functionality

**How to add wallets:**
1. Click "Add Wallet" button
2. Enter currency code in first field (e.g., BTC, ETH, SOL)
3. Enter wallet address in second field
4. Click "Add Wallet" again to add more

**Tips:**
- Use uppercase for currency codes (BTC, ETH, not btc, eth)
- Add all wallets you want to track
- You can add more later in Configuration page
- Remove wallets by clicking the "Remove" button

**Can be skipped** - configure later via Configuration page

---

### ⚙️ Step 5: Configure Settings

**What it does:**
- Set accounting method
- Choose tax year
- Configure tax calculation preferences

**Settings:**

**Accounting Method:**
- **HIFO** (Highest In, First Out) - Minimizes taxes
- **FIFO** (First In, First Out) - Most common
- **LIFO** (Last In, First Out)

**Tax Year:**
- Default: Current year
- Can be changed later

**Options:**
- ✅ Use long-term capital gains benefits (>365 days)
- ✅ Include fees in cost basis

**Tips:**
- HIFO typically results in lowest tax liability
- Long-term benefits should be enabled for tax optimization
- Including fees in cost basis is recommended for accuracy

---

### ✅ Completion & Auto-Login

**What happens:**
1. Click "Complete Setup"
2. Your settings are saved
3. Setup completion is marked
4. **You're automatically logged in!**
5. Redirected to dashboard
6. Ready to use the application!

**No manual login required!**

---

## After Setup

Once setup is complete, you can:

### Dashboard
- View transaction statistics
- See gains/losses charts
- Start new tax calculations
- Upload CSV files

### Transactions
- Browse all transactions
- Search and filter
- Edit or delete entries
- All operations encrypted

### Configuration
- Edit general settings
- Manage wallet addresses
- Update API keys
- All changes encrypted

### Warnings
- View tax review warnings
- See audit risk suggestions
- Fix issues with Interactive Fixer

### Reports
- Download tax reports by year
- View gains/losses breakdowns
- Export transaction data

### Settings
- Change your password
- Run setup again (repair)
- Reset program (danger zone)
- View security information

## Security Features

The setup wizard maintains all security features:

### During Setup (Unlocked)
- ✅ Wizard only accessible when no users exist
- ✅ Redirects to login if users already exist
- ✅ User validation on each step
- ✅ Secure password hashing (Bcrypt)
- ✅ Configuration saved with validation

### After Setup (Locked)
- ✅ Full authentication required
- ✅ End-to-end encryption (Fernet AES-128)
- ✅ CSRF protection on all writes
- ✅ HMAC-SHA256 request signing
- ✅ Timestamp validation (5-min window)
- ✅ HTTPS with self-signed SSL
- ✅ Secure session management
- ✅ Same-origin API enforcement

## Troubleshooting

### Setup page doesn't appear
- Ensure no `web_users.json` file exists
- Delete `web_users.json` and restart server
- Check browser console for errors

### Setup script fails
- Check dependencies are installed: `pip install -r requirements.txt`
- Ensure Python 3.8+ is installed
- Check logs in `outputs/logs/` folder

### Can't add wallets
- Use uppercase currency codes (BTC, not btc)
- Ensure address field is not empty
- Try clicking "Add Wallet" button again

### Password too weak warning
- Use at least 8 characters
- Include uppercase, lowercase, numbers, symbols
- Aim for "Strong" rating on strength indicator

### Browser security warning
- This is normal for self-signed certificates
- Safe for local use
- Click "Advanced" → "Proceed to localhost"

## FAQ

### Q: Can I skip API keys and wallets?
**A:** Yes! Both Step 3 and Step 4 are optional. You can add them later through the Settings and Configuration pages.

### Q: What if I make a mistake during setup?
**A:** You can run the setup wizard again by deleting `web_users.json` file and restarting the server. Or use the "Reset Program" option in Settings (requires confirmation).

### Q: Is my data secure during setup?
**A:** Yes! Even though the wizard is unlocked, all data is saved with validation, passwords are hashed with Bcrypt, and full encryption is enabled after setup completes.

### Q: Can I change settings after setup?
**A:** Absolutely! All settings can be modified later through the Configuration and Settings pages.

### Q: Do I need Moralis API key?
**A:** Highly recommended if you have EVM (Ethereum, Polygon, BSC) or Solana transactions. Required for accurate blockchain auditing.

### Q: What if the setup script times out?
**A:** The script has a 30-second timeout. If it fails, you can continue to the next steps and run Setup.py manually later, or use the "Repair Program" option in Settings.

## Next Steps

After completing the setup wizard:

1. **Upload transaction data**
   - CSV files from exchanges
   - Manual entry via UI

2. **Run tax calculation**
   - Click "Start New Run" on dashboard
   - Watch progress in real-time

3. **Review warnings**
   - Check Warnings page
   - Use Interactive Fixer for issues

4. **Download reports**
   - Navigate to Reports page
   - Download tax forms by year

5. **Schedule automated runs** (coming soon)
   - Set up recurring calculations
   - Automated report generation

## Support

For issues or questions:
- Check the logs in `outputs/logs/`
- Review documentation in `docs/`
- Check system health on Dashboard
- Run system health check (automatic on login)

---

**Enjoy your professional setup experience!** 🎉
