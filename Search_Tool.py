import ccxt
import requests
import json
import time

def main_menu():
    while True:
        print("\n========================================")
        print("   CRYPTO CONFIGURATION SEARCH TOOL")
        print("========================================")
        print("1. Search for EXCHANGE IDs (for api_keys.json)")
        print("2. Search for COIN SYMBOLS (for wallets.json)")
        print("3. Exit")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            search_exchanges()
        elif choice == '2':
            search_coins()
        elif choice == '3':
            print("Goodbye.")
            break
        else:
            print("Invalid choice.")

def search_exchanges():
    print("\n--- EXCHANGE SEARCH ---")
    print("WARNING: This tool only lists exchanges supported by the API automation.")
    print("If your platform (e.g., MoonPay, PayPal, CashApp, Venmo) is NOT listed below,")
    print("it means you CANNOT use API sync for it.")
    print("-> ACTION: You must download the CSV history from that website")
    print("           and drop it into the 'inputs/' folder manually.")
    
    print("\nEnter part of the name (e.g., 'coinbase', 'binance', 'crypto')")
    
    all_exchanges = ccxt.exchanges
    
    while True:
        query = input("\nSearch Exchange (or 'back'): ").lower().strip()
        if query == 'back': break
        if not query: continue
        
        matches = [x for x in all_exchanges if query in x]
        
        if matches:
            print(f"\nFound {len(matches)} matches (Use the text on the LEFT in your JSON):")
            print("-" * 50)
            for m in matches:
                # Try to get a nicer name if possible, otherwise just ID
                print(f"ID: {m:<20}")
            print("-" * 50)
        else:
            print("No matches found. (Reminder: This platform likely requires a manual CSV export).")

def search_coins():
    print("\n--- COIN SYMBOL SEARCH ---")
    print("Fetching coin list from CoinGecko... (Please wait)")
    
    try:
        url = "https://api.coingecko.com/api/v3/coins/list"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print("Error fetching data from CoinGecko.")
            return
            
        coin_list = response.json() # List of dicts: {'id': 'bitcoin', 'symbol': 'btc', 'name': 'Bitcoin'}
        print(f"Loaded {len(coin_list)} coins.")
        
    except Exception as e:
        print(f"Connection Error: {e}")
        return

    while True:
        query = input("\nSearch Coin Name (e.g., 'Ripple', 'Solana') or 'back': ").lower().strip()
        if query == 'back': break
        if len(query) < 2: 
            print("Please enter at least 2 characters.")
            continue
        
        # Search in Name or Symbol
        matches = []
        for c in coin_list:
            if query in c['name'].lower() or query == c['symbol'].lower():
                matches.append(c)
                if len(matches) >= 15: break # Limit results
        
        if matches:
            print(f"\nFound matches (Use the SYMBOL in your wallets.json):")
            print(f"{'SYMBOL':<10} | {'NAME':<30} | {'COINGECKO ID'}")
            print("-" * 60)
            for m in matches:
                symbol = m['symbol'].upper()
                name = m['name']
                cg_id = m['id']
                print(f"{symbol:<10} | {name:<30} | {cg_id}")
            print("-" * 60)
        else:
            print("No matches found.")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nExiting...")