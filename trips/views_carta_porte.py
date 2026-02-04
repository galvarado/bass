
# trips/views_carta_porte.py
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from .models import Trip, CartaPorteCFDI, CartaPorteLocation
from .forms import (
    CartaPorteCFDIForm,
    get_carta_porte_location_formset,
    get_carta_porte_goods_formset,
)
from decimal import Decimal


class CartaPorteEditView(TemplateView):
    template_name = "trips/carta_porte_form.html"

    def get_trip(self):
        return get_object_or_404(Trip, pk=self.kwargs["trip_id"], deleted=False)

    def get_carta(self, trip: Trip):
        carta, _ = CartaPorteCFDI.objects.get_or_create(trip=trip)
        return carta

    def get_success_url(self, trip: Trip):
        return reverse("trips:detail", kwargs={"pk": trip.id})

    def ensure_subtotal_from_trip(self, trip: Trip, carta: CartaPorteCFDI):
        """
        Subtotal = snapshot del viaje (preferido).
        Fallback = tarifa de la ruta.
        Solo setea si no existe o está en 0.00
        """
        current = getattr(carta, "subtotal", None)

        if current is not None and current != Decimal("0.00"):
            return

        subtotal = Decimal("0.00")

        # preferido: snapshot del trip
        if getattr(trip, "tarifa_cliente_snapshot", None):
          subtotal = trip.tarifa_cliente_snapshot or Decimal("0.00")

        # fallback: route.tarifa_cliente
        if subtotal == Decimal("0.00") and trip.route:
          subtotal = getattr(trip.route, "tarifa_cliente", None) or Decimal("0.00")

        carta.subtotal = subtotal
        carta.save(update_fields=["subtotal"])

    def build_forms(self, *, request, carta: CartaPorteCFDI, trip: Trip, bound: bool):
        LocationFS = get_carta_porte_location_formset()
        GoodsFS = get_carta_porte_goods_formset()

        if bound:
            form = CartaPorteCFDIForm(request.POST, instance=carta)
            fs_locations = LocationFS(request.POST, instance=carta, prefix="loc")
            fs_goods = GoodsFS(request.POST, instance=carta, prefix="goods")
            return form, fs_locations, fs_goods

        # GET
        initial = {}

        # customer default
        try:
            if trip.route and trip.route.origen and trip.route.origen.client_id:
                if not getattr(carta, "customer_id", None):
                    initial["customer"] = trip.route.origen.client_id
        except Exception:
            pass

        # subtotal default (tarifa_cliente)
        try:
            current = getattr(carta, "subtotal", None)
            is_empty = (current is None) or (Decimal(str(current)) == Decimal("0.00"))
            if is_empty and trip.route_id:
                initial["subtotal"] = trip.route.tarifa_cliente or Decimal("0.00")
        except Exception:
            pass

        form = CartaPorteCFDIForm(instance=carta, initial=initial)
        fs_locations = LocationFS(instance=carta, prefix="loc")
        fs_goods = GoodsFS(instance=carta, prefix="goods")

        return form, fs_locations, fs_goods

    def ensure_locations_from_route(self, trip: Trip, carta: CartaPorteCFDI):
        r = trip.route
        if not r:
            return

        # deja solo Origen/Destino
        carta.locations.exclude(tipo_ubicacion__in=["Origen", "Destino"]).delete()

        def client_rfc(loc_model):
            return getattr(getattr(loc_model, "client", None), "rfc", "") or ""

        def build(loc_model, tipo, orden, dt):
            return CartaPorteLocation(
                carta_porte=carta,
                tipo_ubicacion=tipo,
                orden=orden,
                rfc=client_rfc(loc_model),
                nombre=getattr(loc_model, "nombre", "") or "",
                localidad=getattr(loc_model, "poblacion", "") or "",
                codigo_postal=getattr(loc_model, "cp", "") or "",
                calle=getattr(loc_model, "calle", "") or "",
                numero_exterior=getattr(loc_model, "no_ext", "") or "",
                numero_interior="",
                colonia=getattr(loc_model, "colonia_sat", "") or getattr(loc_model, "colonia", "") or "",
                municipio=getattr(loc_model, "municipio", "") or "",
                estado=getattr(loc_model, "estado", "") or "",
                pais=getattr(loc_model, "pais", "") or "MX",
                referencia=getattr(loc_model, "referencias", "") or "",
                fecha_hora_salida_llegada=dt,
            )

        dt_origen = getattr(trip, "departure_origin_at", None) or timezone.now()
        dt_destino = getattr(trip, "arrival_destination_at", None) or timezone.now()

        # ORIGEN
        o = carta.locations.filter(tipo_ubicacion="Origen").first()
        if not o:
            o = build(r.origen, "Origen", 0, dt_origen)
            o.save()
        else:
            o.orden = 0
            o.nombre = o.nombre or (r.origen.nombre or "")
            o.localidad = o.localidad or (r.origen.poblacion or "")
            o.codigo_postal = o.codigo_postal or (r.origen.cp or "")
            o.rfc = o.rfc or client_rfc(r.origen)

            o.calle = o.calle or (r.origen.calle or "")
            o.numero_exterior = o.numero_exterior or (r.origen.no_ext or "")
            o.colonia = o.colonia or (r.origen.colonia_sat or r.origen.colonia or "")
            o.municipio = o.municipio or (r.origen.municipio or "")
            o.estado = o.estado or (r.origen.estado or "")
            o.pais = o.pais or (r.origen.pais or "MX")
            o.referencia = o.referencia or (r.origen.referencias or "")

            if not o.fecha_hora_salida_llegada:
                o.fecha_hora_salida_llegada = dt_origen
            o.save()

        # DESTINO
        d = carta.locations.filter(tipo_ubicacion="Destino").first()
        if not d:
            d = build(r.destino, "Destino", 99, dt_destino)
            d.save()
        else:
            d.orden = 99
            d.nombre = d.nombre or (r.destino.nombre or "")
            d.localidad = d.localidad or (r.destino.poblacion or "")
            d.codigo_postal = d.codigo_postal or (r.destino.cp or "")
            d.rfc = d.rfc or client_rfc(r.destino)

            d.calle = d.calle or (r.destino.calle or "")
            d.numero_exterior = d.numero_exterior or (r.destino.no_ext or "")
            d.colonia = d.colonia or (r.destino.colonia_sat or r.destino.colonia or "")
            d.municipio = d.municipio or (r.destino.municipio or "")
            d.estado = d.estado or (r.destino.estado or "")
            d.pais = d.pais or (r.destino.pais or "MX")
            d.referencia = d.referencia or (r.destino.referencias or "")

            if not d.fecha_hora_salida_llegada:
                d.fecha_hora_salida_llegada = dt_destino
            d.save()

        # asegura exactamente 2 registros
        carta.locations.exclude(id__in=[o.id, d.id]).delete()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        trip = self.get_trip()
        carta = self.get_carta(trip)

        # ✅ autogenera Origen/Destino al entrar
        self.ensure_locations_from_route(trip, carta)

        # ✅ subtotal desde ruta/viaje
        self.ensure_subtotal_from_trip(trip, carta)

        form, fs_locations, fs_goods = self.build_forms(
            request=self.request, carta=carta, trip=trip, bound=False
        )

        ctx.update({
            "trip": trip,
            "carta": carta,
            "form": form,
            "fs_locations": fs_locations,
            "fs_goods": fs_goods,
        })
        return ctx

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        trip = self.get_trip()
        carta = self.get_carta(trip)

        form, fs_locations, fs_goods = self.build_forms(
            request=request, carta=carta, trip=trip, bound=True
        )

        if not (form.is_valid() and fs_locations.is_valid() and fs_goods.is_valid()):
            messages.error(request, "Revisa los errores del formulario.")
            return self.render_to_response({
                "trip": trip,
                "carta": carta,
                "form": form,
                "fs_locations": fs_locations,
                "fs_goods": fs_goods,
            })

        carta = form.save(commit=False)
        carta.customer = form.cleaned_data.get("customer")  # no readonly
        carta.save()

        fs_locations.save()
        fs_goods.save()

        # asegurar que no se cuelen más de 2 ubicaciones
        self.ensure_locations_from_route(trip, carta)

        messages.success(request, "Carta Porte guardada.")
        return redirect(self.get_success_url(trip))
