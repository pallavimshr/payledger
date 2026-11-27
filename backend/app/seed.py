"""Create the default chart of accounts. Safe to run more than once."""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, AccountType

DEFAULT_ACCOUNTS = [
    ("assets:bank", "Bank account", AccountType.ASSET),
    ("assets:razorpay_clearing", "Money held by Razorpay, not yet settled", AccountType.ASSET),
    ("assets:stripe_clearing", "Money held by Stripe, not yet settled", AccountType.ASSET),
    ("liabilities:refunds_payable", "Refunds owed to customers", AccountType.LIABILITY),
    ("equity:owner", "Owner's equity", AccountType.EQUITY),
    ("revenue:sales", "Sales revenue", AccountType.REVENUE),
    ("expenses:gateway_fees", "Payment gateway fees", AccountType.EXPENSE),
]


def main() -> None:
    with SessionLocal() as session:
        existing = set(session.scalars(select(Account.code)))
        added = 0
        for code, name, type_ in DEFAULT_ACCOUNTS:
            if code not in existing:
                session.add(Account(code=code, name=name, type=type_.value))
                added += 1
        session.commit()
    print(f"Seed complete: {added} account(s) added, {len(existing)} already existed.")


if __name__ == "__main__":
    main()
