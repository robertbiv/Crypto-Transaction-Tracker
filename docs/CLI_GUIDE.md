# Crypto Transaction Tracker - CLI Guide

Unified, colorized CLI with feature parity to the web interface. Every operation exposed in the web UI can now be driven from `cli.py`.

## Quick start

```bash
# Setup
python cli.py setup

# Process current year (or all years with --cascade)
python cli.py run [--cascade]

# Review warnings, start web UI, or run tests
python cli.py review [year]
python cli.py web
python cli.py test [--file tests/test_cli.py]

# System info
python cli.py info
```

## Command map

**Core**
- `setup`, `run [--cascade]`, `review [year]`, `web`, `test [--file]`, `info`, `export [--year]`

**Transactions**
- `transactions list --page --per-page --search --coin --action --source`
- `transactions add --date --action --coin --amount [--source --destination --price-usd --fee --fee-coin]`
- `transactions update <id> [--date --action --coin --amount --source --destination --price-usd --fee --fee-coin]`
- `transactions delete <id>`
- `transactions upload <file>`
- `transactions template [--output]`
- `transactions reprocess [--batch-size]`

**Reports & review**
- `reports list`
- `reports download <path> [--output]`
- `warnings`
- `stats`

**Config & keys**
- `config show` | `config set --file <config.json>`
- `wallets show|save --file <wallets.json>|test --source <src> --address <addr>`
- `api-keys show|save --file <api_keys.json>|test --exchange <id> --apiKey <key> --secret <secret>`

**Backups**
- `backup full [--output]` (CSV export zip)
- `backup zip [--output]` (encrypted if DB key loaded)
- `backup restore <file> [--mode merge|replace] [--password]`

**Logs**
- `logs list`
- `logs download <name> [--output]`
- `logs download-all [--output]`
- `logs download-redacted [--output]`

**Diagnostics & status**
- `diagnostics run|schema|generate-cert|unlock [--password]|health|status`

**Scheduler**
- `schedule show`
- `schedule save --file <schedule_config.json>`
- `schedule toggle --enabled|--disabled`
- `schedule test [--cascade]`

**Accuracy / ML**
- `accuracy get|set --file <json>`
- `ml check-deps`
- `ml pre-download [--shutdown]`
- `ml delete-model`

## Examples

```bash
# List the latest warnings and suggestions
python cli.py warnings

# Add a manual transaction
python cli.py transactions add --date 2024-12-31T12:00:00Z --action BUY --coin BTC --amount 0.01 --price-usd 42000 --fee 5 --fee-coin USD

# Upload a CSV and then reprocess everything with ML fallback
python cli.py transactions upload ./inputs/new_trades.csv
python cli.py transactions reprocess --batch-size 25

# Show reports and download one
python cli.py reports list
python cli.py reports download outputs/Year_2024/CAP_GAINS_REPORT.csv --output ./cap_gains.csv

# Manage schedules
python cli.py schedule show
python cli.py schedule toggle --enabled

# Rotate ML/accuracy settings
python cli.py accuracy get
python cli.py accuracy set --file ./configs/accuracy_mode.json
```

## Help

```bash
python cli.py --help
python cli.py <command> --help
python cli.py <command> <subcommand> --help
```

Tip: The CLI mirrors the web UI. If you can click it in the browser, you can script it here.
