#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests>=2.32,<3",
#   "click>=8.2,<9",
#   "pydantic>=2.11,<3",
# ]
# ///

import logging
import re
import sys
import urllib.parse
from collections.abc import Iterator

import click
import pydantic
import requests

LOGGER = logging.getLogger()
logging.root.addHandler(logging.StreamHandler(sys.stderr))


def setup_logging(verbosity: int) -> None:
    # Setup logging level based on verbosity
    match verbosity:
        case 0:
            LOGGER.setLevel(logging.ERROR)
        case 1:
            LOGGER.setLevel(logging.WARNING)
        case 2:
            LOGGER.setLevel(logging.INFO)
        case 3:
            LOGGER.setLevel(logging.DEBUG)
        case _:
            LOGGER.setLevel(0)


def process_api_response[T: object](
    r: requests.Response,
    *,
    expected_type: type[T],
) -> T:
    """
    Process the response from the firefly api, if the response contains an
    error, raise an explicit exception containing the api response, otherwise
    try to validate the returned data and convert it to the expected python
    type.

    :param r: The response from the api.
    :param expected_type: The expected type of the response.
    """
    try:
        data = r.json()
    except requests.JSONDecodeError as e:
        raise ValueError(f"Unexpected response format: {r.text}") from e

    match data:
        case {"message": str() as message, "exception": str() as exception}:
            raise RuntimeError(exception + ": " + message)
        case {"data": object() as actual_data}:
            adapter = pydantic.TypeAdapter(expected_type)
            return adapter.validate_python(actual_data)
        case _:
            raise ValueError(f"Unexpected response format: {data}")


def process_paginated_api_response[T: object](
    r: requests.Response,
    *,
    expected_type: type[T],
    session: requests.Session,
) -> Iterator[T]:
    """
    Similar to process_api_response, excepts that the data of the response is
    always expected to be a list, and may contain multiple pages.  For this
    function, the expected type is not the one of the data, but of the items
    inside the data list.  All pages will be accessed, lazily, when reaching
    the end of the previous page.
    """
    try:
        data = r.json()
    except requests.JSONDecodeError as e:
        raise ValueError(f"Unexpected response format: {r.text}") from e

    yield from process_api_response(r, expected_type=list[expected_type])

    match data:
        case {"links": {"next": str() as next}}:
            yield from process_paginated_api_response(
                session.get(next),
                expected_type=expected_type,
                session=session,
            )
        case _:
            pass


class FireflySession(requests.Session):
    """
    Session class to interact with the firefly api.  This session offers some
    helpers to facilitate the interaction with the api.
    """

    def __init__(self, base_url: str, api_token: str):
        super().__init__()
        self.base_url = base_url
        self.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
            },
        )

    def request(
        self, method: str, url: str, *args: object, **kwargs: object
    ) -> requests.Response:
        # Prefix the url received with the firefly base url
        url = urllib.parse.urljoin(self.base_url, url)
        return super().request(method, url, *args, **kwargs)


def get_transactions_with_notes(
    session: requests.Session, account: str
) -> Iterator[dict]:
    """
    Get all the transactions of the given account that have a note specifying
    another beneficiary name.
    """
    query = {
        "account_is": account,
        "type": "withdrawal",
        "notes_contain": "Original account name",
    }
    for page in process_paginated_api_response(
        session.get(
            "/api/v1/search/transactions",
            params={"query": " ".join(f'{k}:"{v}"' for k, v in query.items())},
        ),
        expected_type=dict,
        session=session,
    ):
        yield from page["attributes"]["transactions"]


def create_fixing_rule(
    session: requests.Session, account: str, beneficiary: str, group: str
) -> dict:
    """
    Create a rule that triggers for each transaction going to the given
    account, which has a note containing the rightful beneficiary of the
    transaction. Place the rule in the given group.
    """
    LOGGER.debug("Creating rule %s in group %s", beneficiary, group)
    rule = process_api_response(
        session.post(
            "/api/v1/rules",
            json={
                "title": beneficiary,
                "rule_group_title": group,
                "strict": True,
                "trigger": "store-journal",
                "triggers": [
                    {
                        "type": "transaction_type",
                        "value": "withdrawal",
                    },
                    {
                        "type": "to_account_is",
                        "value": account,
                    },
                    {
                        "type": "notes_contains",
                        "value": f"Original account name: {beneficiary}",
                    },
                ],
                "actions": [
                    {
                        "type": "set_destination_account",
                        "value": beneficiary,
                    },
                ],
            },
        ),
        expected_type=dict,
    )

    # Trigger the rule to apply the change to the transactions that match it
    rule_id = rule["id"]
    LOGGER.debug("Triggering newly created rule %s (%s)", rule_id, beneficiary)
    session.post(f"/api/v1/rules/{rule_id}/trigger", json={}).raise_for_status()
    return rule


@click.command()
@click.option(
    "--verbose",
    "-v",
    count=True,
    required=False,
    default=0,
    help="Verbosity of the script",
)
@click.option(
    "--url",
    "-u",
    required=True,
    envvar="FIREFLY_III_URL",
    help=(
        "The url where the firefly api can be reached, "
        "i.e. https://demo.firefly-iii.org/."
    ),
    show_envvar=True,
)
@click.option(
    "--access-token",
    "-t",
    required=True,
    envvar="FIREFLY_III_ACCESS_TOKEN",
    help="A user token to interact with the api",
    show_envvar=True,
)
@click.option(
    "--group",
    "-g",
    required=True,
    envvar="FIREFLY_III_RULE_GROUP",
    help="The name of the group in which the rules should be created",
    show_envvar=True,
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    envvar="DRY_RUN",
    help=(
        "When set to true, only perform get requests to the api, and display "
        "an overview of the changes that would be made if the script was run "
        "without the flag."
    ),
    show_envvar=True,
)
@click.argument("account", envvar="ACCOUNT_NAME", nargs=1)
def main(
    verbose: int, url: str, access_token: str, group: str, dry_run: bool, account: str
) -> None:
    """
    This tool helps you manage and cleanup transactions imported using gocardless for
    which the destination account is a common payment platform such as visa, by updating
    the destination account to match the actual business you made the payment to.
    """
    setup_logging(verbose)

    with FireflySession(
        url,
        access_token,
    ) as session:
        # Get and print the current user, to validate that the api setup works
        user = process_api_response(
            session.get("/api/v1/about/user"),
            expected_type=dict,
        )
        LOGGER.info("Authenticated as %s", user["attributes"]["email"])

        # For each account provided, look for transactions that contain a note
        # describing the true payment beneficiary
        missing_rules: set[str] = set()
        for transaction in get_transactions_with_notes(session, account):
            LOGGER.debug(
                "Transaction %s: %s",
                transaction["transaction_journal_id"],
                transaction["notes"],
            )

            # Extract the beneficiary name from the notes of the transaction
            matched = re.search(
                r"Original account name: ([^\n]*)", transaction["notes"]
            )
            if not matched:
                LOGGER.error(
                    "Failed to match note of transaction %s: %s",
                    transaction["transaction_journal_id"],
                    transaction["notes"],
                )
                continue

            # Add the account name to the set of missing rules
            missing_rules.add(matched.group(1).strip())

        if not missing_rules:
            LOGGER.info(
                "No transaction towards account %s need fixing, no rule to create",
                account,
            )
            return

        LOGGER.info(
            "Account %s contains transactions towards %d other beneficiaries:\n- %s",
            account,
            len(missing_rules),
            "\n- ".join(missing_rules),
        )
        LOGGER.info("New rules will be created in rule group %s", group)

        if dry_run:
            # Nothing else to do, we are in dry-run mode
            return

        # Create all the rules, then execute them
        for beneficiary in missing_rules:
            rule = create_fixing_rule(session, account, beneficiary, group)
            LOGGER.info(
                "Successfully created rule %s (%s)",
                rule["attributes"]["title"],
                rule["id"],
            )


main()
