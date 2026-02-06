# trips/services/facturapi.py
from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional

import requests
from django.conf import settings

from trips.models import CartaPorteCFDI, Trip
from trips.facturapi_payloads import build_cfdi_payload

logger = logging.getLogger(__name__)


# ======================================================
# Errores controlados
# ======================================================
class FacturapiError(Exception):
    """Error controlado para Facturapi."""
    pass


# ======================================================
# Configuración
# ======================================================
def _get_facturapi_config():
    """
    Espera estas variables en settings.py:

    FACTURAPI_API_KEY = "sk_live_xxx" o "sk_test_xxx"
    FACTURAPI_BASE_URL = "https://www.facturapi.io/v2"
    FACTURAPI_TIMEOUT_SECONDS = 30  (opcional)
    """
    api_key = getattr(settings, "FACTURAPI_API_KEY", None)
    base_url = getattr(settings, "FACTURAPI_BASE_URL", "https://www.facturapi.io/v2")
    timeout = int(getattr(settings, "FACTURAPI_TIMEOUT_SECONDS", 30) or 30)

    if not api_key:
        raise FacturapiError("FACTURAPI_API_KEY no está configurado.")

    return api_key, base_url.rstrip("/"), timeout


# ======================================================
# HTTP helper
# ======================================================
def _facturapi_request(
    *,
    method: str,
    url: str,
    api_key: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise FacturapiError(f"Error de red con Facturapi: {e}")

    content_type = resp.headers.get("Content-Type", "")

    # ---------- JSON ----------
    if "application/json" not in content_type:
        # Log duro para diagnósticos (HTML 404, etc.)
        logger.error(
            "FACTURAPI NON-JSON HTTP %s %s\nCT=%s\nBody=%s",
            resp.status_code,
            url,
            content_type,
            (resp.text or "")[:2000],
        )
        raise FacturapiError(
            f"Respuesta no JSON de Facturapi ({resp.status_code}): {resp.text[:300]}"
        )

    try:
        data = resp.json()
    except Exception:
        logger.error(
            "FACTURAPI JSON PARSE ERROR HTTP %s %s\nBody=%s",
            resp.status_code,
            url,
            (resp.text or "")[:2000],
        )
        raise FacturapiError(
            f"Respuesta JSON inválida de Facturapi ({resp.status_code})."
        )

    if resp.status_code >= 400:
        # Log request/response para debug
        logger.error(
            "FACTURAPI HTTP %s %s\nHeaders=%s\nPayload=%s\nResponseCT=%s\nResponse=%s",
            resp.status_code,
            url,
            json.dumps({k: ("***" if k.lower() == "authorization" else v) for k, v in headers.items()}, ensure_ascii=False, indent=2),
            json.dumps(payload or {}, ensure_ascii=False, indent=2),
            content_type,
            json.dumps(data, ensure_ascii=False),
        )

        msg = data.get("message") or data.get("error") or "Error desconocido en Facturapi"
        details = data.get("details")
        if details:
            msg = f"{msg}\n{json.dumps(details, indent=2, ensure_ascii=False)}"
        raise FacturapiError(msg)

    return data


# ======================================================
# Crear CFDI en Facturapi
# ======================================================
def create_invoice_in_facturapi(*, carta: CartaPorteCFDI, trip: Trip) -> Dict[str, Any]:
    """
    - Construye payload desde modelos reales
    - Envía a Facturapi
    - Devuelve dict con:
        {
          "payload": payload_enviado,
          "response": respuesta_facturapi_normalizada
        }
    """

    # ----------------------------
    # Validaciones duras
    # ----------------------------
    if carta.status == "stamped" and carta.uuid:
        raise FacturapiError("Este CFDI ya fue timbrado.")

    if carta.status == "canceled":
        raise FacturapiError("Este CFDI está cancelado y no puede timbrarse.")

    if not carta.customer_id:
        raise FacturapiError("La Carta Porte no tiene cliente (receptor).")

    if not trip.operator_id:
        raise FacturapiError("El viaje no tiene operador asignado.")

    if carta.total <= 0:
        raise FacturapiError("El total del CFDI debe ser mayor a 0.")

    # ----------------------------
    # Configuración
    # ----------------------------
    api_key, base_url, timeout = _get_facturapi_config()

    # ----------------------------
    # Payload CFDI
    # ----------------------------
    payload = build_cfdi_payload(
        carta=carta,
        trip_operator=trip.operator,
    )

    # 🚫 Facturapi NO permite external_reference -> NO agregar nada extra aquí.

    # ----------------------------
    # Endpoint Facturapi
    # ----------------------------
    url = f"{base_url}/invoices"

    # ----------------------------
    # Request
    # ----------------------------
    response = _facturapi_request(
        method="POST",
        url=url,
        api_key=api_key,
        payload=payload,
        timeout=timeout,
    )

    # ----------------------------
    # Normalización respuesta
    # ----------------------------
    normalized = {
        "id": response.get("id"),
        "uuid": response.get("uuid"),
        "status": response.get("status"),
        "pdf_url": response.get("pdf_url") or response.get("pdf"),
        "xml_url": response.get("xml_url") or response.get("xml"),
        "raw": response,
    }

    return {
        "payload": payload,
        "response": normalized,
    }
