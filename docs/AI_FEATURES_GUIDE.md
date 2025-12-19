# 🧠 AI & Machine Learning Features Guide

## Overview

This crypto tax engine includes advanced AI/ML features that enhance accuracy, detect fraud, learn your trading patterns, and provide intelligent insights. All AI models run **locally on your machine** - no data is sent to external servers.

---

## 🎯 AI Strategy Modes

Choose one of three AI strategies in [config.json](../configs/config.json):

### MODE 1: NONE (Deterministic Rules Only)
- **Settings**: `ml_fallback.enabled=false` AND `accuracy_mode.enabled=false`
- **Best For**: Maximum speed, minimal resource usage, rule-based classification only
- **Trade-off**: May leave some transactions unclassified

### MODE 2: ML FALLBACK ONLY
- **Settings**: `ml_fallback.enabled=true` AND `accuracy_mode.enabled=false`
- **Best For**: Balance between speed and accuracy
- **Features**: Deterministic rules + Gemma AI for unclassified transactions

### MODE 3: ACCURACY MODE (Recommended)
- **Settings**: `accuracy_mode.enabled=true` (requires `ml_fallback.enabled=true`)
- **Best For**: Maximum accuracy, comprehensive fraud detection, intelligent insights
- **Features**: Everything in MODE 2 + Fraud Detection + Pattern Learning + Smart Descriptions + Natural Language Search

---

## 🚨 Anomaly Detection

### What It Does
Automatically flags suspicious transactions based on:
- **Price Errors**: Sent/Received ratios that don't match expected market prices
- **Extreme Values**: Transactions significantly larger/smaller than your normal activity
- **Pattern Deviations**: Behavior that doesn't match your learned trading patterns
- **Dust Transactions**: Tiny amounts that may indicate spam or scams

### Warning Severity Levels
- **🔴 HIGH**: Critical issues requiring immediate review (e.g., >50% price error, >5σ from mean)
- **🟠 MEDIUM**: Significant anomalies worth investigating (e.g., 20-50% price error, 3-5σ from mean)
- **🟡 LOW**: Minor anomalies for reference (e.g., 10-20% price error, slight pattern deviation)

### How to Interpret Warnings

When you see an anomaly warning:

1. **Check the Severity Badge**: HIGH warnings are critical, MEDIUM need review, LOW are informational
2. **Read the Message**: Describes what anomaly was detected (e.g., "Extreme Value: 4.2σ above mean")
3. **Review Suggestions**: AI provides actionable fixes (e.g., "Verify exchange rate on date X")
4. **Acknowledge or Fix**: 
   - If correct: Acknowledge and proceed
   - If error: Fix the transaction details before saving

**Example Warning:**
```
🔴 HIGH SEVERITY
Price Error: Sent/Received ratio suggests 35% pricing error
Suggestion: Verify BTC/USD rate on 2024-03-15 was $67,500
```

### Adjusting Sensitivity

Edit [config.json](../configs/config.json) → `anomaly_detection` section:

```json
{
  "anomaly_detection": {
    "price_error_threshold": 20,          // Lower = more sensitive (5-50)
    "extreme_value_threshold": 3.0,       // Higher = less sensitive (2.0-5.0)
    "dust_threshold_usd": 0.10,           // Ignore amounts below this
    "pattern_deviation_multiplier": 2.5,  // Lower = more pattern warnings
    "min_transactions_for_learning": 20   // Required before pattern learning
  }
}
```

**Tuning Tips:**
- **Too many warnings?** Increase thresholds (e.g., `price_error_threshold: 30`)
- **Missing real errors?** Decrease thresholds (e.g., `extreme_value_threshold: 2.5`)
- **Getting dust warnings?** Increase `dust_threshold_usd` to filter noise

---

## 🕵️ Fraud Detection

### What It Does
Identifies potentially fraudulent or risky trading patterns:
- **Wash Sales**: Buying and selling the same asset within 30 days to trigger tax losses
- **Pump & Dump**: Unusual price spikes followed by rapid dumps
- **Suspicious Patterns**: High-frequency trading with minimal profit (potential money laundering)
- **Round-Trip Trades**: Same-day buy/sell of identical amounts (self-trading)

### Fraud Alert Levels
- **Critical**: Confirmed patterns requiring immediate action
- **Warning**: Suspicious activity worth investigating
- **Info**: Borderline patterns to be aware of

### How to Respond

**If you see a fraud alert:**

1. **Review the Transaction Chain**: Check all related transactions in the alert
2. **Verify Legitimacy**: Was this intentional arbitrage or an accidental wash sale?
3. **Correct if Needed**: If legitimate, document the business purpose; if fraudulent, remove
4. **Consult a Tax Professional**: For wash sales, you may need to adjust cost basis

**Example Fraud Alert:**
```
⚠️ WARNING: Potential Wash Sale
Sold 1.5 BTC at loss on 2024-03-01, bought 1.6 BTC on 2024-03-15
Action: IRS wash sale rules may disallow this loss. Adjust cost basis or wait 30+ days.
```

---

## 📊 Pattern Learning

### What It Does
Learns your normal trading behavior over time:
- **Average transaction sizes** per asset
- **Typical trading hours** and frequency
- **Common exchange pairs** and routes
- **Usual fee ranges**

After collecting 20+ transactions, the system builds a profile of your "normal" activity. Any significant deviation triggers an anomaly warning.

### Benefits
- **Reduces False Positives**: Knows your $10K trades are normal if that's your typical size
- **Catches Real Errors**: Flags accidental extra zeros (e.g., $100K instead of $10K)
- **Adapts Over Time**: Continuously updates as your trading patterns evolve

### Exporting Patterns

To review what the AI has learned:

1. Go to **🧠 Analytics** page
2. Click **📤 Export Patterns (JSON)**
3. Review the JSON file for:
   - Average amounts per asset
   - Typical price ranges
   - Common transaction types

---

## 💬 Natural Language Search

### What It Does
Search your transaction history using plain English instead of complex filters.

### Example Queries

**Basic Searches:**
- "Show my Bitcoin transactions"
- "Find all trades in January 2024"
- "Losses greater than $1000"

**Advanced Searches:**
- "Ethereum transactions with high fees"
- "Show staking rewards from last year"
- "Find all transactions involving Uniswap"
- "Largest gains in Q1 2024"

**Analytical Searches:**
- "My most profitable asset this year"
- "Transactions flagged as anomalies"
- "Show me potential wash sales"

### How to Use

1. Go to **🧠 Analytics** page
2. Type your query in the **🔍 Natural Language Search** box
3. Click **Search** or press Enter
4. Results appear below with matching transactions

**Tips for Better Results:**
- Be specific about date ranges ("last year", "Q1 2024", "December")
- Include asset names ("Bitcoin", "ETH", "Cardano")
- Use financial terms ("gains", "losses", "fees", "staking")
- Combine conditions ("Bitcoin losses in 2024 greater than $500")

---

## 🤖 Smart Descriptions

### What It Does
Automatically generates human-readable descriptions for transactions based on:
- Transaction type (trade, transfer, staking, etc.)
- Assets involved
- Amounts and context
- Market conditions

### Examples

**Before (raw):**
```
BTC -> USD | Sent: 0.5 | Received: 33750
```

**After (smart description):**
```
💰 Sold 0.5 BTC for $33,750 USD via Binance (Market rate: $67,500/BTC)
```

**Benefits:**
- **Better Reports**: Tax forms are more readable
- **Audit Trail**: Clear explanations for unusual transactions
- **Quick Review**: Understand at-a-glance what happened

---

## 📈 Analytics Dashboard

### What It Shows

Access via **🧠 Analytics** in the navigation menu:

1. **Anomaly Visualizations**
   - Total anomalies by severity (High/Medium/Low)
   - Timeline of anomalies
   - Top anomaly types

2. **Learned Patterns**
   - Average transaction sizes
   - Most common assets
   - Trading frequency

3. **Fraud Alerts**
   - Active fraud warnings
   - Wash sale detections
   - Suspicious pattern summaries

4. **NLP Search Interface**
   - Natural language transaction search
   - Real-time results
   - Export to CSV

### Exporting Data

- **📊 Export Anomaly Report (CSV)**: All detected anomalies with details
- **📤 Export Patterns (JSON)**: Learned behavior patterns
- **💾 Export Search Results (CSV)**: Results from NLP search

---

## ⚙️ Configuration

All AI features are configured in [config.json](../configs/config.json):

```json
{
  "ml_fallback": {
    "enabled": true,              // Enable ML classification
    "model_name": "gemma",        // "gemma" (neural) or "shim" (keyword)
    "confidence_threshold": 0.85  // Min confidence for suggestions
  },
  "accuracy_mode": {
    "enabled": true,              // Enable all advanced features
    "fraud_detection": true,      // Wash sales, pump & dump
    "smart_descriptions": true,   // Creative descriptions
    "pattern_learning": true,     // Learn trading behavior
    "natural_language_search": true  // NLP search
  },
  "anomaly_detection": {
    "price_error_threshold": 20,  // Price deviation % to flag
    "extreme_value_threshold": 3.0,  // Std deviations for outliers
    "dust_threshold_usd": 0.10    // Ignore tiny amounts
  }
}
```

---

## 🛡️ Privacy & Security

### Local Processing
- **All AI models run locally** on your computer
- **No data is sent to external servers** or APIs
- **No cloud dependencies** for ML features

### Model Details
- **Gemma 3n**: Google's open-source neural model (runs via PyTorch)
- **Shim Mode**: Lightweight keyword-based heuristics (no external dependencies)
- **Memory Management**: Auto-shutdown after batch to free RAM

### Data Storage
- Transaction data stored in local SQLite database
- Learned patterns saved in memory (not persisted by default)
- Anomaly detections logged locally only

---

## 🐛 Troubleshooting

### "Anomaly detector not initialized"
**Solution**: Enable `accuracy_mode.enabled=true` in config.json

### Too many false positive warnings
**Solution**: Increase thresholds in `anomaly_detection` section (see Adjusting Sensitivity above)

### NLP search not finding results
**Solution**: 
- Check that `natural_language_search=true` in config.json
- Try more specific queries with asset names and dates
- Ensure you have transactions in the database

### Pattern learning not detecting anomalies
**Solution**: Need minimum 20 transactions before pattern learning activates. Lower `min_transactions_for_learning` if needed.

### High memory usage with Gemma model
**Solution**: 
- Reduce `batch_size` in `ml_fallback` (try 5 for systems with <8GB RAM)
- Enable `auto_shutdown_after_batch=true`
- Switch to `model_name: "shim"` for lightweight mode

---

## 📚 Further Reading

- [API Documentation](API_DOCUMENTATION.md) - Technical details for developers
- [Accuracy Mode Guide](ACCURACY_MODE.md) - Deep dive into ML strategies
- [Natural Language Search Guide](NATURAL_LANGUAGE_SEARCH_GUIDE.md) - Advanced NLP queries

---

**Questions?** Check the [main README](../README.md) or review your configuration in [config.json](../configs/config.json).
