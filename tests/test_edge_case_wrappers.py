from decimal import Decimal

import src.core.database as database


def test_to_decimal_wrapper_fallback_handles_none(monkeypatch):
    monkeypatch.setattr(database, "_to_decimal", None)

    result = database.to_decimal(None)

    assert result == Decimal('0')


def test_set_utility_functions_overrides_wrappers(monkeypatch):
    monkeypatch.setattr(database, "_to_decimal", None)
    monkeypatch.setattr(database, "_is_defi_lp_token", None)
    monkeypatch.setattr(database, "_DEFI_LP_CONSERVATIVE", True)
    monkeypatch.setattr(database, "_initialize_folders", None)

    init_called = {}

    def fake_to_decimal(value):
        return Decimal('7')

    def fake_is_defi_lp_token(symbol):
        return symbol == 'UNI-V2'

    def fake_init():
        init_called['ok'] = True

    database.set_utility_functions(fake_to_decimal, fake_is_defi_lp_token, False, fake_init)

    assert database.to_decimal(1) == Decimal('7')
    assert database.is_defi_lp_token('UNI-V2') is True
    database.initialize_folders()
    assert init_called.get('ok') is True
