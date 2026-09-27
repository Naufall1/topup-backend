import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import config
from digiflazz import Digiflazz, DigiflazzHTTPError, DigiflazzResponseError
from routers import games, kasir, orders, transactions

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()
digiflazz = Digiflazz()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(kasir.router)
app.include_router(games.router)
app.include_router(orders.router)


@app.exception_handler(DigiflazzHTTPError)
async def digiflazz_http_error_handler(request: Request, exc: DigiflazzHTTPError):
    logger.error("Digiflazz HTTP error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "Upstream Digiflazz request failed"})


@app.exception_handler(DigiflazzResponseError)
async def digiflazz_response_error_handler(request: Request, exc: DigiflazzResponseError):
    logger.error("Digiflazz response error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/saldo")
def get_saldo():
    return digiflazz.get_saldo().model_dump()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)