"""Common imports and utilities for all test files"""
import unittest
import shutil
import tempfile
import json
import sqlite3
import pandas as pd
import sys
import os
import random
import math
import importlib
import requests 
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO
from datetime import datetime, timedelta
from decimal import Decimal

# Add parent directory to Python path so we can import the main application modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import application logic
import src.core.engine as app
import src.tools.setup as setup_script
import auto_runner
# Register alias so both `auto_runner` and legacy `Auto_Runner` resolve in tests
sys.modules['Auto_Runner'] = auto_runner
Auto_Runner = auto_runner
from src.tools.review_fixer import InteractiveReviewFixer
from contextlib import redirect_stdout

# Keep a reference to the real price fetcher for test resets
REAL_GET_PRICE = app.PriceFetcher.get_price


# --- SHADOW CALCULATOR (Standard FIFO) ---
class ShadowFIFO:
    def __init__(self):
        self.queues = {}
        self.realized_gains = []
        self.income_log = []
    
    def add(self, coin, amount, price, date, is_income=False):
        if coin not in self.queues: 
            self.queues[coin] = []
        self.queues[coin].append({'amt': amount, 'price': price, 'date': date})
        self.queues[coin].sort(key=lambda x: x['date'])
        if is_income: 
            self.income_log.append({'coin': coin, 'amt': amount, 'usd': amount * price, 'date': date})
    
    def sell(self, coin, amount, price, date, fee=0):
        if coin not in self.queues: 
            self.queues[coin] = []
        rem_sell = amount
        total_basis = 0.0
        self.queues[coin].sort(key=lambda x: x['date'])
        valid_batches = [b for b in self.queues[coin] if b['date'] <= date]
        future_batches = [b for b in self.queues[coin] if b['date'] > date]
        self.queues[coin] = valid_batches
        while rem_sell > 1e-9 and self.queues[coin]:
            batch = self.queues[coin][0]
            if batch['amt'] <= rem_sell:
                total_basis += batch['amt'] * batch['price']
                rem_sell -= batch['amt']
                self.queues[coin].pop(0)
            else:
                total_basis += rem_sell * batch['price']
                batch['amt'] -= rem_sell
                rem_sell = 0
        self.queues[coin].extend(future_batches)
        self.queues[coin].sort(key=lambda x: x['date'])
        proceeds = (amount * price) - fee
        gain = proceeds - total_basis
        self.realized_gains.append({
            'coin': coin, 
            'proceeds': proceeds, 
            'basis': total_basis, 
            'gain': gain, 
            'date': date
        })


