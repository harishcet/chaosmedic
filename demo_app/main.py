"""FastAPI Microservice for Demo Application."""
from __future__ import annotations

import traceback
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from demo_app.service import calculate_discount, process_order, get_health_status

app = FastAPI(title="Demo Billing Service", version="1.0.0")


@app.get("/healthz")
def healthz():
    return get_health_status()


@app.post("/api/checkout")
def checkout(payload: dict):
    """Checkout endpoint that triggers the deliberate zero-division bug if factor is 0."""
    try:
        res = process_order(payload)
        return res
    except Exception as e:
        tb = traceback.format_exc()
        # Return HTTP 500 with stack trace for ChaosMedic detection
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": str(e),
                "stack_trace": tb,
                "service": "demo-billing-service",
                "endpoint": "/api/checkout"
            }
        )


@app.get("/api/calculate")
def calculate(price: float = 100.0, quantity: int = 2, discount_factor: float = 0.0):
    """Direct calculation endpoint for testing."""
    try:
        res = calculate_discount(price, quantity, discount_factor)
        return {"price": price, "quantity": quantity, "discount_factor": discount_factor, "result": res}
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content={
                "error": "ZeroDivisionError",
                "message": str(e),
                "stack_trace": tb,
                "service": "demo-billing-service",
                "endpoint": "/api/calculate"
            }
        )


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)


if __name__ == "__main__":
    main()
