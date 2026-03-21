"""
EveryPay / SEB E-commerce API v4 client.

Handles one-off payments with card tokenization, MIT recurring charges,
payment status queries, and refunds.
"""

import os
import uuid
import logging
import datetime
import httpx

logger = logging.getLogger("vrekini.everypay")

# --- Configuration ---
API_USERNAME = os.getenv("EVERYPAY_API_USERNAME", "")
API_SECRET = os.getenv("EVERYPAY_API_SECRET", "")
ACCOUNT_NAME = os.getenv("EVERYPAY_ACCOUNT_NAME", "")
API_URL = os.getenv("EVERYPAY_API_URL", "https://igw-seb-demo.every-pay.com/api/v4")

# Plan prices (EUR)
PLAN_PRICES = {
    "starter_monthly": 9.99,
    "starter_yearly": 99.00,
    "business_monthly": 19.99,
    "business_yearly": 199.00,
}


def _auth():
    """HTTP Basic Auth tuple."""
    return (API_USERNAME, API_SECRET)


def _timestamp():
    """ISO 8601 timestamp for API requests."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nonce():
    """Unique nonce for request deduplication."""
    return uuid.uuid4().hex


def is_configured():
    """Return True if EveryPay credentials are set."""
    return bool(API_USERNAME and API_SECRET and ACCOUNT_NAME)


def get_plan_price(tier: str, cycle: str) -> float:
    """Return the price for a given tier and billing cycle."""
    key = f"{tier}_{cycle}"
    return PLAN_PRICES.get(key, 0.0)


def initiate_payment(
    amount: float,
    order_reference: str,
    customer_url: str,
    email: str = "",
    customer_ip: str = "",
    request_token: bool = True,
    locale: str = "lv",
) -> dict:
    """
    Initiate a one-off payment with optional card tokenization.

    For initial subscriptions we use request_token=True with
    token_agreement=recurring so the card token can be used for
    future MIT payments.

    Returns the full API response including payment_link.
    """
    payload = {
        "api_username": API_USERNAME,
        "account_name": ACCOUNT_NAME,
        "amount": round(amount, 2),
        "order_reference": order_reference,
        "nonce": _nonce(),
        "timestamp": _timestamp(),
        "customer_url": customer_url,
        "locale": locale,
        "email": email,
        "preferred_country": "LV",
        "integration_details": {
            "integration": "Custom",
            "software": "V-Rekini",
            "version": "1.0",
        },
    }

    if customer_ip:
        payload["customer_ip"] = customer_ip

    if request_token and "demo" not in API_URL:
        payload["request_token"] = True
        payload["token_agreement"] = "recurring"
        payload["token_consent_agreed"] = True

    resp = httpx.post(
        f"{API_URL}/payments/oneoff",
        json=payload,
        auth=_auth(),
        timeout=30,
    )
    if resp.status_code >= 400:
        logger.error("EveryPay oneoff error %s: %s", resp.status_code, resp.text)
    resp.raise_for_status()
    data = resp.json()
    logger.info("Payment initiated: ref=%s state=%s",
                data.get("payment_reference"), data.get("payment_state"))
    return data


def get_payment_status(payment_reference: str) -> dict:
    """
    Get the current status of a payment.

    Returns the full payment object including payment_state,
    cc_details (with token if tokenized), and amounts.
    """
    resp = httpx.get(
        f"{API_URL}/payments/{payment_reference}",
        params={"api_username": API_USERNAME},
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def charge_mit(
    amount: float,
    order_reference: str,
    token: str,
    email: str = "",
    merchant_ip: str = "",
) -> dict:
    """
    Initiate and complete a Merchant Initiated Transaction (recurring charge).

    Step 1: POST /payments/mit to create the payment
    Step 2: POST /payments/charge to complete it with the stored token
    """
    # Step 1: Initiate MIT
    mit_payload = {
        "api_username": API_USERNAME,
        "account_name": ACCOUNT_NAME,
        "amount": round(amount, 2),
        "order_reference": order_reference,
        "nonce": _nonce(),
        "timestamp": _timestamp(),
        "email": email,
        "token_agreement": "recurring",
        "merchant_ip": merchant_ip or "127.0.0.1",
        "integration_details": {
            "integration": "Custom",
            "software": "V-Rekini",
            "version": "1.0",
        },
    }

    resp = httpx.post(
        f"{API_URL}/payments/mit",
        json=mit_payload,
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    mit_data = resp.json()

    payment_reference = mit_data.get("payment_reference", "")
    if not payment_reference:
        logger.error("MIT initiation failed: no payment_reference returned")
        return mit_data

    # Step 2: Complete with token
    charge_payload = {
        "api_username": API_USERNAME,
        "nonce": _nonce(),
        "timestamp": _timestamp(),
        "payment_reference": payment_reference,
        "token_details": {
            "token": token,
        },
    }

    resp = httpx.post(
        f"{API_URL}/payments/charge",
        json=charge_payload,
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    charge_data = resp.json()
    logger.info("MIT charge completed: ref=%s state=%s",
                payment_reference, charge_data.get("payment_state"))
    return charge_data


def refund_payment(payment_reference: str, amount: float) -> dict:
    """Refund a settled payment (full or partial)."""
    payload = {
        "api_username": API_USERNAME,
        "amount": round(amount, 2),
        "timestamp": _timestamp(),
        "payment_reference": payment_reference,
        "nonce": _nonce(),
    }

    resp = httpx.post(
        f"{API_URL}/payments/refund",
        json=payload,
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_token_status(token: str) -> dict:
    """Check the status of a stored card token."""
    resp = httpx.get(
        f"{API_URL}/tokens/{token}/status",
        params={"api_username": API_USERNAME},
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def deactivate_token(token: str) -> dict:
    """Deactivate a stored card token."""
    payload = {
        "api_username": API_USERNAME,
        "token": token,
    }

    resp = httpx.post(
        f"{API_URL}/tokens/deactivate",
        json=payload,
        auth=_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
