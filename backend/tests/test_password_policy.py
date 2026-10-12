"""Password policy module: rules, consistency, generator (T-PWD-01..06, PWD-022)."""
from __future__ import annotations

import itertools

import pytest

from app.services.policy_service import (
    CEILING_MAX_LENGTH,
    FLOOR_MIN_LENGTH,
    PasswordPolicy,
    add_months,
    check_consistency,
    evaluate,
    generate,
    profile_defaults,
)
from datetime import datetime, timezone


def test_defaults_match_rule_17():
    p = PasswordPolicy()
    assert (p.min_length, p.max_length) == (12, 128)
    assert p.require_upper and p.require_lower and p.require_digit and p.require_special
    assert (p.expiration_enabled, p.expiration_months) == (True, 6)
    assert (p.history_count, p.min_age_hours, p.reveal_autohide_seconds) == (5, 48, 5)
    assert p.history_applies_to_admin_set and p.reject_username and p.reject_common
    assert check_consistency(p) == []


def test_all_failed_rules_are_reported_together():
    failed = evaluate(PasswordPolicy(), "abc", "abc")
    assert {"password.too_short", "password.no_upper", "password.no_digit", "password.no_special",
            "password.contains_username"} <= set(failed)


def test_each_class_toggle_changes_behaviour():
    base = {"require_upper": False, "require_lower": False, "require_digit": False, "require_special": False}
    cases = {
        "require_upper": ("abcdefghijkl1!", "password.no_upper"),
        "require_lower": ("ABCDEFGHIJKL1!", "password.no_lower"),
        "require_digit": ("Abcdefghijkl!x", "password.no_digit"),
        "require_special": ("Abcdefghijkl1x", "password.no_special"),
    }
    for flag, (bad, code) in cases.items():
        on = PasswordPolicy(**{**base, flag: True})
        off = PasswordPolicy(**base)
        assert code in evaluate(on, bad)
        assert code not in evaluate(off, bad)


def test_max_length_is_rejected_not_truncated():
    p = PasswordPolicy(max_length=20)
    assert "password.too_long" in evaluate(p, "Aa1!" + "x" * 30)


def test_common_password_and_username_rules():
    p = PasswordPolicy(min_length=6, require_upper=False, require_digit=False, require_special=False)
    assert "password.common" in evaluate(p, "Password")
    assert "password.contains_username" in evaluate(p, "xxJoeSmithxx", "joesmith")
    off = PasswordPolicy(min_length=6, reject_common=False, reject_username=False,
                         require_upper=False, require_digit=False, require_special=False)
    assert evaluate(off, "password", "pass") == []


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"min_length": 3}, "policy.min_length_below_floor"),
        ({"min_length": 20, "max_length": 10}, "policy.min_above_max"),
        ({"min_length": 6, "require_upper": True, "require_lower": True, "require_digit": True,
          "require_special": True, "max_length": 128}, None),  # 6 >= 4 classes: consistent
        ({"history_count": 99}, "policy.history_out_of_range"),
        ({"expiration_enabled": True, "expiration_months": 0}, "policy.expiration_out_of_range"),
        ({"expiration_months": 1, "min_age_hours": 24 * 40}, "policy.min_age_above_expiration"),
        ({"expiration_months": 1, "expiry_notice_days": 40}, "policy.notice_above_expiration"),
        ({"max_length": CEILING_MAX_LENGTH + 1}, "policy.max_length_above_ceiling"),
        ({"reveal_autohide_seconds": 9999}, "policy.reveal_out_of_range"),
    ],
)
def test_inconsistent_settings_name_the_conflict(changes, code):
    problems = check_consistency(PasswordPolicy(**changes))
    codes = {p["code"] for p in problems}
    if code is None:
        assert codes == set()
    else:
        assert code in codes
        assert all(p["fields"] for p in problems)


def test_min_length_below_required_class_count():
    # Floor is 6, so the class-count rule is reachable only when the floor allows: assert it directly.
    p = PasswordPolicy(min_length=FLOOR_MIN_LENGTH)
    assert check_consistency(p) == []
    assert p.required_class_count == 4


@pytest.mark.parametrize("profile", ["standard", "minimal"])
def test_generated_password_satisfies_every_class_combination(profile):
    base = profile_defaults(profile)
    flags = ["require_upper", "require_lower", "require_digit", "require_special"]
    for combo in itertools.product([True, False], repeat=4):
        policy = PasswordPolicy(**{**base.to_dict(), **dict(zip(flags, combo))})
        if check_consistency(policy):
            continue
        for _ in range(5):
            pw = generate(policy, "someone")
            assert evaluate(policy, pw, "someone") == []
            assert policy.min_length <= len(pw) <= policy.max_length


def test_generator_does_not_repeat():
    p = PasswordPolicy()
    assert len({generate(p) for _ in range(30)}) == 30


def test_add_months_clamps_day():
    moment = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    assert add_months(moment, 6) == datetime(2027, 2, 28, 10, 0, tzinfo=timezone.utc)
    assert add_months(moment, 6 + 12 * 2).month == 2
