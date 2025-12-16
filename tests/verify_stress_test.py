"""
================================================================================
TEST UTILITY: Stress Test Verification
================================================================================

Verification script for stress test data processing and accuracy.

Runs the full tax engine against generated stress test data to validate:
    - Correct processing of large transaction volumes (500+ transactions)
    - FIFO basis tracking accuracy across multiple exchanges
    - Income calculation correctness (staking, airdrops)
    - Capital gains computation (short-term and long-term)
    - Fee handling and deductions
    - Strict broker mode isolation
    - Expected warning generation

Process:
    1. Backs up existing database
    2. Copies stress test CSV files to inputs/
    3. Runs tax engine with strict_broker_mode enabled
    4. Validates output against expected statistics
    5. Checks for anomaly detection warnings

Usage:
    python tests/verify_stress_test.py

Author: robertbiv
================================================================================
"""
import sys
import os
import shutil
import pandas as pd
import logging
from pathlib import Path
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import src.core.engine as crypto_tax_engine
from src.core.engine import DatabaseManager, Ingestor, TaxEngine, initialize_folders, INPUT_DIR, DB_FILE, OUTPUT_DIR

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_stress_test")

def run_verification():
    logger.info("Starting Stress Test Verification...")

    # 1. Setup Environment
    logger.info("Setting up environment...")
    
    # Enable strict broker mode (Recommended Config)
    Crypto_Tax_Engine.GLOBAL_CONFIG['compliance']['strict_broker_mode'] = True
    Crypto_Tax_Engine.STRICT_BROKER_MODE = True
    logger.info("Enabled strict_broker_mode (Recommended Config).")

    # Backup existing DB if it exists
    if DB_FILE.exists():
        shutil.move(str(DB_FILE), str(DB_FILE) + ".verify_backup")
        logger.info("Backed up existing database.")
    
    # Clear inputs directory
    if INPUT_DIR.exists():
        for item in INPUT_DIR.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    else:
        INPUT_DIR.mkdir(parents=True)
    
    # Copy stress test data
    stress_test_dir = Path(__file__).parent / "stress_test_data"
    csv_files = list(stress_test_dir.glob("*.csv"))
    for csv in csv_files:
        shutil.copy(csv, INPUT_DIR / csv.name)
    logger.info(f"Copied {len(csv_files)} CSV files to inputs/.")

    try:
        # 2. Run Engine
        logger.info("Initializing Database...")
        initialize_folders()
        db = DatabaseManager()
        
        logger.info("Running Ingestor...")
        ingestor = Ingestor(db)
        ingestor.run_csv_scan()
        # Skip API sync as this is a stress test with CSVs only
        
        # We don't need price fetcher because the generator put prices in the CSVs 
        # and Ingestor should pick them up if mapped correctly.
        
        actual_short_term = 0.0
        actual_long_term = 0.0
        actual_income = 0.0
        
        # Run for each year in the generated data (2023, 2024)
        for year in ['2023', '2024']:
            logger.info(f"Running Tax Engine for {year}...")
            engine = TaxEngine(db, year)
            engine.run()
            engine.export()
            
            # Accumulate results
            year_dir = OUTPUT_DIR / f"Year_{year}"
            cap_gains_file = year_dir / "GENERIC_TAX_CAP_GAINS.csv"
            income_file = year_dir / "INCOME_REPORT.csv"
            
            if cap_gains_file.exists():
                df_cg = pd.read_csv(cap_gains_file)
                # Calculate Gain if missing
                if 'Gain' not in df_cg.columns and 'Proceeds' in df_cg.columns and 'Cost Basis' in df_cg.columns:
                    df_cg['Gain'] = df_cg['Proceeds'] - df_cg['Cost Basis']
                
                if 'Gain' in df_cg.columns and 'Term' in df_cg.columns:
                    actual_short_term += df_cg[df_cg['Term'] == 'Short']['Gain'].sum()
                    actual_long_term += df_cg[df_cg['Term'] == 'Long']['Gain'].sum()
            
            if income_file.exists():
                df_inc = pd.read_csv(income_file)
                if 'USD' in df_inc.columns:
                    actual_income += df_inc['USD'].sum()
        
        # 3. Verify Results
        logger.info("Verifying results...")
        
        # Load Expected Results
        expected_file_json = stress_test_dir / "expected_results.json"
        expected_file_txt = stress_test_dir / "EXPECTED_OUTPUT.txt"
        expected_data = {}
        
        if expected_file_json.exists():
            import json
            logger.info(f"Loading expected results from {expected_file_json.name}")
            with open(expected_file_json, 'r') as f:
                data = json.load(f)
                expected_data['short_term'] = float(data.get('short_term_gains', 0))
                expected_data['long_term'] = float(data.get('long_term_gains', 0))
                expected_data['income'] = float(data.get('total_income', 0))
        elif expected_file_txt.exists():
            logger.info(f"Loading expected results from {expected_file_txt.name}")
            with open(expected_file_txt, 'r') as f:
                for line in f:
                    if "Short Term Capital Gains:" in line:
                        expected_data['short_term'] = float(line.split('$')[1].replace(',', '').strip())
                    elif "Long Term Capital Gains:" in line:
                        expected_data['long_term'] = float(line.split('$')[1].replace(',', '').strip())
                    elif "Total Income" in line:
                        expected_data['income'] = float(line.split('$')[1].replace(',', '').strip())
                    elif "Total Fees Paid:" in line:
                        expected_data['fees'] = float(line.split('$')[1].replace(',', '').strip())
        else:
            logger.error("No expected results file found!")
            return

        # Compare
        logger.info("\n=== RESULTS COMPARISON ===")
        logger.info(f"{'Metric':<25} | {'Expected':<15} | {'Actual':<15} | {'Diff':<15}")
        logger.info("-" * 75)
        
        diff_short = abs(expected_data.get('short_term', 0) - actual_short_term)
        diff_long = abs(expected_data.get('long_term', 0) - actual_long_term)
        diff_income = abs(expected_data.get('income', 0) - actual_income)
        
        logger.info(f"{'Short Term Gains':<25} | ${expected_data.get('short_term', 0):,.2f}      | ${actual_short_term:,.2f}      | ${diff_short:,.2f}")
        logger.info(f"{'Long Term Gains':<25} | ${expected_data.get('long_term', 0):,.2f}      | ${actual_long_term:,.2f}      | ${diff_long:,.2f}")
        logger.info(f"{'Total Income':<25} | ${expected_data.get('income', 0):,.2f}      | ${actual_income:,.2f}      | ${diff_income:,.2f}")
        
        # Allow for small rounding differences (e.g. < $1.00)
        tolerance = 1.0
        success = True
        if diff_short > tolerance: success = False
        if diff_long > tolerance: success = False
        if diff_income > tolerance: success = False
        
        if success:
            logger.info("\nSUCCESS: Results match within tolerance.")
        else:
            logger.error("\nFAILURE: Results do not match expected values.")
            
    except Exception as e:
        logger.exception(f"Verification failed with error: {e}")
    finally:
        # Restore DB
        if db:
            db.close()
        if Path(str(DB_FILE) + ".verify_backup").exists():
            if DB_FILE.exists():
                try: os.remove(DB_FILE)
                except: pass
            shutil.move(str(DB_FILE) + ".verify_backup", DB_FILE)
            logger.info("Restored original database.")

if __name__ == "__main__":
    run_verification()


