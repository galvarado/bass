from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional
import xml.etree.ElementTree as ET

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
    api_key = getattr(settings, "FACTURAPI_API_KEY", None)
    base_url = getattr(settings, "FACTURAPI_BASE_URL", "https://www.facturapi.io/v2")
    timeout = int(getattr(settings, "FACTURAPI_TIMEOUT_SECONDS", 30) or 30)

    if not api_key:
        raise FacturapiError("FACTURAPI_API_KEY no está configurado.")

    return api_key, base_url.rstrip("/"), timeout


# ======================================================
# HTTP helper (JSON)
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

    if "application/json" not in content_type:
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
        raise FacturapiError(
            f"Respuesta JSON inválida de Facturapi ({resp.status_code})."
        )

    if resp.status_code >= 400:
        msg = data.get("message") or data.get("error") or "Error desconocido en Facturapi"
        details = data.get("details")
        if details:
            msg = f"{msg}\n{json.dumps(details, indent=2, ensure_ascii=False)}"
        raise FacturapiError(msg)

    return data


# ======================================================
# Descargar XML (en memoria)
# ======================================================
def download_invoice_xml(*, invoice_id: str) -> bytes:
    """
    GET /invoices/{id}/xml
    Devuelve XML como bytes (NO se guarda en disco).
    """
    if not invoice_id:
        raise FacturapiError("invoice_id requerido para descargar XML.")

    api_key, base_url, timeout = _get_facturapi_config()
    url = f"{base_url}/invoices/{invoice_id}/xml"

    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/xml",
            },
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise FacturapiError(f"Error al descargar XML: {e}")

    if resp.status_code >= 400:
        body = (resp.text or "")[:800]
        logger.error("FACTURAPI XML ERROR %s %s %s", resp.status_code, url, body)
        raise FacturapiError(f"No se pudo descargar XML ({resp.status_code}).")

    return resp.content


# ======================================================
# Extraer datos del certificado desde XML
# ======================================================
def extract_cert_data_from_xml(xml_bytes: bytes) -> Dict[str, str]:
    """
    Extrae:
      - NoCertificado (emisor)
      - Certificado (base64 del .cer público)
    """
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        raise FacturapiError(f"No se pudo parsear XML CFDI: {e}")

    return {
        "emitter_no_cert": root.attrib.get("NoCertificado", "") or "",
        "emitter_cert_b64": root.attrib.get("Certificado", "") or "",
    }


# ======================================================
# Crear CFDI en Facturapi + enriquecer con NoCertificado
# ======================================================
def create_invoice_in_facturapi(*, carta: CartaPorteCFDI, trip: Trip) -> Dict[str, Any]:
    """
    - Construye payload
    - Envía a Facturapi
    - Descarga XML
    - Extrae NoCertificado del emisor
    - Devuelve payload + respuesta normalizada
    """

    # =============================
    # Validaciones
    # =============================
    if carta.status == "stamped" and carta.uuid:
        raise FacturapiError("Este CFDI ya fue timbrado.")

    if carta.status == "canceled":
        raise FacturapiError("Este CFDI está cancelado.")

    if not carta.customer_id:
        raise FacturapiError("La Carta Porte no tiene cliente.")

    if not trip.operator_id:
        raise FacturapiError("El viaje no tiene operador.")

    if carta.total <= 0:
        raise FacturapiError("El total del CFDI debe ser mayor a 0.")

    # =============================
    # Config
    # =============================
    api_key, base_url, timeout = _get_facturapi_config()

    payload = build_cfdi_payload(
        carta=carta,
        trip_operator=trip.operator,
    )

    url = f"{base_url}/invoices"

    # =============================
    # Timbrar
    # =============================
    response = _facturapi_request(
        method="POST",
        url=url,
        api_key=api_key,
        payload=payload,
        timeout=timeout,
    )

    # =============================
    # Normalizar
    # =============================
    normalized: Dict[str, Any] = {
        "id": response.get("id"),
        "uuid": response.get("uuid"),
        "status": response.get("status"),
        "pdf_url": response.get("pdf_url") or response.get("pdf"),
        "xml_url": response.get("xml_url") or response.get("xml"),
        "raw": response,
        "emitter_no_cert": "",
        "sat_no_cert": (response.get("stamp") or {}).get("sat_cert_number", "") or "",
    }

    # =============================
    # Descargar XML y extraer NoCertificado
    # =============================
    invoice_id = normalized.get("id")
    if invoice_id:
        try:
            xml_bytes = download_invoice_xml(invoice_id=invoice_id)
            cert_data = extract_cert_data_from_xml(xml_bytes)

            normalized["emitter_no_cert"] = cert_data.get("emitter_no_cert", "")

            # 🔒 No guardamos emitter_cert_b64 en DB por tamaño
            # Si algún día necesitas generar .cer:
            # base64.b64decode(cert_data["emitter_cert_b64"])

            # Liberar referencia
            del xml_bytes

        except Exception as e:
            logger.warning("No se pudo enriquecer con certificado del emisor: %s", e)

    return {
        "payload": payload,
        "response": normalized,
    }

def _get_facturapi_invoice_id_from_carta(carta: CartaPorteCFDI) -> Optional[str]:
    """
    Resuelve el invoice_id de Facturapi desde response_snapshot.
    """
    snap = carta.response_snapshot or {}
    if not isinstance(snap, dict):
        return None
    raw = (snap.get("raw") or {}) if isinstance(snap.get("raw"), dict) else {}
    return raw.get("id") or snap.get("id") or None


def download_carta_porte_xml(*, carta: CartaPorteCFDI) -> bytes:
    """
    Descarga XML usando el invoice_id guardado en response_snapshot.
    """
    invoice_id = _get_facturapi_invoice_id_from_carta(carta)
    if not invoice_id:
        raise FacturapiError(
            "No se encontró el ID de Facturapi en response_snapshot para descargar el XML."
        )
    return download_invoice_xml(invoice_id=invoice_id)
