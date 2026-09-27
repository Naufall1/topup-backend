"""Manual smoke test against the configured Digiflazz BASE_URL.

Run from api/: python -m scripts.smoke_test
Uses DIGIFLAZZ_TESTING_MODE (see config.py) to control whether the created
transaction hits Digiflazz's sandbox or live endpoint.
"""
import time
from uuid import uuid4

from digiflazz import Digiflazz
from schemas import TransactionSchema

if __name__ == "__main__":
    digiflazz = Digiflazz()

    saldo = digiflazz.get_saldo()
    print(saldo)

    transaction = TransactionSchema(
        ref_id=str(uuid4()),
        buyer_sku_code="xld10",
        customer_no="087800001234",
    )
    transaction_response = digiflazz.create_transaction(transaction)
    print(transaction_response)

    time.sleep(5)  # Wait for the transaction to be processed
    status_response = digiflazz.check_transaction_status(transaction_response.ref_id)
    print(status_response)
