"""Tests for validate_entry(): the rule that keeps the books balanced.

These are the tests YOUR implementation must pass.
"""
import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.ledger import (
    InvalidPostingError,
    PostingLine,
    UnbalancedEntryError,
    validate_entry,
)
from app.models import Direction

D, C = Direction.DEBIT, Direction.CREDIT


def line(direction, amount, code="assets:bank"):
    return PostingLine(code, direction, amount)


def test_simple_balanced_entry_passes():
    # Customer pays ₹1,000: Razorpay holds it (debit), we earned it (credit).
    validate_entry([
        line(D, 100_000, "assets:razorpay_clearing"),
        line(C, 100_000, "revenue:sales"),
    ])


def test_split_entry_passes():
    # ₹1,000 sale, Razorpay keeps ₹20 fee: 98,000 + 2,000 debits == 100,000 credit.
    validate_entry([
        line(D, 98_000, "assets:razorpay_clearing"),
        line(D, 2_000, "expenses:gateway_fees"),
        line(C, 100_000, "revenue:sales"),
    ])


def test_unbalanced_entry_rejected():
    with pytest.raises(UnbalancedEntryError):
        validate_entry([line(D, 100_000), line(C, 99_999)])


def test_single_line_rejected():
    with pytest.raises(InvalidPostingError):
        validate_entry([line(D, 100)])


def test_empty_entry_rejected():
    with pytest.raises(InvalidPostingError):
        validate_entry([])


@pytest.mark.parametrize("bad", [0, -500])
def test_zero_or_negative_amount_rejected(bad):
    with pytest.raises(InvalidPostingError):
        validate_entry([line(D, bad), line(C, bad)])


@pytest.mark.parametrize("bad", [100.0, "100", True, None])
def test_non_integer_amount_rejected(bad):
    with pytest.raises(InvalidPostingError):
        validate_entry([line(D, bad), line(C, bad)])


def test_all_debits_rejected():
    with pytest.raises(UnbalancedEntryError):
        validate_entry([line(D, 500), line(D, 500)])


# Property-based tests: Hypothesis generates hundreds of random entries.
amounts = st.lists(st.integers(min_value=1, max_value=10**12), min_size=1, max_size=10)


@given(debits=amounts, credits=amounts)
def test_property_balanced_iff_sums_match(debits, credits):
    lines = [line(D, a) for a in debits] + [line(C, a) for a in credits]
    if sum(debits) == sum(credits):
        validate_entry(lines)
    else:
        with pytest.raises(UnbalancedEntryError):
            validate_entry(lines)


@given(parts=amounts)
def test_property_any_split_of_a_credit_is_balanced(parts):
    lines = [line(D, a) for a in parts] + [line(C, sum(parts))]
    validate_entry(lines)
