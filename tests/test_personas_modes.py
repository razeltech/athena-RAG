from app.services.modes import get_mode, list_modes
from app.services.personas import get_persona, list_personas


def test_all_expected_personas_registered():
    ids = {p.id for p in list_personas()}
    assert {"athena", "meera", "smiley", "raza"} <= ids


def test_all_expected_modes_registered():
    ids = {m.id for m in list_modes()}
    assert {"answering", "explaining", "teaching", "review", "summary"} <= ids


def test_get_persona_falls_back_to_default_for_unknown_id():
    assert get_persona("nonexistent").id == "athena"
    assert get_persona(None).id == "athena"


def test_get_mode_falls_back_to_default_for_unknown_id():
    assert get_mode("nonexistent").id == "answering"
    assert get_mode(None).id == "answering"


def test_every_persona_has_a_worked_example():
    for persona in list_personas():
        assert "Example:" in persona.prompt
