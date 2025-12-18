"""
Accuracy Mode Documentation
User Control: Fast vs. Accurate ML Analysis

==============================================================================
OVERVIEW
==============================================================================

The system now offers TWO MODES for each advanced ML feature:

1. FAST MODE (Heuristics)
   - Instant results (no Gemma inference)
   - Rule-based: fixed thresholds, regex patterns
   - Always available, no ML required
   - Best for: Quick scanning, high volume

2. ACCURATE MODE (Gemma-Enhanced)
   - Uses Gemma model for semantic understanding
   - Context-aware analysis, behavioral learning
   - Better accuracy, slower (2-5 sec/batch)
   - Best for: Deep analysis, final review
   - Requires: ML enabled in config

==============================================================================
CONFIGURATION
==============================================================================

In configs/config.json:

{
  "ml_fallback": {
    "enabled": true,          // Master ML toggle
    "model_name": "gemma",    // Which model to use
    "confidence_threshold": 0.85
  },
  
  "accuracy_mode": {
    "enabled": true,          // Use Gemma when available
    "fraud_detection": true,    // Context-aware fraud analysis
    "smart_descriptions": true, // Creative transaction descriptions
    "pattern_learning": true,   // Behavioral anomaly detection
    "natural_language_search": true, // True NLP queries
    "fallback_on_error": true   // Fall back to heuristics if Gemma fails
  }
}

User Settings:
- Set accuracy_mode.enabled=false to disable Gemma (uses heuristics only)
- Individual features can be toggled (if smart_descriptions=false, uses heuristics)
- Graceful fallback: if Gemma unavailable, automatically uses heuristics

==============================================================================
API ENDPOINTS
==============================================================================

For each feature, endpoints now support mode parameter:

POST /api/advanced/fraud-detection
Body: {"mode": "accurate" or "fast"}
Returns: {wash_sales, pump_dumps, suspicious_volumes, gemma_analysis, use_gemma}

POST /api/advanced/smart-descriptions
Body: {"mode": "accurate" or "fast"}
Returns: {descriptions: [{id, suggested, confidence, source}]}

POST /api/advanced/pattern-analysis
Body: {"mode": "accurate" or "fast"}
Returns: {statistical_anomalies, behavioral_anomalies, user_profile}

POST /api/advanced/search
Body: {"query": "...", "mode": "accurate" or "fast"}
Returns: {results, interpretation, confidence, source}

Default: mode="accurate" (if enabled in config)
Fallback: automatically uses "fast" mode if Gemma unavailable

==============================================================================
FEATURES BREAKDOWN
==============================================================================

FRAUD DETECTION
===============
Fast Mode (Heuristics):
  - Wash sales: buy then sell same coin within 30 days
  - Pump & dump: >50% price change between buy/sell
  - Suspicious volume: >5x average transaction
  - Instant results, no false positives

Accurate Mode (Gemma):
  - Context awareness: understands market conditions
  - Timing analysis: suspicious patterns in transaction flow
  - Correlations: links multiple transactions
  - Returns confidence scores
  - Example: Detects "bought at ATH, sold immediately" pattern


SMART DESCRIPTIONS
===================
Fast Mode (Heuristics):
  - Template-based: "Purchased 1.5 BTC @ $42,000"
  - DeFi keyword matching
  - Instant, always available

Accurate Mode (Gemma):
  - Creative: "Sold on relief bounce after 10% dip"
  - Context-aware: understands transaction sequence
  - Better readability for reviews
  - Returns confidence score
  - Example: "Strategic partial take-profit on strong close"


PATTERN LEARNING
=================
Fast Mode (Heuristics):
  - Statistical: 3x average amount = anomaly
  - Simple rules: "new exchange, unusual coin"
  - Fast aggregation

Accurate Mode (Gemma):
  - Behavioral analysis: learns user's actual patterns
  - User profiling: "conservative", "aggressive", "diversified"
  - Intelligent anomalies: understands context
  - Returns user_profile and behavioral_anomalies
  - Example: For user who always buys dips, large purchase not anomaly


NATURAL LANGUAGE SEARCH
========================
Fast Mode (Heuristics):
  - Regex-based parsing
  - "Show BTC transactions" -> coin=BTC
  - Limited query complexity

Accurate Mode (Gemma):
  - True NLP understanding
  - "Show my biggest losses in Q4" -> action=SELL, metric=loss, quarter=Q4
  - Complex query interpretation
  - Returns interpretation and confidence
  - Example: Understands "when I bought dips and made >50% ROI"

==============================================================================
USAGE EXAMPLES
==============================================================================

PYTHON CODE:
from src.advanced_ml_features_accurate import AccuracyModeController
from src.ml_service import MLService

# Initialize with Gemma
ml_service = MLService(mode='gemma')
controller = AccuracyModeController(ml_service=ml_service, enabled=True)

# Get comprehensive fraud analysis
fraud_result = controller.detect_fraud(transactions, mode='accurate')
# Returns: {wash_sales, pump_dumps, suspicious_volumes, gemma_analysis, use_gemma}

# Quick fraud check (no waiting for Gemma)
fraud_quick = controller.detect_fraud(transactions, mode='fast')
# Returns: {suspicious_volume: [...]}

# Fallback behavior (config-driven)
if not config.get('accuracy_mode', {}).get('enabled'):
    result = controller.detect_fraud(transactions, mode='fast')
else:
    result = controller.detect_fraud(transactions, mode='accurate')


WEB UI INTEGRATION:
User selects mode on UI:
  ☐ Fast Mode (instant)
  ☑ Accurate Mode (Gemma-enhanced) [Recommended]

Button: "Analyze Fraud Patterns"
  - If Accurate Mode: shows loading, calls Gemma, displays confidence
  - If Fast Mode: instant results
  - If Gemma fails: auto-falls back to Fast Mode with notification


==============================================================================
PERFORMANCE NOTES
==============================================================================

Fast Mode (Heuristics):
  - 100 transactions: ~10ms
  - 10,000 transactions: ~100ms
  - Always available, no dependencies

Accurate Mode (Gemma):
  - 100 transactions: ~2-3 seconds
  - 1,000 transactions: ~10-15 seconds (batch processing)
  - Requires Gemma model (2GB GPU/CPU)
  - Auto-shutdown after batch to free memory

Recommendation:
  - Use Fast Mode for: quick reviews, high volume processing
  - Use Accurate Mode for: final review, anomaly investigation, complex queries
  - Hybrid: Auto-toggle based on number of transactions

==============================================================================
ERROR HANDLING
==============================================================================

If Gemma unavailable:
  - Automatic fallback to heuristics (if fallback_on_error=true)
  - User sees notification: "Gemma unavailable, using fast analysis"
  - Results still accurate, just less detailed

If Gemma fails mid-batch:
  - Returns partial results with successful items
  - Logs error with transaction IDs
  - Suggests retry or using fast mode

User disables Accuracy Mode:
  - Config: accuracy_mode.enabled=false
  - All features use heuristics immediately
  - No model loading/GPU usage
  - Minimal memory footprint

==============================================================================
RECOMMENDATION FOR USERS
==============================================================================

Recommended Setup:
1. Enable ML: ml_fallback.enabled=true
2. Enable Accuracy: accuracy_mode.enabled=true (default)
3. Let Gemma optimize based on workload:
   - Small batches (<100 txs): accurate mode
   - Large batches (>1000 txs): fast mode (or batch them)

For Privacy-Conscious Users:
  - Disable Accuracy Mode: accuracy_mode.enabled=false
  - System uses fast heuristics only, no model inference
  - All data stays local (Gemma runs locally)

For Performance-First Users:
  - Disable Accuracy Mode: accuracy_mode.enabled=false
  - Instant results, minimal CPU/GPU usage
  - Still get all basic fraud detection and anomalies

For Accuracy-First Users (Recommended):
  - Enable both: ML enabled, Accuracy mode enabled
  - Use Accurate mode for detailed analysis
  - Fall back to Fast mode for quick checks
  - Get Gemma's contextual understanding

==============================================================================
TESTING
==============================================================================

Test Suite: tests/test_accuracy_mode.py (21 tests)
  - Tests both modes for each feature
  - Verifies fallback behavior
  - Tests config integration
  - Mock Gemma testing (without real model)

Run Tests:
  pytest tests/test_accuracy_mode.py -v

All tests verify:
  ✓ Fast mode works without ML
  ✓ Accurate mode works with ML
  ✓ Fallback triggers on errors
  ✓ Config is respected
  ✓ Results are returned correctly

==============================================================================
"""
