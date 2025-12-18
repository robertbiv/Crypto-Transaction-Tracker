# AI/ML Settings Clarity Update

## Summary
Refactored the AI/ML configuration to make it clear that users have three distinct strategies to choose from, rather than independent toggles that could be confusing.

## Changes Made

### 1. **config.html** - Replaced confusing separate toggles with radio button strategy selector

#### Before:
- Checkbox: "Enable Gemma-powered ML suggestions" 
- Checkbox: "Enable Accuracy Mode"
- Sub-checkboxes that were disabled/enabled based on master toggle
- Unclear relationship between ML Fallback and Accuracy Mode

#### After:
- Radio button group: "🤖 AI/ML Strategy" with three clear options:
  1. **❌ None (Deterministic Rules Only)**
     - Use only built-in classification rules
     - No AI/ML models
     - Fastest but may have unclassified transactions
  
  2. **✨ ML Fallback Only (Gemma 3n)**
     - When rules cannot classify a transaction, Gemma AI suggests a classification
     - Good balance of accuracy and speed
     - Model runs locally
  
  3. **🎯 Accuracy Mode (Full Enhancement)**
     - ML Fallback + Fraud Detection + Smart Descriptions + Pattern Learning + NLS
     - Best accuracy, requires more resources

#### Dynamic UI:
- Confidence threshold control appears only when ML mode or Accuracy Mode is selected
- Accuracy Mode feature checkboxes (fraud detection, smart descriptions, etc.) appear only when Accuracy Mode is selected
- Sub-features are automatically enabled/disabled based on selected strategy

### 2. **config.json** - Updated documentation to clarify the three modes

```json
"ml_fallback": {
    "_INSTRUCTIONS": "AI/ML Strategy. Three modes: (1) None: Deterministic rules only, fast, may have unclassified transactions. (2) ML Fallback: When rules cannot classify, Gemma AI suggests classification. (3) Accuracy Mode: ML Fallback + Fraud Detection + Smart Descriptions + Pattern Learning + NLS. enabled=True activates ML-based mode. confidence_threshold (0.0-1.0, default=0.85) filters low-confidence suggestions."
},
"accuracy_mode": {
    "_INSTRUCTIONS": "Enhanced accuracy features requiring ML enabled. enabled=True adds fraud detection, smart descriptions, pattern learning, and NLS on top of ML fallback. If enabled=False and ml_fallback.enabled=True, runs in ML Fallback mode only. If both False, uses deterministic rules only."
}
```

### 3. **JavaScript Logic Updates**

#### New function: `updateAIStrategyUI()`
- Monitors the selected AI strategy radio button
- Shows/hides ML options container based on selection
- Shows/hides Accuracy Mode options based on selection
- Enables/disables accuracy sub-feature checkboxes

#### Updated config loading: `loadGeneralConfig()`
- Determines which strategy is active by checking config state
- Sets the appropriate radio button based on:
  - `accuracy_mode.enabled === true` → Select "Accuracy Mode"
  - `ml_fallback.enabled === true` → Select "ML Fallback Only"
  - Both false → Select "None"

#### Updated form submission: `generalConfigForm`
- Reads selected AI strategy radio button
- Sets `ml_fallback.enabled` based on strategy choice
- Sets `accuracy_mode.enabled` based on strategy choice
- Ensures consistency in the saved config

## Benefits

1. **Clarity**: Users immediately understand they have three distinct choices
2. **Reduced Confusion**: No more wondering which toggles to enable/disable
3. **Progressive Disclosure**: Only relevant options appear based on selection
4. **Automatic Consistency**: Config is always in a valid state (no broken combinations)
5. **Better Documentation**: Instructions in config.json clearly explain each mode

## User Experience

When a user loads the config page:
1. Current strategy is automatically selected based on their config
2. Only relevant options are visible
3. Moving between strategies automatically shows/hides appropriate controls
4. System requirements info remains visible for context
5. Saving works seamlessly with no validation errors

## Backward Compatibility

The system maintains backward compatibility with existing configs:
- Old configs with `ml_fallback.enabled: true` and `accuracy_mode.enabled: false` → "ML Fallback Only" mode
- Old configs with both enabled → "Accuracy Mode"
- Old configs with both disabled → "None"
