# 🧠 AI Capabilities Inventory & Model Requirements

**Current Model:** Gemma 3n  
**Date:** December 18, 2025

---

## 📋 Complete AI Capability List

### 1. **Anomaly Detection** (Statistical + Rule-based)
**What it does:**
- Detects price discrepancies (>20% from market price)
- Identifies extreme values (3σ outliers)
- Flags dust attacks (<$0.10 suspicious transfers)
- Detects unusual transaction patterns
- Compares against historical baselines

**Model Requirements:** ⭐ LOW
- No neural network needed
- Pure statistical/heuristic rules
- Works with any model or no model

**Performance:** Real-time (<100ms per transaction)

---

### 2. **Fraud Detection** (Pattern Recognition)
**What it does:**
- **Wash Sales**: Buy→Sell same coin within 30 days
- **Pump & Dumps**: >50% price spikes + rapid dumps
- **Round-Trip Trades**: Same-day buy/sell identical amounts
- **Money Laundering Patterns**: High-frequency minimal-profit trades
- **Confidence Scoring**: Returns severity (Critical/Warning/Info)

**Model Requirements:** ⭐ MEDIUM
- Rule-based version: Fast, deterministic
- Gemma version: Context-aware, understands market conditions
- Could use simpler models if only need pattern matching

**Performance:**
- Fast mode: <500ms
- Gemma mode: 1-3 seconds

---

### 3. **Pattern Learning** (Behavioral Analysis)
**What it does:**
- Builds profile of user's normal trading behavior
- Tracks: average amounts per asset, trading hours, exchange preferences, fee patterns
- Requires 20+ transactions to activate
- Detects deviations (3x average amount = flag)
- Learns user profile: "Conservative" / "Aggressive" / "Diversified"
- Continuous adaptation

**Model Requirements:** ⭐ MEDIUM-HIGH
- Heuristic version: Statistical aggregation only
- Gemma version: Understands context ("I always buy dips so large purchase isn't anomaly")
- Needs semantic understanding for nuance

**Performance:**
- Learning phase: 1-5 seconds (first 20+ txs)
- Detection: <500ms per transaction

---

### 4. **Natural Language Search** (NLP - Core Feature)
**What it does:**
- Parse queries like:
  - "Show BTC transactions in Q4 2024"
  - "Show my biggest losses in 2024"
  - "When did I buy the dip?"
  - "Show all trades where I made >50% profit"
  - "Find all suspicious trades from exchanges I don't usually use"
- Interpret intent (time periods, metrics, conditions)
- Return results with confidence scores
- Filter by: coin, date range, action (BUY/SELL), profit/loss, amount, source

**Model Requirements:** ⭐⭐⭐ HIGH (CRITICAL)
- **Heuristic version:** Regex-based, very limited
  - Can only handle simple queries like "BTC transactions"
  - Cannot understand "biggest losses" without explicit keywords
  - Cannot handle temporal reasoning ("before", "after", "during")
  - Single-dimension queries only
- **Gemma version:** True NLP
  - Understands semantic relationships
  - Handles complex multi-condition queries
  - Temporal reasoning (dates, quarters, years)
  - Profit/loss calculations
  - Conditional logic ("where I made >50%")

**Performance:**
- Fast mode (regex): <100ms
- Gemma mode: 2-5 seconds

**Critical for this feature:** Needs language model with semantic understanding

---

### 5. **Smart Descriptions** (Text Generation)
**What it does:**
- Auto-generates detailed transaction descriptions
- Context-aware (understands transaction sequence)
- Creative phrasing for tax reviews
- Examples:
  - Heuristic: "Purchased 1.5 BTC @ $42,000"
  - Gemma: "Strategic partial take-profit on strong close"

**Model Requirements:** ⭐⭐ MEDIUM-HIGH
- Heuristic version: Template-based ("Bought X at price Y")
- Gemma version: Contextual understanding + generation
- Needs language generation capability

**Performance:**
- Fast mode: <100ms
- Gemma mode: 1-2 seconds

---

### 6. **DeFi Classification** (Protocol Recognition)
**What it does:**
- Identifies DeFi protocol interactions
- Categories:
  - Liquidity Pool: deposits/withdrawals/LP tokens
  - Yield Farming: staking, rewards
  - Lending/Borrowing: collateral, loans
  - Token Swaps: DEX trades
  - Staking: validator participation
  - Governance: voting participation

**Model Requirements:** ⭐ LOW-MEDIUM
- Heuristic version: Token name/address matching
- Gemma version: Understands complex DeFi mechanics
- Could use specialized domain model

**Performance:** <500ms per classification

---

### 7. **AML Detection** (Anti-Money Laundering)
**What it does:**
- Detects suspicious clustering of transactions
- Flags unusual transaction timing
- Identifies abnormal amounts
- Temporal pattern analysis (rapid sequences)
- Cross-exchange suspicious flows
- Compliance reporting

**Model Requirements:** ⭐⭐ MEDIUM
- Heuristic version: Rule-based thresholds
- Gemma version: Contextual anomaly detection
- Could use simpler decision tree approach

**Performance:** <1 second per scan

---

### 8. **Auto-Categorization** (Classification)
**What it does:**
- When transaction action/type is unknown
- Suggests category: BUY, SELL, DEPOSIT, WITHDRAWAL, FEE, INCOME, TRANSFER, TRADE
- Returns confidence score
- Requires user confirmation

**Model Requirements:** ⭐ LOW-MEDIUM
- Heuristic version: Keyword-based rules
- ML version: Trained on transaction metadata
- Simple classifier sufficient

**Performance:** <500ms

---

### 9. **Transaction History & Undo** (Audit Trail)
**What it does:**
- Tracks all transaction changes (who, when, what)
- Ability to revert/undo edits
- Maintains edit history
- Compliance auditing

**Model Requirements:** ⭐ NONE
- Pure database/log operations
- No ML needed

**Performance:** <100ms

---

### 10. **Analytics Dashboard** (Visualization)
**What it does:**
- Real-time visualization of:
  - Anomalies by severity (High/Medium/Low)
  - Learned patterns (avg amounts, frequency)
  - Fraud alerts summary
  - NLP search results
- Export capabilities: CSV, JSON
- Interactive charts and filtering

**Model Requirements:** ⭐ NONE
- Presentation layer only
- Data aggregation and visualization
- No ML needed

**Performance:** <500ms for data aggregation

---

## 📊 Summary by Model Requirement Level

### ⭐ LOW (Heuristics sufficient)
- Anomaly Detection (statistical)
- Transaction History
- Analytics Dashboard
- Auto-categorization (simple keyword matching)
- DeFi Classification (basic token matching)

### ⭐⭐ MEDIUM (Could benefit from ML)
- Fraud Detection (pattern matching works)
- AML Detection (thresholds work)
- Pattern Learning (statistical baseline works)
- DeFi Classification (advanced DeFi understanding)

### ⭐⭐⭐ HIGH (Needs language model)
- **Natural Language Search** (CORE - requires semantic NLP)
- Smart Descriptions (text generation)
- Pattern Learning (behavioral semantics)

---

## 🎯 Critical Decision: NLP Search

**The biggest blocker for alternative models is Natural Language Search.**

Gemma 3n is needed primarily for:
1. Parsing complex natural language queries
2. Understanding temporal relationships ("before 2024", "in Q3")
3. Metric interpretation ("biggest losses", ">50% profit")
4. Multi-condition queries ("where I bought AND made >50%")

**Alternative Model Options:**

### Option A: Smaller Language Model
- **Candidates**: Llama 2 7B, Mistral 7B, Phi 3, TinyLLaMA
- **Pros**: Faster, less resource-hungry, still good NLP
- **Cons**: May have lower accuracy on complex queries
- **Requirements**: Still need 8GB+ RAM, GPU optional

### Option B: Lightweight NLP + Regex Hybrid
- Keep heuristic/regex for simple queries
- Use lightweight model only for complex queries
- **Pros**: Most queries stay fast
- **Cons**: Two-tier system, maintenance overhead

### Option C: Pre-built NLP Library (No Model)
- Use spaCy, NLTK, or similar
- Custom grammar for transaction queries
- **Pros**: No neural network, lightweight
- **Cons**: Limited semantic understanding, high maintenance

### Option D: API-based Model
- Send queries to external service (OpenAI, Together.ai, etc.)
- **Pros**: Best accuracy, no local compute needed
- **Cons**: Data leaves your system, requires internet, potential costs

### Option E: Specialized Model (Finance/Crypto Domain)
- Use crypto-trained model (if available)
- **Pros**: Domain-specific accuracy
- **Cons**: Harder to find, may be commercial

---

## 💾 Resource Requirements Comparison

### Current Setup (Gemma 3n)
```
CPU: Intel i5+ / Ryzen 5+
RAM: 8GB minimum (16GB recommended)
GPU: Optional 2GB VRAM (NVIDIA CUDA)
Storage: 5GB for model cache
Inference Time: 1-5 seconds per query
Startup Time: 10-30 seconds (model load)
```

### Lighter Alternative (Mistral 7B or Phi 3)
```
CPU: Intel i5+ / Ryzen 5+
RAM: 6GB minimum (10GB recommended)
GPU: Optional 2GB VRAM
Storage: 3-4GB for model cache
Inference Time: 1-3 seconds per query
Startup Time: 5-15 seconds
```

### Very Lightweight (TinyLLaMA 1.1B)
```
CPU: Intel i3+ / Ryzen 3+
RAM: 4GB minimum
GPU: Not needed
Storage: 1GB
Inference Time: 0.5-2 seconds per query
Startup Time: 2-5 seconds
CAVEAT: Significantly reduced NLP accuracy
```

---

## 🎁 What Can Be Removed?

If you want to use a lighter model:

1. **Keep these (essential)**:
   - Anomaly Detection (no model needed)
   - Fraud Detection (heuristic works)
   - Pattern Learning (statistical works)
   - Analytics Dashboard (no model needed)

2. **Can downgrade**:
   - Natural Language Search → Regex-based (loses semantic understanding)
   - Smart Descriptions → Template-based (loses creativity)

3. **Could remove entirely**:
   - AML Detection (optional compliance feature)
   - Advanced DeFi Classification (basic classification sufficient)

---

## 🔄 Switching Models

### To use a different model:

1. **Edit** `config.json`:
   ```json
   {
     "ml_fallback": {
       "model_name": "mistral",  // Change to your model
       "enabled": true
     }
   }
   ```

2. **Update** `src/core/ml_service.py` to load new model:
   ```python
   if model_name == "mistral":
       # Load from Hugging Face
       from transformers import AutoModelForCausalLM, AutoTokenizer
       model = AutoModelForCausalLM.from_pretrained("mistralai/Mistral-7B")
   ```

3. **Test** with simplified queries first

---

## 📝 Recommendation

**Keep Gemma 3n if:**
- You want best accuracy for all AI features
- You have 16GB+ RAM available
- You value complex NLP query handling
- You need creative transaction descriptions

**Switch to lighter model if:**
- You only care about anomaly/fraud detection
- You have limited RAM (4-8GB)
- You don't need natural language search
- You want faster inference (< 2 seconds)

**Suggested Lightweight Alternative:**
- **Mistral 7B** - Best balance of speed/accuracy (1-3x faster than Gemma 3n, nearly as good)
- **Phi 3** - Highly optimized, 2-3x faster, smaller model size

---

## 📞 Questions to Help Choose?

1. What's your target RAM/CPU/GPU configuration?
2. Do you need the NLP search feature, or just anomaly/fraud detection?
3. How important is inference speed?
4. Do you want to keep everything on your machine (no external APIs)?
5. Is model size/startup time critical for your use case?

Let me know if you'd like me to help integrate a different model!
