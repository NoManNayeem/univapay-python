from __future__ import annotations
from typing import Optional

from ..client import UnivapayClient, UnivapayHTTPError
from ..debug import dprint, djson
from ..models import TransactionToken


def _tokens_base(client: UnivapayClient) -> str:
    return client._path("transaction-tokens")


def _validate_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required and must be a non-empty string.")


class TokensAPI:
    """
    Transaction Tokens API (read-only on the server).

    Notes:
    - Transaction tokens are typically created client-side by the Univapay widget.
    - Use this API to fetch token details server-side when needed (e.g., auditing).
    """

    def __init__(self, client: UnivapayClient):
        self.client = client
        dprint("tokens.__init__()", {"base_path": _tokens_base(self.client)})

    def get(self, token_id: str) -> TransactionToken:
        """
        Fetch a transaction token by ID.

        Parameters
        ----------
        token_id : str
            The transaction token id (from the FE widget callback).

        Returns
        -------
        TransactionToken
            A typed model of the token response (extra fields are preserved).

        Raises
        ------
        ValueError
            If token_id is empty/invalid.
        UnivapayHTTPError
            If the HTTP call fails.
        """
        _validate_id("token_id", token_id)
        dprint("tokens.get()", {"token_id": token_id})
        resp = self.client.get(f"{_tokens_base(self.client)}/{token_id}")
        djson("tokens.get response", resp)
        return TransactionToken.model_validate(resp)

    def try_get(self, token_id: str) -> Optional[TransactionToken]:
        """
        Like `get()` but returns None if the token does not exist (HTTP 404).
        Propagates other HTTP errors.
        """
        _validate_id("token_id", token_id)
        dprint("tokens.try_get()", {"token_id": token_id})
        try:
            return self.get(token_id)
        except UnivapayHTTPError as e:
            if e.status == 404:
                dprint("tokens.try_get: not found", {"token_id": token_id})
                return None
            dprint("tokens.try_get: error", {"status": e.status})
            raise
