# Natural Language Search Guide

## Overview

Natural Language Search (NLP) is a powerful feature that lets you search your transactions using plain English questions instead of technical filters. This guide shows you how to use it.

## 🚀 Quick Start

1. **Enable Accuracy Mode** (required)
   - Go to Configuration → AI/ML Strategy
   - Select "Accuracy Mode (Full Enhancement)"
   - Ensure "Natural Language Search" checkbox is checked

2. **Open NLP Search**
   - Go to Transactions page
   - Click the **"🤖 NLP Search"** button in the toolbar

3. **Ask Your Question**
   - Type any natural language query
   - Click **Search** or press Enter
   - Results appear in a table below

## 💡 Example Queries

### Time-Based Searches
```
Show me all transactions from January 2024
Find my trades in Q3
What did I buy in November?
```

### Amount-Based Searches
```
Show transactions over $10,000
Find all losses greater than $5,000
Which sales were less than $100?
```

### Action-Based Searches
```
Show me all my BTC purchases
Find every deposit I made
List all staking income
What exchanges did I sell from?
```

### Combination Searches
```
Show my largest ETH trades in 2024
Find all losses from Coinbase
What was my total income from staking?
Show buys over $1,000 in April
```

### Advanced Queries
```
Find my three largest transactions
Show all transfers between wallets
Which exchanges did I use most?
What was my average buy price for Bitcoin?
List my most profitable trades
```

## ⚙️ Requirements

- **Accuracy Mode** must be enabled in Configuration
- **PyTorch & Transformers** must be installed (run `pip install -r requirements-ml.txt`)
- **System Requirements**:
  - CPU: Intel i5 / AMD Ryzen 5 or better
  - RAM: 8GB minimum (16GB recommended)
  - Storage: 5GB free for model cache

## 🎯 How It Works

1. Your query is sent to the Gemma AI model
2. Gemma understands your natural language intent
3. It parses the query into database filters
4. Results are matched against your transaction database
5. Transactions are displayed in an easy-to-read table

## 🔒 Privacy

- All data processing happens **locally** on your machine
- Queries never leave your computer
- No external API calls are made
- Your transaction data is never shared

## ❓ Troubleshooting

### "Natural Language Search requires Accuracy Mode"
- Go to Configuration → AI/ML Strategy
- Select "Accuracy Mode"
- Ensure "Natural Language Search" is checked

### Search takes too long
- This is normal for the first search (model is loading)
- Subsequent searches are faster
- Results should appear within 2-10 seconds

### No results found
- Try rephrasing your question
- Use simpler keywords
- Check the basic search filters to verify data exists

### Error: "Missing dependencies"
- Run: `pip install -r requirements-ml.txt`
- Restart the application

## 📊 Typical Performance

| First Search | Subsequent Searches |
|--------------|-------------------|
| 10-30 seconds | 1-3 seconds |
| (model loads) | (model cached) |

## 🤖 Example Search Walkthrough

**Query:** "Show me my largest Ethereum losses in 2024"

**System processes:**
1. Recognizes intent: "largest" + "losses" + "Ethereum" + "2024"
2. Translates to: 
   - Filter: coin = "ETH"
   - Filter: action = "SELL" (sales can be losses)
   - Filter: date between 2024-01-01 and 2024-12-31
   - Sort: by loss amount (descending)
   - Limit: top results

3. Returns matching transactions in table format

## 📝 Tips for Better Results

1. **Be specific**: "BTC in January" is better than "Bitcoin"
2. **Use round numbers**: "over $10,000" works better than "$10,234.56"
3. **Mention the action**: "buys" vs "sales" helps narrow results
4. **Include timeframe**: "in 2024" or "last month" is helpful
5. **Ask naturally**: Phrase it like you'd ask a friend

## 🔧 Disabling Natural Language Search

If you want to disable NLP but keep Accuracy Mode:
- Go to Configuration → Accuracy Mode Features
- Uncheck "Natural Language Search"
- Click Save

## 💬 Feedback

If NLP searches return unexpected results:
- Try rewording your question
- Check the basic transaction filters first
- Verify your data was imported correctly
- Review the transaction table for data quality

---

**Note:** Natural Language Search works best with well-formatted transaction data. Ensure your imported transactions have complete information (dates, amounts, actions, etc.).
