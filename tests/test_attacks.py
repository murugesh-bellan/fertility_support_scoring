"""Attack scenario tests."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def attack_scenarios():
    """Load attack scenarios from test dataset."""
    dataset_path = Path(__file__).parent / "test_dataset.json"
    with open(dataset_path) as f:
        data = json.load(f)
    return data["attack_scenarios"]


def test_attack_scenarios_loaded(attack_scenarios):
    """Verify attack scenarios are loaded."""
    assert len(attack_scenarios) == 10
    categories = {s["category"] for s in attack_scenarios}
    assert "injection_attack" in categories
    assert "jailbreak_attack" in categories
    assert "prompt_leaking" in categories


@pytest.mark.asyncio
async def test_injection_attacks(attack_scenarios):
    """Test injection attack detection."""
    from security.injection import detector

    injection_attacks = [s for s in attack_scenarios if "injection" in s["category"]]

    for attack in injection_attacks:
        is_injection, patterns = detector.detect(attack["message"])
        assert is_injection, f"Failed to detect: {attack['message']}"


@pytest.mark.asyncio
async def test_prompt_leaking(attack_scenarios):
    """Test prompt leaking attempts."""
    from security.injection import detector

    leaking_attempts = [s for s in attack_scenarios if s["category"] == "prompt_leaking"]

    for attempt in leaking_attempts:
        is_injection, patterns = detector.detect(attempt["message"])
        assert is_injection, f"Failed to detect prompt leaking: {attempt['message']}"


def test_token_bombing():
    """Test token bombing detection."""
    from security.validation import validate_message, ValidationError

    # Excessive repetition should be caught
    with pytest.raises(ValidationError):
        validate_message("test " * 100)
