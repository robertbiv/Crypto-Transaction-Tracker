# Crypto Transaction Tracker - CLI Quick Reference

## Overview
The `cli.py` provides a unified command-line interface for all Crypto Transaction Tracker features with modern formatting and comprehensive access to the system.

## Installation
No additional installation required - uses standard Python libraries.

## Usage

### Basic Commands

#### Setup
Initialize folders and configuration files:
```bash
python cli.py setup
```

#### Process Activity
Process and review transactions for the current year:
```bash
python cli.py run
```

Process all years (cascade mode):
```bash
python cli.py run --cascade
```

#### Manual Review
Review audit and reconciliation warnings for current year:
```bash
python cli.py review
```

Review specific year:
```bash
python cli.py review 2024
```

#### Web Interface
Start the web UI server:
```bash
python cli.py web
```
Then navigate to https://localhost:5000

#### Testing
Run full test suite:
```bash
python cli.py test
```

Run specific test file:
```bash
python cli.py test --file test_setup_wizard.py
```

#### System Information
Display paths, configuration, and status:
```bash
python cli.py info
```

#### Export Reports
List reports for current year:
```bash
python cli.py export
```

List reports for specific year:
```bash
python cli.py export --year 2024
```

## Command Reference

| Command | Description | Arguments |
|---------|-------------|-----------|
| `setup` | Run initial setup wizard | None |
| `run` | Process transactions | `--cascade` (optional) |
| `review` | Fix audit and reconciliation warnings | `[year]` (optional) |
| `web` | Start web UI server | None |
| `test` | Run tests | `--file <name>` (optional) |
| `info` | Show system info | None |
| `export` | List/export reports | `--year <year>` (optional) |

## Examples

### First-Time Setup
```bash
# 1. Run setup wizard
python cli.py setup

# 2. Check system status
python cli.py info

# 3. Start web UI to configure
python cli.py web
```

### Daily Workflow
```bash
# Process current-year activity
python cli.py run

# Review any warnings
python cli.py review

# View reports
python cli.py export
```

### Development Workflow
```bash
# Run tests before changes
python cli.py test

# Make changes...

# Run specific test
python cli.py test --file test_my_feature.py

# Verify system
python cli.py info
```

## Help
For detailed help on any command:
```bash
python cli.py --help
python cli.py <command> --help
```

## Features
- ✨ **Modern Interface**: Color-coded output with success/error indicators
- 🎯 **Unified Access**: Single entry point for all features
- 📋 **Comprehensive**: Access to setup, calculation, review, web UI, and testing
- 🔍 **Informative**: Built-in system information and status checks
- 🚀 **Efficient**: Direct script execution with proper error handling

## Migration from Old Scripts

### Old Way → New Way

```bash
# Setup
python Setup.py                    → python cli.py setup

# Run
python Auto_Runner.py              → python cli.py run
python Auto_Runner.py --cascade    → python cli.py run --cascade

# Review
python Interactive_Review_Fixer.py → python cli.py review
python Interactive_Review_Fixer.py 2024 → python cli.py review 2024

# Web UI
python start_web_ui.py             → python cli.py web
python web_server.py               → python cli.py web

# Tests
pytest tests/                      → python cli.py test
pytest tests/test_file.py          → python cli.py test --file test_file.py
```

**Note**: Old scripts still work! The CLI is an additional convenience interface.

## Color Output
The CLI uses ANSI color codes for enhanced readability:
- 🔵 **Blue**: Headers
- 🟢 **Green**: Success messages (✓)
- 🔴 **Red**: Error messages (✗)
- 🟡 **Yellow**: Warnings (⚠)
- 🔷 **Cyan**: Info messages (ℹ)

## Exit Codes
- `0`: Success
- `1`: General error
- `130`: User interrupted (Ctrl+C)

## Integration
The CLI can be integrated into automation scripts:

```bash
# Automated daily workflow
python cli.py run && python cli.py review 2025

# CI/CD pipeline
python cli.py test && python cli.py run --cascade
```

## Troubleshooting

### "Script not found" error
Ensure you're running from the project root directory where all scripts are located.

### Import errors
Make sure your virtual environment is activated:
```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### Permission errors
On Linux/Mac, make the CLI executable:
```bash
chmod +x cli.py
./cli.py <command>
```

## Support
For more information:
- See [README.md](../README.md) for full documentation
- Use `python cli.py web` to access the graphical interface
- Check [PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md) for architecture details
