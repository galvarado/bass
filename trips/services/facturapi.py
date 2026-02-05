# trips/services/facturapi.py
from __future__ import annotations

import json
import requests
from typing import Dict, Any

from django.conf import settings
from django.utils import timezone

from trips.models import CartaPorteCFDI, Trip
from trips.facturapi_payloads import build_cfdi_payload


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
    """
    api_key = getattr(settings, "FACTURAPI_API_KEY", None)
    base_url = getattr(settings, "FACTURAPI_BASE_URL", "https://www.facturapi.io/v2")

    if not api_key:
        raise FacturapiError("FACTURAPI_API_KEY no está configurado.")

    return api_key, base_url.rstrip("/")


# ======================================================
# HTTP helper
# ======================================================
def _facturapi_request(
    *,
    method: str,
    url: str,
    api_key: str,
    payload: Dict[str, Any] | None = None,
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
            timeout=30,
        )
    except requests.RequestException as e:
        raise FacturapiError(f"Error de red con Facturapi: {e}")

    # Intenta parsear JSON siempre
    try:
        data = resp.json()
    except Exception:
        raise FacturapiError(
            f"Respuesta no JSON de Facturapi ({resp.status_code}): {resp.text}"
        )

    if resp.status_code >= 400:
        # Facturapi suele mandar {message, details}
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
          "response": respuesta_facturapi
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
    api_key, base_url = _get_facturapi_config()

    # ----------------------------
    # Payload CFDI (ALINEADO)
    # ----------------------------
    payload = build_cfdi_payload(
        carta=carta,
        trip_operator=trip.operator,
    )

    # Opcional: referencia interna
    payload["external_reference"] = f"TRIP-{trip.id}-CP-{carta.id}"

    # ----------------------------
    # Endpoint Facturapi
    # ----------------------------
    # Facturapi:
    # POST /invoices
    url = f"{base_url}/invoices"

    # ----------------------------
    # Request
    # ----------------------------
    response = _facturapi_request(
        method="POST",
        url=url,
        api_key=api_key,
        payload=payload,
    )

    # ----------------------------
    # Normalización respuesta
    # ----------------------------
    # Facturapi típicamente responde:
    # {
    #   id, uuid, status,
    #   pdf_url, xml_url,
    #   ...
    # }

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
