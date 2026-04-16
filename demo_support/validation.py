from accounts import BankAccount
from shared.enums import Currency, TransactionPriority, TransactionType

from demo_support.data import ACCOUNT_PREPARATION_ACTIONS, DEMO_SCHEDULE_NAMES


def _validate_client_definitions(client_definitions: dict[str, dict]) -> None:
    required_fields = {"full_name", "birth_date", "contacts", "pin_code"}
    for client_key, definition in client_definitions.items():
        missing_fields = required_fields - definition.keys()
        if missing_fields:
            raise ValueError(f"Client definition '{client_key}' is missing fields: {sorted(missing_fields)}")


def _validate_account_definitions(account_definitions: dict[str, dict], client_keys: set[str]) -> None:
    required_fields = {"client", "account_type", "currency"}
    for account_key, definition in account_definitions.items():
        missing_fields = required_fields - definition.keys()
        if missing_fields:
            raise ValueError(f"Account definition '{account_key}' is missing fields: {sorted(missing_fields)}")
        if definition["client"] not in client_keys:
            raise ValueError(f"Account definition '{account_key}' references unknown client '{definition['client']}'")
        if not isinstance(definition["account_type"], type) or not issubclass(definition["account_type"], BankAccount):
            raise ValueError(f"Account definition '{account_key}' has invalid account_type")
        if not isinstance(definition["currency"], Currency):
            raise ValueError(f"Account definition '{account_key}' has invalid currency")


def validate_account_preparation_steps(
    account_preparation_steps: tuple[dict, ...],
    account_keys: set[str],
) -> None:
    for index, step in enumerate(account_preparation_steps, start=1):
        action = step.get("action")
        if action not in ACCOUNT_PREPARATION_ACTIONS:
            raise ValueError(f"Account preparation step #{index} has unknown action '{action}'")
        if step.get("account") not in account_keys:
            raise ValueError(f"Account preparation step #{index} references unknown account '{step.get('account')}'")
        if action == "deposit" and "amount" not in step:
            raise ValueError(f"Account preparation step #{index} is missing amount")
        if action == "invest_in_asset" and {"asset_type", "amount"} - step.keys():
            raise ValueError(f"Account preparation step #{index} must define asset_type and amount")


def validate_transaction_group_definitions(
    transaction_group_definitions: tuple[dict, ...],
    account_keys: set[str],
) -> None:
    for group_index, group in enumerate(transaction_group_definitions, start=1):
        schedule = group.get("schedule")
        if schedule is not None and schedule not in DEMO_SCHEDULE_NAMES:
            raise ValueError(f"Transaction group #{group_index} has unknown schedule '{schedule}'")
        cases = group.get("cases")
        if not isinstance(cases, tuple):
            raise ValueError(f"Transaction group #{group_index} must define cases as tuple")

        for case_index, case in enumerate(cases, start=1):
            if not isinstance(case.get("transaction_type"), TransactionType):
                raise ValueError(f"Transaction case #{group_index}.{case_index} has invalid transaction_type")
            if not isinstance(case.get("currency"), Currency):
                raise ValueError(f"Transaction case #{group_index}.{case_index} has invalid currency")
            if case.get("sender") not in account_keys:
                raise ValueError(
                    f"Transaction case #{group_index}.{case_index} references unknown sender '{case.get('sender')}'"
                )
            if "priority" in case and not isinstance(case["priority"], TransactionPriority):
                raise ValueError(f"Transaction case #{group_index}.{case_index} has invalid priority")
            if "scheduled_for" in case and case["scheduled_for"] not in DEMO_SCHEDULE_NAMES:
                raise ValueError(f"Transaction case #{group_index}.{case_index} has invalid scheduled_for alias")

            has_internal_recipient = "recipient_account" in case
            has_external_recipient = "recipient_external" in case
            if has_internal_recipient == has_external_recipient:
                raise ValueError(
                    f"Transaction case #{group_index}.{case_index} must define exactly one recipient source"
                )
            if has_internal_recipient and case["recipient_account"] not in account_keys:
                raise ValueError(
                    f"Transaction case #{group_index}.{case_index} references unknown recipient account "
                    f"'{case['recipient_account']}'"
                )
            if has_external_recipient:
                recipient_external = case["recipient_external"]
                if (
                    not isinstance(recipient_external, tuple)
                    or len(recipient_external) != 2
                    or not isinstance(recipient_external[0], str)
                ):
                    raise ValueError(
                        f"Transaction case #{group_index}.{case_index} has invalid external recipient structure"
                    )
                external_kind, external_number = recipient_external
                if external_kind == "missing_demo_account":
                    if external_number is not None:
                        raise ValueError(
                            f"Transaction case #{group_index}.{case_index} missing_demo_account must use None number"
                        )
                elif not isinstance(external_number, int):
                    raise ValueError(
                        f"Transaction case #{group_index}.{case_index} external recipient number must be integer"
                    )


def validate_demo_definitions(
    client_definitions: dict[str, dict],
    account_definitions: dict[str, dict],
    account_preparation_steps: tuple[dict, ...],
    transaction_group_definitions: tuple[dict, ...],
) -> None:
    client_keys = set(client_definitions)
    account_keys = set(account_definitions)
    _validate_client_definitions(client_definitions)
    _validate_account_definitions(account_definitions, client_keys)
    validate_account_preparation_steps(account_preparation_steps, account_keys)
    validate_transaction_group_definitions(transaction_group_definitions, account_keys)
