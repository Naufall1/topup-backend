# This is webhook handler for digiflazz, it will receive webhook from digiflazz and process it accordingly
import hashlib
import hmac
import logging
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import config
from session import get_db
from models import Transaction

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

DBSession = Annotated[Session, Depends(get_db)]

class WebhookPayload(BaseModel):
    ref_id: str
    buyer_sku_code: str
    customer_no: str
    sn: str
    price: float
    tele: str
    wa: str
    status: str

app = FastAPI()

def handle_update_transaction(payload: dict, db: Session) -> None:
    payload = WebhookPayload(**payload)

    # Update the transaction in the database
    transaction = db.query(Transaction).filter(Transaction.ref_id == payload.ref_id).first()
    if transaction:
        logger.info("Updating transaction %s with status %s", transaction.ref_id, payload.status)
        transaction.status = payload.status.lower()
        transaction.price = payload.price
        db.commit()


@app.post("/webhook")
async def handle_webhook(request: Request, db: DBSession):
    event = request.headers.get("X-Digiflazz-Event")
    user_agent = request.headers.get("User-Agent")
    if event != "update" or user_agent != "Digiflazz-Hookshot":
        logger.warning("Rejected webhook: unrecognized event/user-agent (event=%s, user_agent=%s)", event, user_agent)
        raise HTTPException(status_code=400, detail="Unrecognized webhook event")

    raw_signature = request.headers.get("X-Hub-Signature")
    if not raw_signature or "=" not in raw_signature:
        raise HTTPException(status_code=401, detail="Missing or malformed signature")
    signature = raw_signature.split("sha1=")[-1]

    body = await request.body()
    computed_signature = hmac.new(config.WEBHOOK_SECRET.encode(), body, hashlib.sha1).hexdigest()
    if not hmac.compare_digest(signature, computed_signature):
        logger.warning("Rejected webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    handle_update_transaction(payload.get("data", {}), db)

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)