"""Lightweight ML service with optional real TinyLLaMA model support.

This module provides classification for crypto transactions. It can run in two modes:
1. Shim mode: keyword heuristics (fast, no dependencies)
2. Real mode: TinyLLaMA 1.1B or similar small local model (accurate, requires transformers)

Usage:
    # Shim mode (default, no extra deps)
    svc = MLService(mode="shim")
    
    # Real mode (requires: pip install torch transformers)
    svc = MLService(mode="tinyllama", auto_shutdown_after_inference=True)
    svc.suggest(tx)  # First inference loads model
    svc.shutdown()   # Free memory after use

Environment:
    ML_MODEL_NAME: Override model (default: "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF")
    ML_DEVICE: "cpu" or "cuda" (default: auto-detect)
"""
import os
import sys
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MLService:
    def __init__(self, mode: str = "shim", auto_shutdown_after_inference: bool = False):
        """Initialize ML service.
        
        Args:
            mode: "shim" (keywords) or "tinyllama" (real model)
            auto_shutdown_after_inference: if True, model unloads after each suggest()
        """
        self.mode = mode
        self.auto_shutdown = auto_shutdown_after_inference
        self.model = None
        self.tokenizer = None
        self.device = None
        self.pipe = None
        self._use_count = 0

    def _load_model(self):
        """Load real model on first use (lazy loading) with recovery attempts."""
        if self.model is not None:
            return  # Already loaded

        if self.mode != "tinyllama":
            return

        try:
            import torch
            from transformers import pipeline

            # Auto-detect device
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"[ML] Loading Gemma model on {self.device}...")

            model_name = os.environ.get("ML_MODEL_NAME", "google/gemma-2b-it")
            
            # Create text-generation pipeline with quantization for lower memory
            self.pipe = pipeline(
                "text-generation",
                model=model_name,
                device=0 if self.device == "cuda" else -1,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                model_kwargs={"quantization_config": self._get_quantization_config()},
            )
            logger.info(f"[ML] Model loaded: {model_name}")
        except ImportError as e:
            logger.warning(f"[ML] ⚠️  Missing dependencies: {e}")
            logger.warning(f"[ML] 💡 Install with: pip install torch transformers")
            logger.warning(f"[ML] → Falling back to lightweight 'shim' mode (keyword-based ML)")
            self.mode = "shim"
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.warning(f"[ML] ⚠️  Out of memory when loading model: {e}")
                logger.warning(f"[ML] 💡 Try: (1) Increase system RAM, (2) Use 'shim' mode in config, or (3) Enable auto_shutdown_after_batch")
                logger.warning(f"[ML] → Falling back to lightweight 'shim' mode")
            else:
                logger.warning(f"[ML] ⚠️  Runtime error loading model: {e}")
                logger.warning(f"[ML] → Falling back to lightweight 'shim' mode")
            self.mode = "shim"
        except Exception as e:
            logger.warning(f"[ML] ⚠️  Failed to load Gemma model: {e}")
            logger.warning(f"[ML] 💡 Check: (1) Model name is correct, (2) Internet connection (first download), (3) Disk space for cache (~5GB)")
            logger.warning(f"[ML] → Falling back to lightweight 'shim' mode (keyword-based ML)")
            self.mode = "shim"

    def _get_quantization_config(self):
        """Get quantization config for memory efficiency."""
        try:
            from transformers import BitsAndBytesConfig
            return BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_threshold=6.0,
            )
        except Exception:
            return None

    def suggest(self, tx: Dict) -> Dict:
        """Return a suggestion for a single transaction.

        Output format:
          {
            "suggested_label": str,
            "confidence": float,   # 0..1
            "explanation": str
          }
        """
        if self.mode == "shim":
            return self._suggest_shim(tx)
        elif self.mode == "gemma":
            return self._suggest_gemma(tx)
        else:
            return {"suggested_label": "unknown", "confidence": 0.0, "explanation": "mode not configured"}

    def _suggest_shim(self, tx: Dict) -> Dict:
        """Simple keyword-based heuristics to emulate classification."""
        description = (tx.get("description") or tx.get("memo") or tx.get("note") or "").strip()
        desc = description.lower()

        if any(k in desc for k in ("buy", "bought", "exchange", "trade")):
            return {"suggested_label": "BUY", "confidence": 0.92, "explanation": "description indicates a trade/buy"}
        if any(k in desc for k in ("sell", "sold", "exchanged")):
            return {"suggested_label": "SELL", "confidence": 0.92, "explanation": "description indicates a trade/sell"}
        if any(k in desc for k in ("deposit", "received", "incoming")):
            return {"suggested_label": "DEPOSIT", "confidence": 0.9, "explanation": "description indicates incoming funds"}
        if any(k in desc for k in ("withdraw", "sent", "withdrawal", "to wallet")):
            return {"suggested_label": "WITHDRAWAL", "confidence": 0.9, "explanation": "description indicates outgoing funds"}
        if any(k in desc for k in ("fee", "commission", "service charge")):
            return {"suggested_label": "FEE", "confidence": 0.95, "explanation": "description contains fee keywords"}

        try:
            amount = float(tx.get("amount", 0) or 0)
        except Exception:
            amount = 0

        if amount and abs(amount) < 0.0001:
            return {"suggested_label": "MICRO_TRANSFER", "confidence": 0.7, "explanation": "very small amount"}

        return {"suggested_label": "TRANSFER", "confidence": 0.58, "explanation": "no clear keywords found; fallback to TRANSFER"}

    def _suggest_gemma(self, tx: Dict) -> Dict:
        """Use real Gemma model for classification."""
        self._load_model()
        
        if self.pipe is None:
            # Model failed to load; fall back to shim
            return self._suggest_shim(tx)

        try:
            description = (tx.get("description") or tx.get("memo") or tx.get("note") or "").strip()
            if not description:
                description = "No description"

            # Craft prompt for classification
            prompt = f"""Classify this cryptocurrency transaction into ONE category: BUY, SELL, DEPOSIT, WITHDRAWAL, FEE, INCOME, or TRANSFER.

Description: {description}

Category:"""

            # Generate with strict output
            result = self.pipe(
                prompt,
                max_new_tokens=10,
                temperature=0.1,  # Low temp = more deterministic
                top_p=0.9,
                do_sample=False,
            )

            output_text = result[0]["generated_text"][len(prompt):].strip().upper()
            
            # Parse label (take first word if multiple)
            label = output_text.split()[0] if output_text else "TRANSFER"
            valid_labels = {"BUY", "SELL", "DEPOSIT", "WITHDRAWAL", "FEE", "INCOME", "TRANSFER"}
            if label not in valid_labels:
                label = "TRANSFER"

            self._use_count += 1
            
            # Auto-shutdown after use if configured
            if self.auto_shutdown:
                self.shutdown()

            return {
                "suggested_label": label,
                "confidence": 0.88,  # Gemma confidence is empirical
                "explanation": f"Gemma model classified as {label}"
            }

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.warning(f"[ML] ⚠️  Out of memory during inference: {e}")
                logger.warning(f"[ML] 💡 Try enabling auto_shutdown_after_batch or reducing batch size")
            else:
                logger.warning(f"[ML] ⚠️  Runtime error during inference: {e}")
            logger.warning(f"[ML] → Using lightweight 'shim' mode for this transaction")
            return self._suggest_shim(tx)
        except Exception as e:
            logger.warning(f"[ML] ⚠️  Gemma inference failed: {e}")
            logger.warning(f"[ML] → Using lightweight 'shim' mode for this transaction")
            return self._suggest_shim(tx)

    def shutdown(self):
        """Free model memory."""
        if self.pipe is not None:
            try:
                import torch
                del self.pipe
                torch.cuda.empty_cache() if hasattr(torch, 'cuda') else None
                self.pipe = None
                logger.info("[ML] Model unloaded and memory freed.")
            except Exception as e:
                logger.debug(f"[ML] Shutdown error: {e}")


def simple_demo():
    print("=== Shim Mode ===")
    svc = MLService(mode="shim")
    examples = [
        {"description": "Bought BTC via exchange", "amount": "0.01"},
        {"description": "Withdrawal to external wallet", "amount": "0.5"},
        {"description": "Fee: network fee", "amount": "0.0001"},
        {"description": "Transfer to savings", "amount": "1.2"},
    ]
    for e in examples:
        print(f"{e['description']:40} -> {svc.suggest(e)['suggested_label']}")

    print("\n=== Gemma Mode (if available) ===")
    svc_real = MLService(mode="gemma", auto_shutdown_after_inference=True)
    for e in examples:
        result = svc_real.suggest(e)
        print(f"{e['description']:40} -> {result['suggested_label']} (conf: {result['confidence']:.2f})")


if __name__ == "__main__":
    simple_demo()
