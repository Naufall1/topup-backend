import logging
from enum import Enum
from pydantic import BaseModel
from typing import TypeVar, Type

import requests

from config import config
from security import sign_request
from schemas import SaldoSchema, PriceListSchema, TransactionResponseSchema, TransactionSchema


logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class DigiflazzError(Exception):
    """Base error for Digiflazz API interactions."""


class DigiflazzHTTPError(DigiflazzError):
    """Non-200 HTTP response from Digiflazz."""


class DigiflazzResponseError(DigiflazzError):
    """Digiflazz returned an application-level error (rc not in the success set)."""

    def __init__(self, message: str, rc: str | None = None):
        super().__init__(message)
        self.rc = rc


class DigiflazzAction(Enum):
    DEPO = "depo"
    PRICELIST = "pricelist"


class Digiflazz:
    def __init__(self):
        self.base_url = config.BASE_URL
        self._session = requests.Session()
        if config.HTTP_PROXY:
            self._session.proxies.update({"http": config.HTTP_PROXY, "https": config.HTTP_PROXY})

    def _post(self, endpoint: str, payload: dict) -> dict:
        response = self._session.post(f"{self.base_url}/{endpoint}", json=payload)

        if response.status_code == 204:
            return {}

        try:
            body = response.json()
        except ValueError:
            raise DigiflazzHTTPError(f"API request failed with status code {response.status_code}: {response.text}")

        data = body.get("data", {})
        rc = data.get("rc") if isinstance(data, dict) else None

        # Digiflazz sometimes wraps application-level errors (e.g. rc 45 "IP
        # Anda tidak kami kenali") in a non-200 HTTP response, not just a 200
        # with an error rc — check the body for an actionable rc first, on
        # any status code, so callers get the specific DigiflazzResponseError
        # (with the real rc/message) instead of a generic DigiflazzHTTPError.
        if rc and rc not in ["00", "02", "03"]:
            logger.warning("raw response: %s", response.text)
            raise DigiflazzResponseError(f"API error: {data.get('message', 'Unknown error')}", rc=rc)

        if response.status_code != 200:
            raise DigiflazzHTTPError(f"API request failed with status code {response.status_code}: {response.text}")

        return body

    def _parse_response(self, schema: Type[T], response: dict) -> T:
        return schema(**response)

    def get_saldo(self):
        response = self._post("cek-saldo", {
            "cmd": "deposit",
            "username": config.USERNAME,
            "sign": sign_request(DigiflazzAction.DEPO.value)
        })
        return self._parse_response(SaldoSchema, response.get("data", {}))

    def get_price_list(self):
        response = self._post("price-list", {
            "cmd": "prepaid",
            "username": config.USERNAME,
            "sign": sign_request(DigiflazzAction.PRICELIST.value)
        })
        return [self._parse_response(PriceListSchema, item) for item in response.get("data", [])]

    def create_transaction(self, transaction: TransactionSchema) -> TransactionResponseSchema:
        payload = {
            "username": config.USERNAME,
            "buyer_sku_code": transaction.buyer_sku_code,
            "customer_no": transaction.customer_no,
            "ref_id": transaction.ref_id,
            "sign": sign_request(transaction.ref_id),
            "testing": config.DIGIFLAZZ_TESTING_MODE
        }
        response = self._post("transaction", payload)
        return self._parse_response(TransactionResponseSchema, response.get("data", {}))

    def check_transaction_status(self, ref_id: str) -> TransactionResponseSchema:
        payload = {
            "username": config.USERNAME,
            "ref_id": ref_id,
            "sign": sign_request(ref_id)
        }
        response = self._post("transaction", payload)
        return self._parse_response(TransactionResponseSchema, response.get("data", {}))