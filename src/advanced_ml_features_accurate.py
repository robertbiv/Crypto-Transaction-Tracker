"""
Advanced ML Features - Accuracy Mode with TinyLLaMA Integration
Uses TinyLLaMA model for enhanced accuracy on fraud detection, descriptions, patterns, and NLS.
Falls back to heuristics if model is unavailable or disabled.

Features:
    - FraudDetectorAccurate: Context-aware fraud detection via TinyLLaMA
    - SmartDescriptionGeneratorAccurate: Creative descriptions via TinyLLaMA
    - PatternLearnerAccurate: Behavioral pattern analysis via TinyLLaMA
    - NaturalLanguageSearchAccurate: True NLP via TinyLLaMA

Author: robertbiv
Last Modified: December 2025
"""

import json
import hashlib
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from src.advanced_ml_features import (
    FraudDetector, SmartDescriptionGenerator, PatternLearner, NaturalLanguageSearch
)


class FraudDetectorAccurate:
    """Context-aware fraud detection using TinyLLaMA + heuristics"""
    
    def __init__(self, ml_service=None):
        self.ml_service = ml_service
        self.fallback = FraudDetector()
    
    def detect_fraud_comprehensive(self, transactions: List[Dict]) -> Dict:
        """
        Detect all fraud types with Gemma analysis for accuracy
        Returns detailed fraud analysis with confidence scores
        """
        
        # Start with fast heuristic detections
        results = {
            'wash_sales': self.fallback.detect_wash_sale(transactions),
            'pump_dumps': self.fallback.detect_pump_dump(transactions),
            'suspicious_volumes': self.fallback.detect_suspicious_volume(transactions),
            'gemma_analysis': None,
            'use_gemma': bool(self.ml_service)
        }
        
        # Enhance with Gemma analysis if available
        if self.ml_service:
            try:
                gemma_findings = self._analyze_with_gemma(transactions)
                results['gemma_analysis'] = gemma_findings
                
                # Merge Gemma insights with heuristic findings
                if gemma_findings.get('additional_wash_sales'):
                    results['wash_sales'].extend(gemma_findings['additional_wash_sales'])
                if gemma_findings.get('contextual_flags'):
                    results['contextual_flags'] = gemma_findings['contextual_flags']
                
            except Exception as e:
                print(f"Gemma analysis failed, using heuristics only: {e}")
        
        return results
    
    def _analyze_with_gemma(self, transactions: List[Dict]) -> Dict:
        """Run Gemma analysis on transactions for context-aware fraud detection"""
        
        # Prepare transaction summary for Gemma
        tx_summary = self._prepare_summary(transactions)
        
        prompt = f"""
Analyze these crypto transactions for fraud patterns and suspicious activity.
Focus on: wash sales, pump & dumps, structuring, timing anomalies.

Transactions:
{tx_summary}

Return JSON with:
{{
    "wash_sales": [...],
    "contextual_flags": [...],
    "confidence": 0-1,
    "explanation": "..."
}}
"""
        
        try:
            response = self.ml_service.infer(prompt)
            # Parse Gemma response
            result = json.loads(response)
            return result
        except:
            return {'confidence': 0, 'contextual_flags': []}
    
    def _prepare_summary(self, transactions: List[Dict]) -> str:
        """Prepare transaction data for Gemma analysis"""
        summary = []
        for tx in transactions[:20]:  # Limit to first 20 for context window
            summary.append(
                f"- {tx.get('date', 'N/A')}: {tx.get('action', '')} "
                f"{tx.get('amount', 0)} {tx.get('coin', '')} @ ${tx.get('price_usd', 0)}"
            )
        return '\n'.join(summary)


class SmartDescriptionGeneratorAccurate:
    """Creative, context-aware descriptions using TinyLLaMA + heuristics"""
    
    def __init__(self, ml_service=None):
        self.ml_service = ml_service
        self.fallback = SmartDescriptionGenerator()
    
    def generate_description_smart(self, tx: Dict, context_txs: Optional[List[Dict]] = None) -> Dict:
        """
        Generate intelligent description with Gemma for accuracy
        Returns: {description, confidence, source}
        """
        
        # Fast heuristic version
        heuristic_desc = self.fallback.generate_description(tx)
        
        # If no Gemma, return heuristic
        if not self.ml_service:
            return {
                'description': heuristic_desc,
                'confidence': 0.6,
                'source': 'heuristic'
            }
        
        # Enhance with Gemma
        try:
            gemma_desc = self._generate_with_gemma(tx, context_txs)
            return {
                'description': gemma_desc['description'],
                'confidence': gemma_desc.get('confidence', 0.9),
                'source': 'gemma',
                'heuristic_fallback': heuristic_desc
            }
        except Exception as e:
            print(f"Gemma description failed: {e}")
            return {
                'description': heuristic_desc,
                'confidence': 0.6,
                'source': 'heuristic'
            }
    
    def _generate_with_gemma(self, tx: Dict, context_txs: Optional[List[Dict]] = None) -> Dict:
        """Use Gemma to generate creative, contextual description"""
        
        context = ""
        if context_txs:
            recent_actions = [t.get('action', '').upper() for t in context_txs[-5:]]
            context = f"Recent actions: {', '.join(recent_actions)}"
        
        prompt = f"""
Generate a brief, specific transaction description:

Transaction: {tx.get('action', 'Unknown')} {tx.get('amount', 0)} {tx.get('coin', '')} @ ${tx.get('price_usd', 0)}
Date: {tx.get('date', '')}
Source: {tx.get('source', '')}
{context}

Be specific and brief (under 50 chars). Return JSON: {{"description": "..."}}
"""
        
        try:
            response = self.ml_service.infer(prompt)
            result = json.loads(response)
            return result
        except:
            return {'description': '', 'confidence': 0}


class PatternLearnerAccurate:
    """Behavioral pattern learning using TinyLLaMA + statistical analysis"""
    
    def __init__(self, ml_service=None):
        self.ml_service = ml_service
        self.fallback = PatternLearner()
    
    def learn_and_detect_accurate(self, transactions: List[Dict]) -> Dict:
        """
        Learn user patterns and detect anomalies with Gemma context
        Returns: {patterns, anomalies, confidence}
        """
        
        # Statistical baseline
        self.fallback.learn_patterns(transactions)
        
        results = {
            'statistical_anomalies': [],
            'behavioral_anomalies': [],
            'use_gemma': bool(self.ml_service)
        }
        
        # Statistical detection
        for tx in transactions:
            anomaly_list = self.fallback.detect_anomalies(tx)
            if anomaly_list:
                results['statistical_anomalies'].extend(anomaly_list)
        
        # Gemma behavioral analysis
        if self.ml_service:
            try:
                behavioral = self._analyze_behavior_with_gemma(transactions)
                results['behavioral_anomalies'] = behavioral.get('anomalies', [])
                results['user_profile'] = behavioral.get('user_profile', {})
            except Exception as e:
                print(f"Gemma behavioral analysis failed: {e}")
        
        return results
    
    def _analyze_behavior_with_gemma(self, transactions: List[Dict]) -> Dict:
        """Analyze user's trading behavior patterns"""
        
        # Aggregate statistics
        stats = self._get_transaction_stats(transactions)
        
        prompt = f"""
Analyze this user's crypto trading behavior for anomalies:

Statistics:
- Total transactions: {stats['total']}
- Favorite coins: {', '.join(stats['top_coins'])}
- Average trade size: ${stats['avg_size']:,.0f}
- Most common action: {stats['common_action']}
- Trading frequency: {stats['frequency']}

Identify behavioral anomalies (unusual patterns for THIS user).
Return JSON: {{
    "user_profile": {{"profile": "...", "risk_level": "..."}},
    "anomalies": [...]
}}
"""
        
        try:
            response = self.ml_service.infer(prompt)
            result = json.loads(response)
            return result
        except:
            return {'anomalies': [], 'user_profile': {}}
    
    def _get_transaction_stats(self, transactions: List[Dict]) -> Dict:
        """Calculate transaction statistics"""
        if not transactions:
            return {
                'total': 0, 'top_coins': [], 'avg_size': 0,
                'common_action': 'UNKNOWN', 'frequency': 'LOW'
            }
        
        amounts = [float(t.get('amount', 0)) for t in transactions if t.get('amount')]
        actions = [t.get('action', '').upper() for t in transactions]
        coins = [t.get('coin', '') for t in transactions]
        
        # Most common coin
        coin_counts = defaultdict(int)
        for coin in coins:
            coin_counts[coin] += 1
        top_coins = [coin for coin, _ in sorted(coin_counts.items(), key=lambda x: x[1], reverse=True)[:3]]
        
        # Most common action
        action_counts = defaultdict(int)
        for action in actions:
            action_counts[action] += 1
        common_action = max(action_counts.items(), key=lambda x: x[1])[0] if action_counts else 'UNKNOWN'
        
        # Frequency
        days_span = (datetime.now() - datetime.fromisoformat(transactions[0].get('date', ''))).days if transactions else 1
        frequency = 'HIGH' if len(transactions) > (days_span / 7) else 'MEDIUM' if days_span > 30 else 'LOW'
        
        return {
            'total': len(transactions),
            'top_coins': top_coins,
            'avg_size': sum(amounts) / len(amounts) if amounts else 0,
            'common_action': common_action,
            'frequency': frequency
        }


class NaturalLanguageSearchAccurate:
    """True NLP search using TinyLLaMA + regex fallback"""
    
    def __init__(self, ml_service=None):
        self.ml_service = ml_service
        self.fallback = NaturalLanguageSearch()
    
    def search_accurate(self, transactions: List[Dict], query: str) -> Dict:
        """
        Search transactions with NLP understanding
        Returns: {results, interpretation, confidence}
        """
        
        # Fast regex-based search
        regex_results = self.fallback.search(transactions, query)
        
        results = {
            'results': regex_results,
            'interpretation': query,
            'confidence': 0.6,
            'use_gemma': bool(self.ml_service)
        }
        
        # Gemma NLP understanding
        if self.ml_service:
            try:
                nlp_result = self._search_with_gemma(transactions, query)
                results['results'] = nlp_result['results']
                results['interpretation'] = nlp_result['interpretation']
                results['confidence'] = nlp_result.get('confidence', 0.9)
                results['source'] = 'gemma'
            except Exception as e:
                print(f"Gemma NLP search failed: {e}")
                results['source'] = 'regex'
        else:
            results['source'] = 'regex'
        
        return results
    
    def _search_with_gemma(self, transactions: List[Dict], query: str) -> Dict:
        """Use Gemma for semantic search understanding"""
        
        # Prepare transaction list
        tx_list = json.dumps([
            {
                'id': t['id'],
                'date': t.get('date'),
                'action': t.get('action'),
                'coin': t.get('coin'),
                'amount': float(t.get('amount', 0)),
                'price': float(t.get('price_usd', 0))
            }
            for t in transactions
        ], indent=2)
        
        prompt = f"""
Search these crypto transactions based on the user's query.

Query: "{query}"

Transactions (JSON):
{tx_list}

Return JSON: {{
    "interpretation": "what the user is looking for",
    "results": [{{id: ..., reason: "why this matches"}}],
    "confidence": 0-1
}}
"""
        
        try:
            response = self.ml_service.infer(prompt)
            result = json.loads(response)
            
            # Map results back to full transaction objects
            result_ids = [r['id'] for r in result.get('results', [])]
            result['results'] = [t for t in transactions if t['id'] in result_ids]
            
            return result
        except:
            return {'results': [], 'interpretation': query, 'confidence': 0}


class AccuracyModeController:
    """Unified controller for accuracy mode - switches between heuristic and Gemma"""
    
    def __init__(self, ml_service=None, enabled: bool = True):
        self.ml_service = ml_service
        self.enabled = enabled
        
        # Initialize both versions
        self.fraud_accurate = FraudDetectorAccurate(ml_service)
        self.fraud_fast = FraudDetector()
        
        self.desc_accurate = SmartDescriptionGeneratorAccurate(ml_service)
        self.desc_fast = SmartDescriptionGenerator()
        
        self.pattern_accurate = PatternLearnerAccurate(ml_service)
        self.pattern_fast = PatternLearner()
        
        self.search_accurate = NaturalLanguageSearchAccurate(ml_service)
        self.search_fast = NaturalLanguageSearch()
    
    def detect_fraud(self, transactions: List[Dict], mode: str = 'accurate') -> Dict:
        """Detect fraud with user's preferred mode"""
        if mode == 'accurate' and self.enabled:
            return self.fraud_accurate.detect_fraud_comprehensive(transactions)
        else:
            return self.fraud_fast.detect_suspicious_volume(transactions)
    
    def generate_description(self, tx: Dict, context_txs: Optional[List[Dict]] = None, mode: str = 'accurate') -> Dict:
        """Generate description with user's preferred mode"""
        if mode == 'accurate' and self.enabled:
            return self.desc_accurate.generate_description_smart(tx, context_txs)
        else:
            return {'description': self.desc_fast.generate_description(tx), 'source': 'heuristic'}
    
    def analyze_patterns(self, transactions: List[Dict], mode: str = 'accurate') -> Dict:
        """Analyze patterns with user's preferred mode"""
        if mode == 'accurate' and self.enabled:
            return self.pattern_accurate.learn_and_detect_accurate(transactions)
        else:
            return {'anomalies': []}
    
    def search_transactions(self, transactions: List[Dict], query: str, mode: str = 'accurate') -> Dict:
        """Search transactions with user's preferred mode"""
        if mode == 'accurate' and self.enabled:
            return self.search_accurate.search_accurate(transactions, query)
        else:
            return {'results': self.search_fast.search(transactions, query), 'source': 'regex'}
