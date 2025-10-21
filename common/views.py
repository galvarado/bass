from django.shortcuts import render

from django.http import JsonResponse
from django.utils import timezone
from common.models import ExchangeRate
from datetime import date
from django.conf import settings   
import requests


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