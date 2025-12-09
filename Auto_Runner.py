import Crypto_Tax_Engine as tax_app
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# --- LOGGING CONFIGURATION ---
LOG_DIR = tax_app.OUTPUT_DIR / "logs"
if not LOG_DIR.exists(): LOG_DIR.mkdir(parents=True)

# Generate a unique filename based on current date and time
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = LOG_DIR / f"AutoRun_{timestamp}.log"

def log(message):
    """Prints to console AND appends to the log file."""
    # We don't need the timestamp in the message body anymore because the filename has it,
    # but it's good practice to keep it for long running processes.
    ts_prefix = datetime.now().strftime("[%H:%M:%S] ")
    formatted_msg = f"{ts_prefix}{message}"
    
    print(formatted_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")

def run_automation():
    log("=========================================")
    log("   CRYPTO TAX AUTO-PILOT: STARTED")
    log("=========================================")

    try:
        # 1. INITIALIZE DATABASE
        db = tax_app.DatabaseManager()
        ingest = tax_app.Ingestor(db)
        
        # 2. SYNC DATA
        log(">>> STEP 1: SYNCING DATA SOURCES")
        ingest.run_csv_scan()
        ingest.run_api_sync()
        log("   -> Sync process completed.")
        
        # 3. BACKFILL PRICES
        bf = tax_app.PriceFetcher()
        zeros = db.get_zeros()
        if not zeros.empty:
            log(f">>> STEP 2: BACKFILLING {len(zeros)} MISSING PRICES")
            count = 0
            for _, r in zeros.iterrows():
                p = bf.get_price(r['coin'], pd.to_datetime(r['date']))
                if p > 0: 
                    db.update_price(r['id'], p)
                    count += 1
            db.commit()
            log(f"   -> Backfilled {count} prices.")
        else:
            log(">>> STEP 2: NO MISSING PRICES FOUND (SKIP)")

        # 4. DETERMINE YEARS
        now = datetime.now()
        current_year = now.year
        prev_year = current_year - 1
        
        # 5. CHECK PREVIOUS YEAR (The "Final Run")
        prev_folder = tax_app.OUTPUT_DIR / f"Year_{prev_year}"
        snapshot_file = prev_folder / "EOY_HOLDINGS_SNAPSHOT.csv"
        
        log(f">>> STEP 3: CHECKING PREVIOUS TAX YEAR ({prev_year})")
        
        if snapshot_file.exists():
            log(f"   [SKIP] Year {prev_year} is already finalized.")
        else:
            log(f"   [ACTION] Year {prev_year} not finalized. Running Report...")
            engine_prev = tax_app.TaxEngine(db, prev_year)
            engine_prev.run()
            engine_prev.export()
            log(f"   [SUCCESS] Finalized {prev_year} and created Snapshot.")

        # 6. RUN CURRENT YEAR (The "Live Tracker")
        log(f">>> STEP 4: UPDATING LIVE TRACKER FOR CURRENT YEAR ({current_year})")
        engine_curr = tax_app.TaxEngine(db, current_year)
        engine_curr.run()
        engine_curr.export()
        log(f"   [SUCCESS] Updated 'Draft' reports for {current_year}.")

        db.close()
        log("=========================================")
        log("   AUTO-PILOT: COMPLETED SUCCESSFULLY")
        log("=========================================\n") 

    except Exception as e:
        log(f"[CRITICAL ERROR] Automation Failed: {e}")
        raise e

if __name__ == "__main__":
    try:
        run_automation()
    except:
        input("\nScript crashed. Check logs. Press Enter to close...")
    
    if sys.stdout.isatty():
        input("\nPress Enter to close...")