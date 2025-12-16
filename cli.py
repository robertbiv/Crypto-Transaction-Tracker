#!/usr/bin/env python3
"""
Crypto Tax Generator - Unified Command Line Interface
Modern CLI with rich formatting and comprehensive feature access
"""

import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.ENDC}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓{Colors.ENDC} {text}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗{Colors.ENDC} {text}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ{Colors.ENDC} {text}")

def run_python_script(script_name, *args):
    """Run a Python script with arguments"""
    # Map script names to their new locations
    script_map = {
        'setup.py': 'src/tools/setup.py',
        'auto_runner.py': 'Auto_Runner.py',
        'review_fixer.py': 'src/tools/review_fixer.py',
        'start_web_ui.py': 'start_web_ui.py'
    }
    
    script_path = Path(__file__).parent / script_map.get(script_name, script_name)
    if not script_path.exists():
        print_error(f"Script not found: {script_name}")
        return False
    
    try:
        result = subprocess.run([sys.executable, str(script_path)] + list(args), check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print_error(f"Script failed with exit code {e.returncode}")
        return False
    except KeyboardInterrupt:
        print_info("Interrupted by user")
        return False

def cmd_setup(args):
    """Run initial setup wizard"""
    print_header("INITIAL SETUP")
    print_info("Initializing folders and configuration files...")
    return run_python_script('setup.py')

def cmd_run(args):
    """Run tax calculation"""
    print_header("TAX CALCULATION")
    
    # Check for cascade mode
    script_args = []
    if args.cascade:
        print_info("Running in CASCADE mode (includes all years)")
        script_args.append('--cascade')
    else:
        current_year = datetime.now().year
        print_info(f"Running for current year: {current_year}")
    
    return run_python_script('auto_runner.py', *script_args)

def cmd_review(args):
    """Run manual review assistant"""
    print_header("MANUAL REVIEW ASSISTANT")
    
    # Get year
    year = args.year if args.year else str(datetime.now().year)
    print_info(f"Reviewing tax year: {year}")
    
    return run_python_script('review_fixer.py', year)

def cmd_web(args):
    """Start web UI"""
    print_header("WEB UI SERVER")
    print_info("Starting web interface at https://localhost:5000")
    print_info("Press Ctrl+C to stop the server\n")
    
    return run_python_script('start_web_ui.py')

def cmd_test(args):
    """Run test suite"""
    print_header("TEST SUITE")
    
    if args.file:
        print_info(f"Running specific test: {args.file}")
        test_path = Path(__file__).parent / 'tests' / args.file
        if not test_path.exists():
            print_error(f"Test file not found: {args.file}")
            return False
        
        try:
            result = subprocess.run([sys.executable, '-m', 'pytest', str(test_path), '-v'], check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False
    else:
        print_info("Running full test suite...")
        try:
            result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/', '-v'], check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

def cmd_info(args):
    """Display system information"""
    print_header("SYSTEM INFORMATION")
    
    # Load constants for paths
    try:
        from src.utils.constants import (
            BASE_DIR, DB_FILE, CONFIG_FILE, STATUS_FILE, 
            INPUT_DIR, OUTPUT_DIR, API_KEYS_ENCRYPTED_FILE
        )
        from src.utils.config import load_config, get_status
        
        print(f"{Colors.BOLD}Paths:{Colors.ENDC}")
        print(f"  Base Directory:  {BASE_DIR}")
        print(f"  Database:        {DB_FILE} {'✓' if DB_FILE.exists() else '✗'}")
        print(f"  Config:          {CONFIG_FILE} {'✓' if CONFIG_FILE.exists() else '✗'}")
        print(f"  API Keys:        {API_KEYS_ENCRYPTED_FILE} {'✓' if API_KEYS_ENCRYPTED_FILE.exists() else '✗'}")
        print(f"  Input Folder:    {INPUT_DIR} ({len(list(INPUT_DIR.glob('*.csv'))) if INPUT_DIR.exists() else 0} CSVs)")
        
        # Try to load config
        try:
            config = load_config()
            status = get_status()
            
            print(f"\n{Colors.BOLD}Configuration:{Colors.ENDC}")
            print(f"  Accounting:      {config.get('accounting', {}).get('method', 'FIFO')}")
            print(f"  Audit Enabled:   {config.get('general', {}).get('run_audit', True)}")
            print(f"  Backups:         {config.get('general', {}).get('create_db_backups', True)}")
            
            print(f"\n{Colors.BOLD}Status:{Colors.ENDC}")
            print(f"  Last Run:        {status.get('last_run', 'Never')}")
            print(f"  Processing Year: {status.get('processing_year', 'Not set')}")
            
        except Exception as e:
            print(f"\n{Colors.YELLOW}⚠{Colors.ENDC} Could not load configuration: {e}")
        
        print_success("System information displayed")
        return True
        
    except Exception as e:
        print_error(f"Could not load system information: {e}")
        return False

def cmd_export(args):
    """Export reports to specified format"""
    print_header("EXPORT REPORTS")
    
    year = args.year if args.year else str(datetime.now().year)
    output_dir = Path(__file__).parent / 'outputs' / f'Year_{year}'
    
    if not output_dir.exists():
        print_error(f"No reports found for year {year}")
        print_info(f"Expected location: {output_dir}")
        return False
    
    # List available reports
    reports = list(output_dir.glob('*.csv'))
    if not reports:
        print_error("No CSV reports found")
        return False
    
    print_success(f"Found {len(reports)} report(s) for year {year}:")
    for report in reports:
        print(f"  • {report.name}")
    
    print_info(f"Reports location: {output_dir}")
    return True

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Crypto Tax Generator - Professional Tax Calculation Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s setup              # Run initial setup wizard
  %(prog)s run                # Calculate taxes for current year
  %(prog)s run --cascade      # Calculate taxes for all years
  %(prog)s review             # Review and fix audit warnings
  %(prog)s review 2024        # Review specific year
  %(prog)s web                # Start web UI
  %(prog)s test               # Run full test suite
  %(prog)s test --file test_setup_wizard.py  # Run specific test
  %(prog)s info               # Display system info
  %(prog)s export             # Export reports for current year
  %(prog)s export --year 2024 # Export reports for specific year

For more information, see README.md or visit the web UI.
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    parser_setup = subparsers.add_parser('setup', help='Run initial setup wizard')
    parser_setup.set_defaults(func=cmd_setup)
    
    # Run command
    parser_run = subparsers.add_parser('run', help='Run tax calculation')
    parser_run.add_argument('--cascade', action='store_true', 
                          help='Process all years (cascade mode)')
    parser_run.set_defaults(func=cmd_run)
    
    # Review command
    parser_review = subparsers.add_parser('review', help='Run manual review assistant')
    parser_review.add_argument('year', nargs='?', 
                             help='Tax year to review (default: current year)')
    parser_review.set_defaults(func=cmd_review)
    
    # Web command
    parser_web = subparsers.add_parser('web', help='Start web UI server')
    parser_web.set_defaults(func=cmd_web)
    
    # Test command
    parser_test = subparsers.add_parser('test', help='Run test suite')
    parser_test.add_argument('--file', help='Specific test file to run')
    parser_test.set_defaults(func=cmd_test)
    
    # Info command
    parser_info = subparsers.add_parser('info', help='Display system information')
    parser_info.set_defaults(func=cmd_info)
    
    # Export command
    parser_export = subparsers.add_parser('export', help='List/export generated reports')
    parser_export.add_argument('--year', help='Tax year (default: current year)')
    parser_export.set_defaults(func=cmd_export)
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 0
    
    # Run command
    try:
        success = args.func(args)
        return 0 if success else 1
    except KeyboardInterrupt:
        print_info("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
