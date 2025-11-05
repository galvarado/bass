from django.shortcuts import render

from django.http import JsonResponse
from django.utils import timezone
from common.models import ExchangeRate
from datetime import date
from django.conf import settings   
import requests

from django.db.models.functions import Trim

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Value
from django.db.models.functions import Coalesce

from django_postalcodes_mexico.models import PostalCode as PC  # type: ignore

SEPOMEX_STATES = {
    "01":"Aguascalientes","02":"Baja California","03":"Baja California Sur","04":"Campeche",
    "05":"Coahuila de Zaragoza","06":"Colima","07":"Chiapas","08":"Chihuahua","09":"Ciudad de México",
    "10":"Durango","11":"Guanajuato","12":"Guerrero","13":"Hidalgo","14":"Jalisco","15":"México",
    "16":"Michoacán de Ocampo","17":"Morelos","18":"Nayarit","19":"Nuevo León","20":"Oaxaca",
    "21":"Puebla","22":"Querétaro","23":"Quintana Roo","24":"San Luis Potosí","25":"Sinaloa",
    "26":"Sonora","27":"Tabasco","28":"Tamaulipas","29":"Tlaxcala","30":"Veracruz de Ignacio de la Llave",
    "31":"Yucatán","32":"Zacatecas",
}

@require_GET
def lookup_cp(request):
    cp = (request.GET.get("cp") or "").strip()
    if not cp.isdigit() or len(cp) != 5:
        return JsonResponse({"ok": False, "error": "CP inválido."}, status=400)

    qs = PC.objects.filter(d_codigo=cp)
    if not qs.exists():
        return JsonResponse({"ok": True, "found": False})

    estado_code = (qs.values_list("c_estado", flat=True).first() or "").zfill(2)
    estado_name = SEPOMEX_STATES.get(estado_code, "")

    municipio = (
        qs.annotate(_mun=Trim("D_mnpio"))
          .exclude(_mun__isnull=True).exclude(_mun="")
          .values_list("_mun", flat=True).order_by("_mun").first()
        or ""
    )
    ciudad = (
        qs.annotate(_ciu=Trim("d_ciudad"))
          .exclude(_ciu__isnull=True).exclude(_ciu="")
          .values_list("_ciu", flat=True).order_by("_ciu").first()
        or ""
    )
    if not municipio and ciudad:
        municipio = ciudad  # fallback si SEPOMEX trae d_mnpio vacío

    colonias = list(
        qs.annotate(_col=Trim("d_asenta"))
          .exclude(_col__isnull=True).exclude(_col="")
          .values_list("_col", flat=True)
          .distinct().order_by("_col")
    )

    return JsonResponse({
        "ok": True, "found": True,
        "estado": estado_name, "estado_code": estado_code,
        "municipio": municipio, "ciudad": ciudad,
        "colonias": colonias,
    })


def header_info(request):
    """
    Devuelve el tipo de cambio USD→MXN del día.
    Si no existe, consulta OpenExchangeRates y lo guarda.
    """
    provider = "openexchangerates.org"
    today = date.today()
    rate_obj = ExchangeRate.objects.filter(date=today).first()

    # Si ya hay un registro de hoy, devolvemos ese valor
    if rate_obj:
        return JsonResponse({
            "now": timezone.now().isoformat(),
            "usd_mxn": rate_obj.usd_mxn,
            "provider": rate_obj.provider,
        })

    # Si no existe, consultamos la API y guardamos
    rate = None
    try:
        app_id = getattr(settings, "OPENEXCHANGE_APP_ID", None)
        if not app_id:
            raise ValueError("OPENEXCHANGE_APP_ID not configured")

        url = getattr(settings, "OPENEXCHANGE_BASE_URL", "https://openexchangerates.org/api/latest.json")
        r = requests.get(url, params={"app_id": app_id, "symbols": "MXN"}, timeout=8)
        r.raise_for_status()

        data = r.json()
        rate = data.get("rates", {}).get("MXN")

        if rate:
            rate_obj = ExchangeRate.objects.create(
                date=today,
                usd_mxn=rate,
                provider=provider,
            )
    except Exception as e:
        # fallback: si no hay API y no hay valor previo, rate queda None
        provider = f"{provider} (error: {e})"

    return JsonResponse({
        "now": timezone.now().isoformat(),
        "usd_mxn": rate,
        "provider": provider,
    })