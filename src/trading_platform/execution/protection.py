"""Pure recovery policy. Returning an action is not confirmation it executed."""


def recovery_action(*,owned,open_quantity,protected,connected,repair_attempted,repair_confirmed):
    if not owned: return 'OBSERVE_EXTERNAL'
    if open_quantity<=0: return 'RECONCILE'
    if protected or repair_confirmed: return 'PROTECTED'
    if not connected: return 'HALT_UNABLE_TO_PROTECT_OR_CLOSE'
    return 'REQUEST_OWNED_CLOSE' if repair_attempted else 'REQUEST_PROTECTION_REPAIR'
