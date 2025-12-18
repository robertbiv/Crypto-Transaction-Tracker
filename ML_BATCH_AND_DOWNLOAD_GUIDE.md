# Batch Size & Model Download Guide

## Question 1: How to Reduce Batch Size for Users

### Current State
The reprocess endpoint currently processes transactions in a **single pass** (no batching). Each transaction is:
1. Loaded from database
2. Sent to ML service one-by-one
3. Updated in database if changed

**For batch size control**, we can add two settings:

### Option A: Batch Processing Size (Recommended)
Add a user-configurable batch size that processes N transactions at a time before freeing memory/checkpointing:

```json
"ml_fallback": {
    "batch_size": 10,  // Process 10 transactions, checkpoint, then 10 more
    "checkpoint_memory_clear": true  // Clear intermediate memory after each batch
}
```

**Benefits:**
- Reduces peak memory usage
- Allows checkpointing (user can pause/resume)
- Lets users adjust based on their system RAM

### Option B: Progressive Inference Delay
Add delay between transactions to reduce resource spike:

```json
"ml_fallback": {
    "inference_delay_ms": 100,  // 100ms between inferences
    "max_parallel_inferences": 1  // Only 1 at a time
}
```

### Implementation (What We Should Do)

**In config.json:**
```json
"ml_fallback": {
    "_SETTING_batch_size": "Number of transactions to process before memory checkpoint. Lower = less memory usage but slower. Default: 10. Try 5 for systems with <8GB RAM, or 20+ for systems with 16GB+.",
    "batch_size": 10
}
```

**In web UI (config.html):**
Add slider: "ML Batch Size" (1-50 transactions per batch)
- Tooltip: "Lower values = less memory usage"
- Shows estimated memory impact

**In reprocess endpoint (web_server.py):**
```python
batch_size = ml_config.get('batch_size', 10)
for i in range(0, len(transactions), batch_size):
    batch = transactions[i:i+batch_size]
    for tx in batch:
        # process transaction
    if ml_config.get('checkpoint_memory', True):
        gc.collect()  # Force garbage collection after batch
```

---

## Question 2: Model Download Behavior

### **Model Downloads ONLY on First Use (Lazy Loading)**

**Timeline:**
1. **Settings Changed to `model_name: "gemma"`** → No download yet
2. **First Reprocess Click** → Downloads start
3. **First Transaction Processed** → Model loaded into memory
4. **Subsequent Transactions** → Reuse loaded model

### **Where/When Downloads Happen**

1. **Automatic Download Trigger:**
   ```python
   # In MLService._load_model()
   from transformers import pipeline  # Downloads model on import
   
   # First call to suggest() → _load_model() called
   # HuggingFace library downloads to ~/.cache/huggingface/hub/
   ```

2. **What Gets Downloaded:**
   - Model weights: `google/gemma-2b-it` (~2GB for default model)
   - Tokenizer files: (~100MB)
   - Config files: (~50MB)
   - **Total: ~2-5GB** depending on model variant

3. **Where It's Stored:**
   - Linux/Mac: `~/.cache/huggingface/hub/`
   - Windows: `C:\Users\<username>\.cache\huggingface\hub\`
   - Can override: `HF_HOME` environment variable

### **Dependencies Installation**

When user sets `model_name: "gemma"` but dependencies missing:

**Current Flow:**
1. User clicks "Reprocess All with ML"
2. System tries `from transformers import pipeline`
3. ImportError → Falls back to "shim" mode with warning
4. Warning shows: `pip install torch transformers`

**Better Flow (What We Should Add):**

Add endpoint: `/api/ml/check-dependencies` that returns:
```json
{
    "torch_installed": false,
    "transformers_installed": false,
    "model_name": "gemma-2b-it",
    "estimated_download_size": "2-5GB",
    "cache_location": "C:\\Users\\yoshi\\.cache\\huggingface\\hub\\",
    "install_command": "pip install torch transformers",
    "notes": "First run will download ~2-5GB. Requires internet connection."
}
```

### **Suggested UI Improvements**

**In Config Page, when `model_name="gemma"`:**
1. Show status banner: ⚠️ "Gemma model not yet downloaded"
2. Add button: "🔍 Check Dependencies & Cache"
3. Shows:
   - ✅ or ❌ for torch, transformers
   - Download size needed
   - Cache location
4. When first "Reprocess" is clicked:
   - Show progress: "Downloading model (2-5GB)... 25%"
   - Can cancel
   - Logs downloading files to outputs/logs/ml_download.log

---

## Summary

| Question | Answer |
|----------|--------|
| **Reduce Batch Size?** | Add `batch_size` config (default 10). Lower = less RAM. Add UI slider for easy adjustment. |
| **Auto Download?** | NO - only on first use (lazy loading). Download happens when first reprocess is clicked. |
| **When to Install Deps?** | Only when user sets `model_name="gemma"` and clicks reprocess. System tries, gives helpful warnings if missing. |
| **Where Does It Go?** | `~/.cache/huggingface/hub/` (~2-5GB). User can override with `HF_HOME` env var. |

