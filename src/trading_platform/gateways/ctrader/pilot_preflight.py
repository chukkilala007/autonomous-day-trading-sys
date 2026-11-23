"""Pure preflight for a strategy-scoped autonomous demo pilot; never enables orders."""
from trading_platform.contracts.config import Instance
from trading_platform.contracts.values import digest,utc
from .attended_binding import ReviewedBundle
from .pilot import PilotMandate


def check(mandate,instance,bundle,*,approved_mandate_hash,approved_bundle_hash,now):
    mandate=PilotMandate.model_validate_json(mandate.model_dump_json())
    instance=Instance.model_validate_json(instance.model_dump_json())
    bundle=ReviewedBundle.model_validate_json(bundle.model_dump_json())
    if digest(mandate)!=approved_mandate_hash or digest(bundle)!=approved_bundle_hash:
        raise ValueError('autonomous pilot review pin mismatch')
    if (instance.mode!='demo' or instance.account.environment!='demo'
            or instance.account.broker_account!=mandate.account_id
            or instance.account.alias!=mandate.account_alias
            or instance.instance_id!=mandate.instance or instance.strategy!=mandate.package
            or instance.hash!=mandate.config_hash or mandate.instrument not in instance.universe):
        raise ValueError('autonomous pilot strategy binding mismatch')
    if (bundle.policy.account_id!=mandate.account_id or bundle.policy.instrument!=mandate.instrument
            or bundle.quantity!=mandate.quantity or digest(bundle)!=mandate.reviewed_bundle_hash
            or bundle.source_hash!=mandate.source_hash or bundle.image_digest!=mandate.image_digest):
        raise ValueError('autonomous pilot broker review mismatch')
    now=utc(now)
    if not mandate.valid_from<=now<mandate.submit_before or not bundle.policy.observed_at<=now<bundle.policy.valid_until:
        raise ValueError('autonomous pilot inputs expired')
    return dict(status='PREPARED_DISABLED',orders_enabled=False,account_id=mandate.account_id,
                test_id=mandate.test_id,instance=mandate.instance,instrument=mandate.instrument,
                mandate_hash=approved_mandate_hash,bundle_hash=approved_bundle_hash)
