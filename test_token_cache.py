"""
Quick test script to verify automatic token address caching from CoinGecko API
"""

import sys
from pathlib import Path
from Interactive_Review_Fixer import InteractiveReviewFixer
from Crypto_Tax_Engine import DatabaseManager

# Create a temporary database for testing
db = DatabaseManager()
db.db_file = ':memory:'
db.connect()
fixer = InteractiveReviewFixer(db, 2024)

print("=" * 60)
print("Testing Automatic Token Address Caching")
print("=" * 60)

# This will trigger cache fetch if not present/expired
print("\n1. Getting cached token addresses...")
token_map = fixer._get_cached_token_addresses()

if token_map:
    print(f"\n[✓] Success! Retrieved {sum(len(tokens) for tokens in token_map.values())} token addresses")
    print(f"[✓] Covering {len(token_map)} chains: {', '.join(token_map.keys())}")
    
    # Show sample tokens from each chain
    print("\nSample tokens by chain:")
    for chain, tokens in sorted(token_map.items()):
        sample_tokens = list(tokens.keys())[:5]
        print(f"  {chain}: {', '.join(sample_tokens)}")
        
    # Test lookup for common tokens
    print("\nTesting common token lookups:")
    test_tokens = [
        ('ethereum', 'USDC'),
        ('polygon', 'USDT'),
        ('bsc', 'USDC'),
        ('arbitrum', 'USDC')
    ]
    
    for chain, token in test_tokens:
        if chain in token_map and token in token_map[chain]:
            addr = token_map[chain][token]
            print(f"  ✓ {token} on {chain}: {addr[:10]}...{addr[-8:]}")
        else:
            print(f"  ✗ {token} on {chain}: not found")
    
    # Check cache file
    cache_file = Path("configs/cached_token_addresses.json")
    if cache_file.exists():
        print(f"\n[✓] Cache file created at: {cache_file}")
        print(f"[✓] Cache size: {cache_file.stat().st_size / 1024:.1f} KB")
    
else:
    print("\n[✗] Failed to fetch token addresses")
    print("[!] This may be due to network issues or API rate limits")
    print("[!] Try again in a few moments")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
