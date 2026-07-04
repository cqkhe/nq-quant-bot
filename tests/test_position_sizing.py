from nqbot.risk.position_sizing import contracts_for_risk


def test_basic_sizing():
    # $25k, 0.5% = $125 de riesgo; stop a 20 pts en MNQ ($2/pt) = $40/contrato -> 3
    assert contracts_for_risk(25_000, 0.5, 20.0, 2.0, max_contracts=10) == 3


def test_returns_zero_if_risk_does_not_cover_one_contract():
    # $125 de riesgo vs $200/contrato -> no se opera
    assert contracts_for_risk(25_000, 0.5, 100.0, 2.0, max_contracts=10) == 0


def test_caps_at_max_contracts():
    assert contracts_for_risk(1_000_000, 1.0, 10.0, 2.0, max_contracts=10) == 10


def test_degenerate_inputs():
    assert contracts_for_risk(0, 0.5, 20.0, 2.0, 10) == 0
    assert contracts_for_risk(25_000, 0.5, 0.0, 2.0, 10) == 0
    assert contracts_for_risk(25_000, 0.5, -5.0, 2.0, 10) == 0
