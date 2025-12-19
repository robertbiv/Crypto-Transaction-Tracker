import io
import json
import os
import sqlite3
import sys
import threading
import types
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import cli


@pytest.fixture()
def cli_env(monkeypatch, tmp_path):
    # Core paths
    base = tmp_path
    outputs = base / "outputs"
    configs = base / "configs"
    keys_dir = base / "keys"
    outputs.mkdir(parents=True, exist_ok=True)
    configs.mkdir(parents=True, exist_ok=True)
    keys_dir.mkdir(parents=True, exist_ok=True)

    db_path = base / "crypto_master.db"

    def get_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # Ensure trades table exists
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            date TEXT,
            source TEXT,
            destination TEXT,
            action TEXT,
            coin TEXT,
            amount TEXT,
            price_usd TEXT,
            fee TEXT,
            fee_coin TEXT,
            batch_id TEXT
        )
        """
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.commit()
    conn.close()

    # Patch module-level paths
    monkeypatch.setattr(cli, "BASE_DIR", base)
    monkeypatch.setattr(cli, "OUTPUT_DIR", outputs)
    monkeypatch.setattr(cli, "CONFIG_FILE", configs / "config.json")
    monkeypatch.setattr(cli, "DB_FILE", db_path)
    monkeypatch.setattr(cli, "API_KEYS_ENCRYPTED_FILE", keys_dir / "api_keys_encrypted.json")
    monkeypatch.setattr(cli, "API_KEYS_FILE", base / "api_keys.json")
    monkeypatch.setattr(cli, "WALLETS_ENCRYPTED_FILE", keys_dir / "wallets_encrypted.json")
    monkeypatch.setattr(cli, "WALLETS_FILE", base / "wallets.json")
    monkeypatch.setattr(cli, "PROJECT_ROOT", base)

    # Web server stubs
    fake_app = SimpleNamespace(config={}, _tinyllama_download_failures=0)
    monkeypatch.setattr(cli.web_server, "app", fake_app)
    monkeypatch.setattr(
        cli.web_server,
        "txn_app",
        SimpleNamespace(mark_data_changed=lambda: None, get_status=lambda: {"ok": True}),
    )
    monkeypatch.setattr(cli.web_server, "_compute_diagnostics", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(cli.web_server, "generate_self_signed_cert", lambda: ("cert", "key"))

    class FakeFernet:
        def __init__(self, key):
            self.key = key

        def encrypt(self, data: bytes) -> bytes:
            return b"enc" + data

        def decrypt(self, data: bytes) -> bytes:
            return data[3:] if data.startswith(b"enc") else data

    monkeypatch.setattr(cli.web_server, "Fernet", FakeFernet)
    monkeypatch.setattr(cli.web_server, "get_db_connection", get_conn)
    monkeypatch.setattr(cli.web_server, "_ingest_csv_with_engine", lambda path: {"total_rows": 2, "new_trades": 2})

    # Encryption helpers
    monkeypatch.setattr(cli.DatabaseEncryption, "initialize_encryption", lambda password: b"dbkey")
    monkeypatch.setattr(cli.DatabaseEncryption, "decrypt_key", lambda enc, pw, salt: b"dbkey")

    # Wallets/API keys storage
    wallet_store = {"eth": {"addresses": ["0xabc"]}}
    api_key_store = {"binance": {"apiKey": "abcd1234", "secret": "wxyz9876"}}
    monkeypatch.setattr(cli, "load_wallets_file", lambda: wallet_store)
    monkeypatch.setattr(cli, "save_wallets_file", lambda data: wallet_store.update(data))
    monkeypatch.setattr(cli, "load_api_keys_file", lambda: api_key_store)
    monkeypatch.setattr(cli, "save_api_keys_file", lambda data: api_key_store.update(data))

    # Wallet linker stub
    from src.web import wallet_linker

    class FakeWalletLinker:
        def __init__(self, wallets):
            self.wallets = wallets

        def find_matching_wallet(self, source, address):
            return {"source": source, "address": address} if address in ["0xabc", "0xdef"] else None

        def get_possible_wallets_for_source(self, source):
            return [f"{source}-option"]

        def get_all_wallets_for_selection(self):
            return ["0xabc"]

    monkeypatch.setattr(wallet_linker, "WalletLinker", FakeWalletLinker)

    # ML service + rules bridge
    class FakeMLService:
        def __init__(self, mode="tinyllama", auto_shutdown_after_inference=True):
            self.mode = mode
            self.pipe = None

        def _load_model(self):
            self.pipe = "ready"

        def shutdown(self):
            self.pipe = None

    sys.modules["src.ml_service"] = types.SimpleNamespace(MLService=FakeMLService)
    sys.modules["src.rules_model_bridge"] = types.SimpleNamespace(
        classify_rules_ml=lambda row, svc: {"source": "ml", "label": "SELL", "confidence": 0.9, "explanation": ""}
    )

    # ccxt stub
    class FakeExchange:
        def __init__(self, cfg):
            self.cfg = cfg

        def fetch_balance(self):
            return {"total": 0}

    class FakeCCXTModule(types.SimpleNamespace):
        def __init__(self):
            super().__init__(binance=type("Binance", (), {"__init__": lambda self, cfg: FakeExchange(cfg), "fetch_balance": FakeExchange.fetch_balance}))

    sys.modules["ccxt"] = FakeCCXTModule()

    # Fernet key for backup encryption
    fake_app.config["DB_ENCRYPTION_KEY"] = b"dbkey"

    return SimpleNamespace(base=base, db_path=db_path, outputs=outputs, configs=configs, wallet_store=wallet_store, api_key_store=api_key_store)


def test_transactions_crud(cli_env, monkeypatch):
    from cli import cmd_tx_add, cmd_tx_update, cmd_tx_delete, cmd_tx_list

    # Insert
    ok = cmd_tx_add(SimpleNamespace(date="2024-01-01", action="BUY", coin="BTC", amount="1", source="EX", destination=None, price_usd=10000.0, fee=10.0, fee_coin="USD"))
    assert ok

    # Fetch id
    conn = sqlite3.connect(cli_env.db_path)
    conn.row_factory = sqlite3.Row
    tx_id = conn.execute("SELECT id FROM trades").fetchone()[0]

    # Update
    ok = cmd_tx_update(SimpleNamespace(id=tx_id, action="SELL", coin=None, amount=None, source=None, destination=None, date=None, price_usd=None, fee=None, fee_coin=None))
    assert ok

    # List
    monkeypatch.setattr(cli.web_server, "get_transactions", lambda **kwargs: {"transactions": [], "total": 0})
    ok = cmd_tx_list(SimpleNamespace(page=1, per_page=10, search=None, coin=None, action=None, source=None))
    assert ok

    # Delete
    ok = cmd_tx_delete(SimpleNamespace(id=tx_id))
    assert ok
    conn.close()


def test_transactions_upload_template_reprocess(cli_env):
    from cli import cmd_tx_upload, cmd_tx_template, cmd_tx_reprocess

    csv_file = cli_env.base / "sample.csv"
    csv_file.write_text("date,coin,amount\n2024-01-01,BTC,1\n")
    ok = cmd_tx_upload(SimpleNamespace(file=str(csv_file)))
    assert ok

    tmpl = cli_env.base / "tmpl.csv"
    ok = cmd_tx_template(SimpleNamespace(output=str(tmpl)))
    assert ok and tmpl.exists()

    # Prepare config with ML enabled and a sample row
    config = {"ml_fallback": {"enabled": True, "model_name": "shim", "batch_size": 1}, "accuracy_mode": {"enabled": False}}
    cli_env.configs.joinpath("config.json").parent.mkdir(parents=True, exist_ok=True)
    cli_env.configs.joinpath("config.json").write_text(json.dumps(config))
    conn = sqlite3.connect(cli_env.db_path)
    conn.execute("INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ("abc", "2024-01-01", "SRC", "DEST", "BUY", "ETH", 1, 1000, 0, "", None))
    conn.commit()
    conn.close()

    ok = cmd_tx_reprocess(SimpleNamespace(batch_size=1))
    assert ok


def test_reports_warnings_stats(cli_env):
    from cli import cmd_reports_list, cmd_reports_download, cmd_warnings, cmd_stats

    year_dir = cli_env.outputs / "Year_2024"
    year_dir.mkdir(parents=True, exist_ok=True)
    report_file = year_dir / "CAP_GAINS.csv"
    report_file.write_text("col1,col2\n1,2\n")

    ok = cmd_reports_list(SimpleNamespace())
    assert ok

    dest = cli_env.base / "copy.csv"
    ok = cmd_reports_download(SimpleNamespace(path=str(report_file.relative_to(cli_env.base)), output=str(dest)))
    assert ok and dest.exists()

    warn_file = year_dir / "REVIEW_WARNINGS.csv"
    warn_file.write_text("col\nval\n")
    sugg_file = year_dir / "REVIEW_SUGGESTIONS.csv"
    sugg_file.write_text("col\nval\n")
    ok = cmd_warnings(SimpleNamespace())
    assert ok

    # Stats with sample rows
    conn = sqlite3.connect(cli_env.db_path)
    conn.execute("INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ("def", "2024-02-01", "SRC", "DEST", "BUY", "BTC", 2, 20000, 0, "", None))
    conn.commit()
    conn.close()
    ok = cmd_stats(SimpleNamespace())
    assert ok


def test_config_wallets_api_keys(cli_env):
    from cli import cmd_config_show, cmd_config_set, cmd_wallets_show, cmd_wallets_save, cmd_wallets_test, cmd_api_keys_show, cmd_api_keys_save, cmd_api_keys_test

    config_content = {"general": {"run_audit": True}}
    cli.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cli.CONFIG_FILE.write_text(json.dumps(config_content))
    assert cmd_config_show(SimpleNamespace())

    new_cfg_path = cli_env.base / "new_config.json"
    new_cfg_path.write_text(json.dumps({"general": {"run_audit": False}}))
    assert cmd_config_set(SimpleNamespace(file=str(new_cfg_path)))

    assert cmd_wallets_show(SimpleNamespace())
    wallet_input = cli_env.base / "wallets.json"
    wallet_input.write_text(json.dumps({"eth": {"addresses": ["0xdef"]}}))
    assert cmd_wallets_save(SimpleNamespace(file=str(wallet_input)))
    assert cmd_wallets_test(SimpleNamespace(source="eth", address="0xabc"))

    assert cmd_api_keys_show(SimpleNamespace())
    api_input = cli_env.base / "api.json"
    api_input.write_text(json.dumps({"binance": {"apiKey": "abcd9999", "secret": "secret9999"}}))
    assert cmd_api_keys_save(SimpleNamespace(file=str(api_input)))
    assert cmd_api_keys_test(SimpleNamespace(exchange="binance", apiKey="abcd9999", secret="secret9999"))


def test_backups_and_restore(cli_env):
    from cli import cmd_backup_full, cmd_backup_zip, cmd_restore_backup

    # Seed DB
    conn = sqlite3.connect(cli_env.db_path)
    conn.execute("INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 ("ghi", "2024-03-01", "SRC", "DEST", "BUY", "ADA", 3, 3000, 0, "", None))
    conn.commit()
    conn.close()

    full_dest = cli_env.base / "full.zip"
    assert cmd_backup_full(SimpleNamespace(output=str(full_dest)))
    assert full_dest.exists()

    zip_dest = cli_env.base / "backup.zip"
    assert cmd_backup_zip(SimpleNamespace(output=str(zip_dest)))
    assert zip_dest.exists()

    # Restore from plain zip
    assert cmd_restore_backup(SimpleNamespace(file=str(zip_dest), mode="merge", password=None))


def test_logs(cli_env):
    from cli import cmd_logs_list, cmd_logs_download, cmd_logs_download_all, cmd_logs_download_redacted

    log_dir = cli_env.outputs / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"
    log_file.write_text("apiKey=abcd1234 secret=shhh 0x1111111111111111111111111111111111111111")

    assert cmd_logs_list(SimpleNamespace())

    dest = cli_env.base / "app_copy.log"
    assert cmd_logs_download(SimpleNamespace(name=str(log_file), output=str(dest)))
    assert dest.exists()

    all_zip = cli_env.base / "logs.zip"
    assert cmd_logs_download_all(SimpleNamespace(output=str(all_zip)))
    assert all_zip.exists()

    red_zip = cli_env.base / "logs_redacted.zip"
    assert cmd_logs_download_redacted(SimpleNamespace(output=str(red_zip)))
    assert red_zip.exists()


def test_diagnostics_health_status(cli_env, monkeypatch):
    from cli import cmd_diagnostics, cmd_diagnostics_schema, cmd_diagnostics_generate_cert, cmd_diagnostics_unlock, cmd_system_health, cmd_status

    assert cmd_diagnostics(SimpleNamespace())
    assert cmd_diagnostics_schema(SimpleNamespace())
    assert cmd_diagnostics_generate_cert(SimpleNamespace())
    assert cmd_diagnostics_unlock(SimpleNamespace(password="pw"))

    # Health and status rely on txn_app get_status
    monkeypatch.setattr(cli.web_server.txn_app, "get_status", lambda: {"last_run": "now"})
    assert cmd_system_health(SimpleNamespace())
    assert cmd_status(SimpleNamespace())


def test_scheduler(cli_env, monkeypatch):
    from cli import cmd_schedule_show, cmd_schedule_save, cmd_schedule_toggle, cmd_schedule_test

    class FakeScheduleManager:
        def __init__(self, base_dir, auto_runner_path):
            self.base_dir = base_dir
            self.auto_runner_path = auto_runner_path
            self.saved = {"enabled": False, "schedules": []}
            self.active = []

        def load_schedule_config(self):
            return self.saved

        def save_schedule_config(self, config):
            self.saved = config

        def get_active_schedules(self):
            return self.active

        def reload_schedules(self):
            if self.saved.get("enabled"):
                self.active = [{"id": "job1", "trigger": "cron", "next_run": None}]
            else:
                self.active = []

        def shutdown(self):
            pass

    monkeypatch.setattr(cli, "ScheduleManager", FakeScheduleManager)

    assert cmd_schedule_show(SimpleNamespace())

    cfg_path = cli_env.base / "schedule_config.json"
    cfg_path.write_text(json.dumps({"enabled": True, "schedules": [{"id": "daily", "frequency": "daily"}]}))
    assert cmd_schedule_save(SimpleNamespace(file=str(cfg_path)))

    assert cmd_schedule_toggle(SimpleNamespace(enabled=True, disabled=False))
    assert cmd_schedule_test(SimpleNamespace(cascade=False))


def test_accuracy_and_ml(cli_env, monkeypatch):
    from cli import cmd_accuracy_get, cmd_accuracy_set, cmd_ml_check_deps, cmd_ml_pre_download, cmd_ml_delete_model

    accuracy_cfg = {"accuracy_mode": {"enabled": False}}
    cli.CONFIG_FILE.write_text(json.dumps(accuracy_cfg))
    assert cmd_accuracy_get(SimpleNamespace())

    acc_path = cli_env.base / "acc.json"
    acc_path.write_text(json.dumps({"enabled": True}))
    assert cmd_accuracy_set(SimpleNamespace(file=str(acc_path)))

    assert cmd_ml_check_deps(SimpleNamespace())

    # ML pre-download uses FakeMLService
    assert cmd_ml_pre_download(SimpleNamespace(shutdown=True))

    # Create fake cache and delete it
    hf_cache = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface" / "hub"))
    tiny_cache = hf_cache / "models--TheBloke--TinyLlama-1.1B-Chat-v1.0-GGUF"
    tiny_cache.mkdir(parents=True, exist_ok=True)
    sample = tiny_cache / "weights.bin"
    sample.write_bytes(b"12345")
    assert cmd_ml_delete_model(SimpleNamespace())