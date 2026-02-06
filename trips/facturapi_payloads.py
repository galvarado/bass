# trips/facturapi_payloads.py
from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from django.utils import timezone
from customers.models import Client
from operators.models import Operator, CrossBorderCapability
from trips.models import CartaPorteCFDI

# ============================================================
# Regex/Validaciones
# ============================================================

RFC_RE = re.compile(r"^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$")
TAX_SYSTEM_RE = re.compile(r"^\d{3}$")  # "601", "612", etc.


# ============================================================
# Helpers
# ============================================================

def _iso_dt(v: Any) -> str:
    """
    Facturapi espera 'YYYY-MM-DDTHH:MM:SS' (sin timezone explícito).
    Acepta datetime/date/string. Si viene aware, lo convierte a local y lo vuelve naive.
    """
    if v is None:
        dt = timezone.localtime(timezone.now())
    elif isinstance(v, datetime):
        dt = v
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
    else:
        # string u otro: intenta parsear ISO (Django suele guardar datetime)
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            if timezone.is_aware(dt):
                dt = timezone.localtime(dt)
        except Exception:
            dt = timezone.localtime(timezone.now())

    # dejarlo naive para el string final
    if timezone.is_aware(dt):
        dt = timezone.make_naive(dt, timezone.get_current_timezone())

    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _loc_fecha_hora(carta: CartaPorteCFDI, loc: Any) -> str:
    """
    Origen -> carta.fecha_salida
    Destino -> carta.fecha_llegada
    Otros -> loc.fecha_hora_salida_llegada si existe, si no carta.fecha_salida
    """
    tipo = _s(getattr(loc, "tipo_ubicacion", "")).lower()

    # intenta usar campo propio del location si lo tuvieras
    loc_dt = getattr(loc, "fecha_hora_salida_llegada", None) or getattr(loc, "fecha_hora", None)

    if "origen" in tipo:
        base = getattr(carta, "fecha_salida", None) or loc_dt
    elif "destino" in tipo:
        base = getattr(carta, "fecha_llegada", None) or loc_dt
    else:
        base = loc_dt or getattr(carta, "fecha_salida", None)

    return _iso_dt(base)

def _country_2_to_3(code: str) -> str:
    """Facturapi espera ISO-3166 alpha-3 (ej: MEX, USA)."""
    c = (code or "").strip().upper()
    if c in ("MX", "MEX"):
        return "MEX"
    if c in ("US", "USA"):
        return "USA"
    return (c[:3] or "MEX")


def _s(v: Optional[str]) -> str:
    return (v or "").strip()


def _clean(v: Optional[str]) -> str:
    return _s(v)


def _d(v: Any, default: str = "0") -> Decimal:
    try:
        if v is None:
            return Decimal(default)
        return Decimal(str(v))
    except Exception:
        return Decimal(default)


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def _q3(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.001"))


def _safe_zip(cp: Optional[str]) -> str:
    return _s(cp)[:20]


def _client_country_code(client: Client) -> str:
    c = _s(getattr(client, "pais", "MX")).upper()
    return c if c in ("MX", "US") else "MX"


def _operator_country_code(op: Operator) -> str:
    p = _s(getattr(op, "pais", "")).upper()
    if p in ("MX", "MEXICO", "MÉXICO"):
        return "MX"
    if p in ("US", "USA", "UNITED STATES", "ESTADOS UNIDOS"):
        return "US"
    return "MX"


def _strip_nones(d: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            vv = _strip_nones(v)
            if vv:
                out[k] = vv
            continue
        if isinstance(v, list):
            vv = []
            for it in v:
                if it is None:
                    continue
                if isinstance(it, dict):
                    itd = _strip_nones(it)
                    if itd:
                        vv.append(itd)
                else:
                    vv.append(it)
            if vv:
                out[k] = vv
            continue
        out[k] = v
    return out


def _is_valid_rfc_with_real_date(rfc: str) -> bool:
    r = _s(rfc).upper().replace(" ", "").replace("-", "").replace(".", "")
    if not RFC_RE.match(r):
        return False

    idx = 4 if len(r) == 13 else 3
    yymmdd = r[idx: idx + 6]

    try:
        yy = int(yymmdd[0:2])
        mm = int(yymmdd[2:4])
        dd = int(yymmdd[4:6])
    except Exception:
        return False

    today = date.today()
    cutoff = today.year % 100
    year = 2000 + yy if yy <= cutoff else 1900 + yy

    try:
        _ = date(year, mm, dd)
    except ValueError:
        return False

    return True


def _normalize_rfc_or_generic(rfc: Optional[str], *, country2: str) -> str:
    """
    - MX: RFC real si es válido; si no -> XAXX010101000
    - Extranjero: XEXX010101000
    """
    c2 = (country2 or "MX").upper()
    if c2 != "MX":
        return "XEXX010101000"

    r = _s(rfc).upper().replace(" ", "").replace("-", "").replace(".", "")
    if not r:
        return "XAXX010101000"
    if _is_valid_rfc_with_real_date(r):
        return r
    return "XAXX010101000"


def _tax_system_or_default(value: Optional[str], *, default: str = "601") -> str:
    v = _s(value)
    if TAX_SYSTEM_RE.match(v):
        return v
    return default


def generate_idccp() -> str:
    """
    IdCCP (SAT/SW): UUID RFC4122, sustituir primeros 3 caracteres por 'CCC'
    """
    u = str(uuid.uuid4())
    return "CCC" + u[3:]


def _is_international_shipment(carta: CartaPorteCFDI) -> bool:
    """
    Heurística:
    - Si currency == USD -> internacional
    - Si alguna ubicación tiene país != MEX -> internacional
    """
    cur = _s(getattr(carta, "currency", "")).upper()
    if cur == "USD":
        return True

    try:
        locs = list(carta.locations.all())
    except Exception:
        locs = []

    for l in locs:
        lp = _country_2_to_3(_s(getattr(l, "pais", "")))
        if lp and lp != "MEX":
            return True
    return False


def _pais_origen_destino(carta: CartaPorteCFDI) -> str:
    """
    Mínimo requerido cuando TranspInternac='Sí':
    - usa el país del cliente si lo tienes, si no MEX
    """
    client = getattr(carta, "customer", None)
    if client:
        return _country_2_to_3(_client_country_code(client))
    return "MEX"


# ============================================================
# Facturapi: Customer.address
# ============================================================

def facturapi_customer_address_from_client(client: Client) -> Dict[str, Any]:
    country2 = _client_country_code(client)
    country3 = _country_2_to_3(country2)

    addr = {
        "country": country3,
        "zip": _safe_zip(getattr(client, "cp", None)),
        "street": _s(getattr(client, "calle", None)) or None,
        "exterior": _s(getattr(client, "no_ext", None)) or None,
        "interior": _s(getattr(client, "no_int", None)) or None,
        "neighborhood": _s(getattr(client, "colonia_sat", None)) or _s(getattr(client, "colonia", None)) or None,
        "city": _s(getattr(client, "poblacion", None)) or _s(getattr(client, "ciudad", None)) or None,
        "municipality": _s(getattr(client, "municipio", None)) or None,
        "state": _s(getattr(client, "estado", None)) or None,
    }

    return {k: v for k, v in addr.items() if v not in (None, "", [])}


# ============================================================
# Receptor (Customer)
# ============================================================

def build_customer_payload(client: Client) -> Dict[str, Any]:
    country2 = _client_country_code(client)

    legal_name = _s(getattr(client, "razon_social", None)) or _s(getattr(client, "nombre", None))
    tax_id = _normalize_rfc_or_generic(getattr(client, "rfc", None), country2=country2)

    raw_tax_system = getattr(client, "regimen_fiscal", None)
    tax_system = _tax_system_or_default(raw_tax_system, default="601")

    print(
        f"[FACTURAPI][RFC][CUSTOMER] "
        f"client_id={getattr(client, 'id', None)} "
        f"raw_rfc={getattr(client, 'rfc', None)!r} "
        f"normalized_tax_id={tax_id}"
    )
    print(
        f"[FACTURAPI][TAX_SYSTEM][CUSTOMER] "
        f"client_id={getattr(client, 'id', None)} "
        f"raw_tax_system={raw_tax_system!r} "
        f"normalized_tax_system={tax_system}"
    )

    payload: Dict[str, Any] = {
        "legal_name": legal_name,
        "tax_id": tax_id,
        "tax_system": tax_system,  # ✅ requerido
        "address": facturapi_customer_address_from_client(client),
    }

    if country2 != "MX":
        foreign_tax_id = _s(getattr(client, "id_tributario", None)) or None
        if foreign_tax_id:
            payload["foreign_tax_id"] = foreign_tax_id

    return _strip_nones(payload)


# ============================================================
# Items (Facturapi)
# ============================================================

def build_items_payload(carta: CartaPorteCFDI) -> List[Dict[str, Any]]:
    items = list(carta.items.order_by("orden", "id").all())
    out: List[Dict[str, Any]] = []

    for it in items:
        qty = _d(getattr(it, "cantidad", None), "0")
        price = _d(getattr(it, "precio", None), "0")
        desc = (_clean(getattr(it, "descripcion", None)) or "Servicio de transporte")[:255]

        product_key = "78101800"
        unit_key = _clean(getattr(it, "unidad", None)) or "E48"

        taxes: List[Dict[str, Any]] = []
        iva_pct = _d(getattr(it, "iva_pct", None), "0")
        if iva_pct > 0:
            taxes.append({
                "type": "IVA",
                "rate": float((iva_pct / Decimal("100")).quantize(Decimal("0.0001"))),
            })

        out.append(_strip_nones({
            "quantity": float(_q3(qty)),
            "product": {
                "description": desc,
                "product_key": product_key,
                "unit_key": unit_key,
                "unit_name": unit_key,
                "price": float(_q2(price)),
                "taxes": taxes,
            },
        }))

    return out


# ============================================================
# Carta Porte - Ubicaciones
# ============================================================

def build_ubicaciones_payload(carta: CartaPorteCFDI) -> List[Dict[str, Any]]:
    locs = list(carta.locations.order_by("orden", "id").all())
    out: List[Dict[str, Any]] = []

    for l in locs:
        out.append(_strip_nones({
            "TipoUbicacion": _s(getattr(l, "tipo_ubicacion", None)),
            "RFCRemitenteDestinatario": _normalize_rfc_or_generic(getattr(l, "rfc", None), country2="MX"),
            "NombreRemitenteDestinatario": _s(getattr(l, "nombre", None)) or None,

            # ✅ requerido por Facturapi
            "FechaHoraSalidaLlegada": _loc_fecha_hora(carta, l),

            "Domicilio": {
                "Calle": _s(getattr(l, "calle", None)) or None,
                "NumeroExterior": _s(getattr(l, "numero_exterior", None)) or None,
                "NumeroInterior": _s(getattr(l, "numero_interior", None)) or None,
                "Colonia": _s(getattr(l, "colonia", None)) or None,
                "Localidad": _s(getattr(l, "localidad", None)) or None,
                "Municipio": _s(getattr(l, "municipio", None)) or None,
                "Estado": _s(getattr(l, "estado", None)) or None,
                "Pais": _country_2_to_3(_s(getattr(l, "pais", None))),  # MEX/USA
                "CodigoPostal": _s(getattr(l, "codigo_postal", None)),
            },

            "DistanciaRecorrida": float(_q2(_d(getattr(l, "distancia_recorrida_km", None))))
            if getattr(l, "distancia_recorrida_km", None) is not None else None,
        }))

    return out


# ============================================================
# Carta Porte - Mercancías
# ============================================================

def build_mercancias_payload(carta: CartaPorteCFDI) -> Dict[str, Any]:
    goods = list(carta.goods.select_related("mercancia").all())

    mercancia_rows: List[Dict[str, Any]] = []
    peso_total = Decimal("0.00")

    for g in goods:
        m = getattr(g, "mercancia", None)
        if not m:
            continue

        bienes_transp = _clean(getattr(m, "clave", None))
        if not bienes_transp:
            continue

        desc = _clean(getattr(m, "nombre", None)) or "Mercancía"
        cantidad = _d(getattr(g, "cantidad", None), "0")
        unidad = _clean(getattr(g, "unidad", None)) or "H87"

        peso_val = getattr(g, "peso_en_kg", None)
        if peso_val is not None:
            peso = _d(peso_val, "0")
            peso_total += peso
        else:
            peso = None

        mon = (
            _clean(getattr(g, "moneda", None))
            or _clean(getattr(m, "moneda", None))
            or _clean(getattr(carta, "currency", ""))
            or "MXN"
        )

        row: Dict[str, Any] = {
            "BienesTransp": bienes_transp,
            "Descripcion": desc[:500],
            "Cantidad": float(_q3(cantidad)),
            "ClaveUnidad": unidad,
            "Unidad": unidad,
        }

        if peso is not None:
            row["PesoEnKg"] = float(_q3(peso))
        if mon:
            row["Moneda"] = mon.upper()

        frac = _clean(getattr(m, "fraccion_arancelaria", None))
        if frac:
            row["FraccionArancelaria"] = frac

        # uuidce = getattr(m, "comercio_exterior_uuid", None)
        # if uuidce:
        #     row["UUIDComercioExterior"] = str(uuidce)

        ped = _clean(getattr(g, "pedimento", None)) or _clean(getattr(m, "pedimento", None)) or _clean(getattr(carta, "pedimento", ""))
        if ped:
            row["DocumentacionAduanera"] = [{"TipoDocumento": "01", "NumPedimento": ped}]

        mercancia_rows.append(_strip_nones(row))

    return _strip_nones({
        "NumTotalMercancias": len(mercancia_rows),
        "PesoBrutoTotal": float(_q2(peso_total)),
        "UnidadPeso": "KGM",
        "Mercancia": mercancia_rows,
    })


# ============================================================
# FiguraTransporte (Operador)
# ============================================================

def build_figura_transporte_payload(op: Operator) -> List[Dict[str, Any]]:
    country2 = _operator_country_code(op)
    country3 = _country_2_to_3(country2)

    rfc_figura = _normalize_rfc_or_generic(getattr(op, "rfc", None), country2="MX")

    print(
        f"[FACTURAPI][RFC][OPERATOR] "
        f"operator_id={getattr(op, 'id', None)} "
        f"raw_rfc={getattr(op, 'rfc', None)!r} "
        f"normalized_rfc={rfc_figura}"
    )

    return [_strip_nones({
        "TipoFigura": "01",
        "RFCFigura": rfc_figura,
        "NumLicencia": _s(getattr(op, "licencia_federal", None)) or None,
        "NombreFigura": _s(getattr(op, "nombre", None)) or None,
        "Domicilio": {
            "Calle": _s(getattr(op, "calle", None)) or None,
            "NumeroExterior": _s(getattr(op, "no_ext", None)) or None,
            "Colonia": _s(getattr(op, "colonia_sat", None)) or _s(getattr(op, "colonia", None)) or None,
            "Municipio": _s(getattr(op, "municipio", None)) or None,
            "Estado": _s(getattr(op, "estado", None)) or None,
            "Pais": country3,
            "CodigoPostal": _safe_zip(getattr(op, "cp", None)) or None,
        },
    })]


# ============================================================
# Payload CFDI completo (Facturapi)
# ============================================================

def build_cfdi_payload(*, carta: CartaPorteCFDI, trip_operator: Operator) -> Dict[str, Any]:
    if not carta.customer_id:
        raise ValueError("CartaPorteCFDI.customer es requerido para generar CFDI (receptor).")

    idccp = generate_idccp()
    transp_internac = "Sí" if _is_international_shipment(carta) else "No"

    # Defaults “mínimos” cuando es internacional
    pais_origen_destino = _pais_origen_destino(carta)  # MEX/USA
    entrada_salida = "Entrada"  # default; ajusta si quieres lógica
    via_entrada_salida = "04"   # "04" = Carretera (default razonable)

    print(f"[FACTURAPI][CARTA_PORTE][IdCCP] carta_id={getattr(carta,'id',None)} IdCCP={idccp}")
    print(f"[FACTURAPI][CARTA_PORTE][TranspInternac] carta_id={getattr(carta,'id',None)} TranspInternac={transp_internac}")

    carta_porte_data = {
        "IdCCP": idccp,
        "TranspInternac": transp_internac,
        "Ubicaciones": build_ubicaciones_payload(carta),
        "Mercancias": build_mercancias_payload(carta),
        "FiguraTransporte": build_figura_transporte_payload(trip_operator),
    }

    if transp_internac == "Sí":
        carta_porte_data.update({
            "EntradaSalidaMerc": entrada_salida,
            "PaisOrigenDestino": pais_origen_destino,
            "ViaEntradaSalida": via_entrada_salida,
        })

    payload: Dict[str, Any] = {
        "type": _s(getattr(carta, "type", "")) or "T",
        "customer": build_customer_payload(carta.customer),
        "payment_method": _s(getattr(carta, "payment_method", "")) or None,
        "payment_form": _s(getattr(carta, "payment_form", "")) or "99",
        "currency": _s(getattr(carta, "currency", "")) or "MXN",
        "use": _s(getattr(carta, "uso_cfdi", "")) or "S01",
        "items": build_items_payload(carta),
        "complements": [
            {
                "type": "carta_porte",
                "data": _strip_nones(carta_porte_data),
            }
        ],
    }

    return _strip_nones(payload)
