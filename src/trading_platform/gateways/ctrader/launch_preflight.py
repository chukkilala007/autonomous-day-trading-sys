"""Offline deployment-input checks. Never authenticates or authorizes orders."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import digest
from .attended_binding import ReviewedBundle


def check(bundle, entry, *, account_id, approved_bundle_hash, now):
    blockers = []
    policy = bundle.policy
    if digest(bundle) != approved_bundle_hash:
        blockers.append('REVIEW_PIN_MISMATCH')
    if (policy.account_id != account_id
            or policy.currency != 'USD' or policy.quote_currency != 'USD'):
        blockers.append('UNSUPPORTED_ACCOUNT_CONTRACT')
    if not policy.observed_at <= now < policy.valid_until:
        blockers.append('POLICY_NOT_CURRENT')
    if (entry.instrument != policy.instrument or entry.side != 'buy'
            or entry.order_type != 'limit' or entry.entry != entry.worst_fill
            or entry.target is None or entry.exit_at is not None
            or entry.profile != 'protected' or entry.basis != 'executable'):
        blockers.append('UNSUPPORTED_PROPOSAL')
    created = entry.expires_at - timedelta(seconds=60)
    if not created <= now <= created + timedelta(seconds=10):
        blockers.append('PROPOSAL_NOT_CURRENT')
    if (policy.minimum > bundle.quantity or policy.maximum < bundle.quantity
            or (bundle.quantity-policy.minimum) % policy.step):
        blockers.append('QUANTITY_GRID_MISMATCH')
    if any(price is not None and price % policy.tick for price in
           (entry.entry, entry.worst_fill, entry.stop, entry.target)):
        blockers.append('PRICE_GRID_MISMATCH')
    return dict(status='BLOCKED' if blockers else 'INPUTS_VALIDATED_NOT_BROKER_READY',
                blockers=blockers, orders_enabled=False, broker_connected=False,
                bundle_hash=digest(bundle), proposal_hash=digest(entry))


def load_check(bundle_path, entry_path, **kwargs):
    # Fixed diagnostics: never echo file contents, validation input or credentials.
    try:
        bundle = ReviewedBundle.model_validate_json(Path(bundle_path).read_text())
    except FileNotFoundError:
        return dict(status='BLOCKED', blockers=['REVIEW_REQUIRED'], orders_enabled=False, broker_connected=False)
    except (OSError, ValueError):
        return dict(status='BLOCKED', blockers=['INVALID_REVIEW_FILE'], orders_enabled=False, broker_connected=False)
    try:
        entry = Entry.model_validate_json(Path(entry_path).read_text())
    except (OSError, ValueError):
        return dict(status='BLOCKED', blockers=['INVALID_PROPOSAL_FILE'], orders_enabled=False, broker_connected=False)
    return check(bundle, entry, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--proposal', required=True)
    parser.add_argument('--account-id', required=True)
    parser.add_argument('--approved-bundle-hash', required=True,
                        help='Separately reviewed deployment pin; not supplied by proposal producer')
    args = parser.parse_args()
    report = load_check(args.bundle, args.proposal, account_id=args.account_id,
                        approved_bundle_hash=args.approved_bundle_hash,
                        now=datetime.now(timezone.utc))
    print(json.dumps(report, sort_keys=True))
    return 2 if report['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
