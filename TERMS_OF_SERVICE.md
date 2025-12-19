# Terms of Service - Crypto Transaction Tracker

**Last Updated: December 19, 2025**

## TL;DR

This is a personal, self-hosted tool I built to track and review my own crypto activity. It's provided AS-IS with **no warranty**. I'm not a financial, accounting, or legal professional. You must review all outputs with a qualified advisor before acting on them. This tool can make mistakes. **I take no liability for errors, data loss, or regulatory consequences.** Use locally only. Use Read-Only API tokens for security. See requirements.txt for dependencies.

---

## Acceptance of Terms

By downloading, installing, or using this software ("the Program"), you agree to be bound by these Terms of Service. If you do not agree to these terms, do not use the Program.

## 1. NO WARRANTY; AS-IS USE

The Program is provided "AS IS" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, or non-infringement.

The author makes no warranty that:
- The Program will meet your requirements
- The Program will be uninterrupted, timely, secure, or error-free
- Any defects will be corrected
- The Program is free of harmful code or malware

## 2. NO FINANCIAL, ACCOUNTING, OR LEGAL ADVICE; NOT A PROFESSIONAL SERVICE

The author is **not a financial advisor, accountant, attorney, or compliance professional**. The Program was built for personal transaction tracking and does not constitute professional advice or services of any kind.

The Program may surface reports and analytics, but they are **not guaranteed to be accurate, complete, or correct**, and they are **not designed to be used as-is for regulatory filings or submissions**.

**You must independently verify all outputs and consult qualified professionals before making financial, accounting, or legal decisions.**

Digital asset regulation is complex and evolving. This Program cannot address all edge cases or changes in law.

## 3. LIMITATION OF LIABILITY

**IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY:**
- Direct, indirect, incidental, special, exemplary, or consequential damages
- Loss of profits, revenue, data, use, or other intangible losses
- Damage to data or property
- Transaction liabilities, penalties, interest, or back Transactions
- Audit costs or legal fees
- Any damages arising from use or inability to use the Program

**This applies even if the author has been advised of the possibility of such damages.**

## 4. USER ASSUMES ALL RISK

You assume all risk of loss associated with using this Program, including:
- Inaccurate calculations or missing transactions
- Incorrect cost basis or gain/loss computations
- Undetected duplicates or data corruption
- Incorrect price data or exchange rate errors
- Transaction misstatements or non-compliance
- Audit exposure or penalties from the IRS
- Data loss or security breaches

## 5. LOCAL USE ONLY

The Program is intended to run on your local machine or private network only. **Do not expose the Program to the internet or make it publicly accessible.**

The web interface uses self-signed HTTPS certificates and is not hardened for public access. Security is not guaranteed. You are responsible for network segmentation and access control.

## 6. SECURITY AND DATA RESPONSIBILITY

You are solely responsible for:
- Securing the host machine and network
- Protecting API keys and secrets (stored encrypted but accessible if host is compromised)
- **Using READ-ONLY API tokens only** – Never provide write/trade permissions to this Program. Generate read-only keys from each exchange for transaction history access only.
- Managing backups of your data and database
- Keeping the Program and dependencies up to date
- Monitoring for security patches and updates
- Protecting your wallet addresses and personal information

The Program stores encrypted secrets, but encryption is only as strong as your host security and key management practices.

**IMPORTANT:** If a read-only token is compromised, attackers can only view your history. If a write-enabled token is compromised, they can execute trades, drain accounts, or cause financial damage.

## 7. NO LIABILITY FOR DATA LOSS

The Program may delete, corrupt, or lose data due to:
- Software bugs
- Hardware failure
- Network interruption
- User error
- Third-party API failures
- Backup failures

**The author is not responsible for any lost data or recovery costs. You are responsible for maintaining independent backups.**

## 8. ACCURACY AND COMPLETENESS NOT GUARANTEED

The Program may:
- Calculate gains/losses incorrectly
- Miss transactions or exchange events
- Produce incorrect cost basis
- Fail to detect wash sales or identify affected transactions
- Misclassify income or losses
- Generate incomplete or malformed reports
- Fail to fetch prices or other data

**You must manually review all CSV outputs before using them for any financial, accounting, or compliance purpose.**

## 9. THIRD-PARTY SERVICES

The Program uses third-party APIs and services:
- CCXT (exchange data)
- staketaxcsv (staking rewards)
- Moralis (blockchain data)
- Blockchair (blockchain data)
- CoinGecko (stablecoin lists, token addresses)
- Yahoo Finance (historical prices)

The author is not responsible for:
- Service outages or data unavailability
- Incorrect data from third parties
- Changes to third-party APIs or pricing
- Account bans from third-party services
- Privacy breaches at third-party providers

See each provider's privacy policy and terms of service.

## 10. THIRD-PARTY PYTHON DEPENDENCIES

This Program relies on numerous open-source Python libraries. **All third-party libraries and their licenses belong to their respective owners.**

The Program uses the following major dependencies (for the complete, up-to-date list, see [requirements.txt](requirements.txt)):

| Package | Version | Purpose | License | Link |
| :---- | :---- | :---- | :---- | :---- |
| **ccxt** | 4.5.26 | Unified cryptocurrency exchange API library for fetching trade history and ledger data | MIT | https://github.com/ccxt/ccxt |
| **pandas** | 2.3.3 | Data manipulation and analysis (core data structure for transactions) | BSD-3 | https://pandas.pydata.org |
| **yfinance** | 0.2.66 | Historical price data from Yahoo Finance API for cost basis and gain calculations | Apache-2.0 | https://github.com/ranaroussi/yfinance |
| **requests** | 2.32.5 | HTTP library for API calls to exchanges and data providers | Apache-2.0 | https://requests.readthedocs.io |
| **cryptography** | 46.0.3 | Cryptographic library for encrypting API keys and wallet data at rest | Apache-2.0/BSD-3 | https://cryptography.io |
| **bcrypt** | 5.0.0 | Password hashing for web UI authentication | Apache-2.0 | https://github.com/pyca/bcrypt |
| **Flask** | 3.1.2 | Web framework for self-hosted UI and API | BSD-3 | https://flask.palletsprojects.com |
| **PyJWT** | 2.10.1 | JSON Web Token support for session management | MIT | https://pyjwt.readthedocs.io |
| **APScheduler** | 3.10.4 | Task scheduling for automated Transaction processing runs | MIT | https://apscheduler.readthedocs.io |
| **pytest** | 9.0.2 | Testing framework for validation suite | MIT | https://pytest.org |
| **coincurve** | 21.0.0 | Bitcoin/Ethereum elliptic curve library for key handling | MIT | https://github.com/ofek/coincurve |
| **beautifulsoup4** | 4.14.3 | HTML/XML parsing for web scraping fallbacks | MIT | https://www.crummy.com/software/BeautifulSoup |
| **aiohttp** | 3.13.2 | Async HTTP client for parallel API requests | Apache-2.0 | https://docs.aiohttp.org |
| **filelock** | 3.20.0 | Cross-platform file locking for concurrent access | Public Domain | https://py-filelock.readthedocs.io |

**Additional Dependencies:** This Program also uses numerous smaller libraries (urllib3, Werkzeug, Jinja2, certifi, etc.) for networking, templating, cryptography, and utilities. All are listed in [requirements.txt](requirements.txt) with version pinning.

**License Compliance:** The author respects all open-source licenses. Users are responsible for understanding the licenses of any modified or deployed versions of this Program.

**Note on Dependency Updates:** The list above reflects versions at release time. Package versions may be updated for security patches or compatibility. Always check [requirements.txt](requirements.txt) for the authoritative, up-to-date list of dependencies.

## 11. NO SUPPORT OR SLA

The Program is provided without any support, updates, or service level agreement (SLA). The author may or may not respond to issues, pull requests, or feature requests.

## 12. COMPLIANCE RESPONSIBILITY

You are solely responsible for:
- Complying with all applicable laws and regulations
- Ensuring accuracy of any reports or filings you create
- Paying any amounts owed to authorities or counterparties
- Responding to any regulator inquiries or audits
- Hiring professional representation if audited or investigated

**If you use this Program and submit incorrect or incomplete information anywhere, you are responsible for resulting penalties, interest, or legal consequences.**

## 13. CONFIGURATION AND SETTINGS

Certain configuration options are marked "Not Recommended" because they increase reconciliation risk or diverge from conservative reporting practices:
- **HIFO accounting** requires specific identification (not supported by this Program)
- **Constructive receipt deferrals** for staking are aggressive positions
- **Strict broker mode disabled** can cause mismatches with exchange-provided statements

**Using non-recommended settings increases your exposure to errors. The author assumes no responsibility for using these settings.**

## 14. NO WARRANTY OF PERFORMANCE

The Program may:
- Run slowly or consume significant resources
- Fail to complete processing
- Crash or hang during long operations
- Timeout while fetching data
- Produce incomplete results if interrupted

## 15. CHANGES TO TERMS

The author may update these Terms at any time without notice. Continued use constitutes acceptance.

## 16. SEVERABILITY

If any provision of these Terms is found to be unenforceable, the remaining provisions remain in effect.

## 17. ENTIRE AGREEMENT

These Terms constitute the entire agreement regarding your use of the Program and supersede all prior agreements.

---

## Acceptance

By using this Program, you acknowledge that:

✓ You have read and understand these Terms of Service  
✓ You assume all risk and responsibility for use  
✓ You will not hold the author liable for any losses or damages  
✓ You will review all outputs with a qualified tax professional  
✓ You will not file taxes based solely on this Program's output without professional review  
✓ You understand this is not professional tax advice  
✓ You will keep the Program local and secure  
✓ You will maintain your own backups  

---

**Questions?** Consult a qualified tax professional or attorney before using this Program.
