# trips/facturapi_payloads.py
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from customers.models import Client
from operators.models import Operator, CrossBorderCapability
from trips.models import CartaPorteCFDI, CartaPorteLocation, CartaPorteGoods, CartaPorteItem


# ============================================================
# Helpers
# ============================================================
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

def _mx_rfc_or_generic(rfc: Optional[str]) -> str:
    """
    RFC genérico SAT:
    - Público en general: XAXX010101000
    - Extranjero:        XEXX010101000
    """
    r = _s(rfc).upper()
    return r if r else "XAXX010101000"

def _client_country_code(client: Client) -> str:
    # Client.pais: 'MX'/'US'
    c = _s(getattr(client, "pais", "MX")).upper()
    return c if c in ("MX", "US") else "MX"

def _operator_country_code(op: Operator) -> str:
    # Operator.pais es texto (default 'México')
    p = _s(getattr(op, "pais", "")).upper()
    if p in ("MX", "MEXICO", "MÉXICO"):
        return "MX"
    if p in ("US", "USA", "UNITED STATES", "ESTADOS UNIDOS"):
        return "US"
    return "MX"

def _safe_zip(cp: Optional[str]) -> str:
    return _s(cp)[:10]

def _cp_pais_to_2(code: Optional[str]) -> str:
    """
    CartaPorteLocation.pais en tu modelo es CharField max_length=3 default="MEX"
    pero tú en view a veces asignas "MX". Normalizamos a 2 letras.
    """
    c = _s(code).upper()
    if c == "MEX":
        return "MX"
    if c.startswith("MX"):
        return "MX"
    if c.startswith("US"):
        return "US"
    return c[:2] or "MX"

def _strip_nones(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
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


# ============================================================
# Receptor (Customer) - ALINEADO A customers.Client
# ============================================================
def build_customer_payload(client: Client) -> Dict[str, Any]:
    """
    customers.Client real:
    - razon_social, nombre
    - rfc, regimen_fiscal, uso_cfdi
    - id_tributario (VAT/Tax ID extranjero)
    - calle, no_ext, colonia_sat/colonia, municipio, estado, pais ('MX'/'US'), cp
    """
    country = _client_country_code(client)

    legal_name = _s(client.razon_social) or _s(client.nombre)
    display_name = _s(client.nombre) or legal_name

    if country == "MX":
        tax_id = _mx_rfc_or_generic(client.rfc)
        foreign_tax_id = None
    else:
        tax_id = "XEXX010101000"
        foreign_tax_id = _s(client.id_tributario) or None

    payload: Dict[str, Any] = {
        "legal_name": legal_name,
        "name": display_name,
        "tax_id": tax_id,
        "address": {
            "street": _s(client.calle),
            "external_number": _s(client.no_ext),
            "neighborhood": _s(client.colonia_sat) or _s(client.colonia),
            "city": _s(client.municipio) or _s(client.poblacion),
            "state": _s(client.estado),
            "country": country,
            "zip": _safe_zip(client.cp),
        },
    }

    # Regimen fiscal (Facturapi suele llamarlo tax_system)
    if country == "MX" and _s(client.regimen_fiscal):
        payload["tax_system"] = _s(client.regimen_fiscal)

    # TaxId extranjero (si Facturapi lo soporta para tu cuenta)
    if foreign_tax_id:
        payload["foreign_tax_id"] = foreign_tax_id

    return _strip_nones(payload)


# ============================================================
# FiguraTransporte - Operador - ALINEADO A operators.Operator
# ============================================================
def build_figura_transporte_operator_payload(op: Operator) -> Dict[str, Any]:
    """
    operators.Operator real:
    - nombre
    - rfc, curp
    - licencia_federal
    - dirección: calle, no_ext, colonia_sat/colonia, municipio, estado, cp, pais(texto)
    - cross_border (capability)
    """
    country = _operator_country_code(op)

    payload: Dict[str, Any] = {
        "name": _s(op.nombre),
        "tax_id": _mx_rfc_or_generic(op.rfc) if country == "MX" else "XEXX010101000",
        "curp": _s(op.curp) or None,
        "driver_license": _s(op.licencia_federal) or None,
        "address": {
            "street": _s(op.calle),
            "external_number": _s(op.no_ext),
            "neighborhood": _s(op.colonia_sat) or _s(op.colonia),
            "city": _s(op.municipio) or _s(op.poblacion),
            "state": _s(op.estado),
            "country": country,
            "zip": _safe_zip(op.cp),
        },
        "cross_border": op.cross_border in (CrossBorderCapability.PUEDE, CrossBorderCapability.SOLO_CRUCE),
    }
    return _strip_nones(payload)


# ============================================================
# Carta Porte - Ubicaciones (Origen/Destino) desde CartaPorteLocation
# ============================================================
def build_ubicaciones_payload(carta: CartaPorteCFDI) -> List[Dict[str, Any]]:
    """
    trips.CartaPorteLocation real:
    - tipo_ubicacion: Origen/Destino/Escala
    - rfc, nombre, num_reg_id_trib, residencia_fiscal
    - calle, numero_exterior, colonia, localidad, referencia, municipio, estado, pais, codigo_postal
    - distancia_recorrida_km, orden
    """
    locs = list(carta.locations.order_by("orden", "id").all())
    out: List[Dict[str, Any]] = []

    for l in locs:
        out.append(_strip_nones({
            "TipoUbicacion": _s(l.tipo_ubicacion),
            "RFCRemitenteDestinatario": _mx_rfc_or_generic(l.rfc),
            "NombreRemitenteDestinatario": _s(l.nombre) or None,
            "NumRegIdTrib": _s(l.num_reg_id_trib) or None,
            "ResidenciaFiscal": _s(l.residencia_fiscal) or None,

            "Domicilio": {
                "Calle": _s(l.calle) or None,
                "NumeroExterior": _s(l.numero_exterior) or None,
                "NumeroInterior": _s(l.numero_interior) or None,
                "Colonia": _s(l.colonia) or None,
                "Localidad": _s(l.localidad) or None,
                "Referencia": _s(l.referencia) or None,
                "Municipio": _s(l.municipio) or None,
                "Estado": _s(l.estado) or None,          # tú lo guardas como 3 letras (SAT)
                "Pais": _cp_pais_to_2(l.pais),           # normaliza MEX/MX
                "CodigoPostal": _s(l.codigo_postal),
            },

            # opcional
            "DistanciaRecorrida": float(_q2(_d(l.distancia_recorrida_km))) if l.distancia_recorrida_km is not None else None,
        }))

    return out


# ============================================================
# Carta Porte - Mercancías (ALINEADO a mercancias.Mercancia)
# ============================================================
def build_mercancias_payload(carta: CartaPorteCFDI) -> Dict[str, Any]:
    """
    trips.CartaPorteGoods real:
    - mercancia -> mercancias.Mercancia (clave, nombre, fraccion_arancelaria, comercio_exterior_uuid, valor_mercancia, moneda, pedimento)
    - cantidad, unidad, embalaje, peso_en_kg, valor_mercancia, moneda, pedimento
    """
    goods = list(carta.goods.select_related("mercancia").all())

    mercancia_rows: List[Dict[str, Any]] = []
    peso_total = Decimal("0.00")

    for g in goods:
        m = getattr(g, "mercancia", None)
        if not m:
            continue

        bienes_transp = _clean(m.clave)
        if not bienes_transp:
            continue

        desc = _clean(m.nombre) or "Mercancía"

        cantidad = _d(g.cantidad, "0")
        unidad = _clean(g.unidad) or "H87"

        if g.peso_en_kg is not None:
            peso = _d(g.peso_en_kg, "0")
            peso_total += peso
        else:
            peso = None

        # Valor/Moneda: prioridad partida -> catálogo -> header
        val = g.valor_mercancia if g.valor_mercancia is not None else m.valor_mercancia
        mon = _clean(g.moneda) or _clean(m.moneda) or _clean(getattr(carta, "currency", "")) or "MXN"

        row: Dict[str, Any] = {
            "BienesTransp": bienes_transp,
            "Descripcion": desc[:500],
            "Cantidad": float(_q3(cantidad)),
            "ClaveUnidad": unidad,
            "Unidad": unidad,
        }

        if peso is not None:
            row["PesoEnKg"] = float(_q3(peso))

        if val is not None:
            row["ValorMercancia"] = float(_q2(_d(val)))
        if mon:
            row["Moneda"] = mon.upper()

        emb = _clean(g.embalaje)
        if emb:
            row["Embalaje"] = emb

        # Comercio exterior
        frac = _clean(m.fraccion_arancelaria)
        if frac:
            row["FraccionArancelaria"] = frac

        uuidce = getattr(m, "comercio_exterior_uuid", None)
        if uuidce:
            row["UUIDComercioExterior"] = str(uuidce)

        # Pedimento: partida -> catálogo -> header
        ped = _clean(g.pedimento) or _clean(m.pedimento) or _clean(getattr(carta, "pedimento", ""))
        if ped:
            row["DocumentacionAduanera"] = [{
                "TipoDocumento": "01",      # Pedimento
                "NumPedimento": ped,
            }]

        mercancia_rows.append(_strip_nones(row))

    return _strip_nones({
        "NumTotalMercancias": len(mercancia_rows),
        "PesoBrutoTotal": float(_q2(peso_total)),
        "UnidadPeso": "KGM",
        "Mercancia": mercancia_rows,
    })


# ============================================================
# Conceptos (Items) - tú fuerzas 1 concepto en tu view/modelo
# ============================================================
def build_items_payload(carta: CartaPorteCFDI) -> List[Dict[str, Any]]:
    """
    trips.CartaPorteItem real:
    - cantidad, unidad, producto, descripcion
    - precio, descuento
    - iva_pct, ret_iva_pct
    - subtotal, iva_monto, ret_iva_monto, importe (calculados)
    """
    items = list(carta.items.order_by("orden", "id").all())
    out: List[Dict[str, Any]] = []

    for it in items:
        qty = _d(it.cantidad, "0")
        price = _d(it.precio, "0")
        disc = _d(it.descuento, "0")

        iva_pct = _d(it.iva_pct, "0")
        ret_pct = _d(it.ret_iva_pct, "0")

        row: Dict[str, Any] = {
            "quantity": float(_q3(qty)),
            "unit": _clean(it.unidad) or "E48",
            "product": _clean(it.producto) or "FLETE",
            "description": (_clean(it.descripcion) or "Servicio de transporte")[:255],
            "unit_price": float(_q2(price)),
            "discount": float(_q2(disc)),
            # si tu integración manda taxes por porcentaje:
            "taxes": _strip_nones({
                "iva_pct": float(_q2(iva_pct)),
                "ret_iva_pct": float(_q2(ret_pct)),
            }),
        }
        out.append(_strip_nones(row))

    return out


# ============================================================
# Payload CFDI completo (Facturapi)
# ============================================================
def build_cfdi_payload(*, carta: CartaPorteCFDI, trip_operator: Operator) -> Dict[str, Any]:
    """
    Arma el payload de Facturapi (estructura genérica):
    - customer: receptor (Client)
    - payment_method/payment_form/currency/use: desde CartaPorteCFDI
    - items: desde CartaPorteItem(s)
    - complements.carta_porte: ubicaciones, mercancias, figuras
    """
    if not carta.customer_id:
        raise ValueError("CartaPorteCFDI.customer es requerido para generar CFDI (receptor).")

    receptor = build_customer_payload(carta.customer)
    figura_op = build_figura_transporte_operator_payload(trip_operator)

    payload: Dict[str, Any] = {
        "customer": receptor,

        "payment_method": _s(getattr(carta, "payment_method", "")) or "PUE",
        "payment_form": _s(getattr(carta, "payment_form", "")) or "99",
        "currency": _s(getattr(carta, "currency", "")) or "MXN",
        "use": _s(getattr(carta, "uso_cfdi", "")) or "S01",

        # En tu modelo CartaPorteCFDI.type = "I"/"T"
        "type": _s(getattr(carta, "type", "")) or "T",

        # Conceptos
        "items": build_items_payload(carta),

        # Complemento Carta Porte (estructura conceptual)
        "complements": {
            "carta_porte": {
                "ubicaciones": build_ubicaciones_payload(carta),
                "mercancias": build_mercancias_payload(carta),
                "figures": {
                    "operators": [figura_op],
                },
                # puedes agregar aquí otros nodos si los manejas (autotransporte, seguros, remolques, etc.)
            }
        },
    }

    return _strip_nones(payload)
