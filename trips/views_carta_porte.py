# trips/views_carta_porte.py
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView
from django.utils import timezone

from .models import Trip, CartaPorteCFDI, CartaPorteLocation
from .forms import (
    CartaPorteCFDIForm,
    CartaPorteLocationFormSet,
    CartaPorteGoodsFormSet,
)


class CartaPorteEditView(TemplateView):
    template_name = "trips/carta_porte_form.html"

    def get_trip(self):
        return get_object_or_404(Trip, pk=self.kwargs["trip_id"], deleted=False)

    def get_carta(self, trip: Trip):
        carta, _ = CartaPorteCFDI.objects.get_or_create(trip=trip)
        return carta

    def get_success_url(self, trip: Trip):
        return reverse("trips:detail", kwargs={"pk": trip.id})

    def build_forms(self, *, request, carta: CartaPorteCFDI, trip: Trip, bound: bool):
        """
        customer por default = cliente del origen (pero NO readonly).
        """
        if bound:
            form = CartaPorteCFDIForm(request.POST, instance=carta)
            fs_locations = CartaPorteLocationFormSet(request.POST, instance=carta, prefix="loc")
            fs_goods = CartaPorteGoodsFormSet(request.POST, instance=carta, prefix="goods")
        else:
            form = CartaPorteCFDIForm(instance=carta)
            fs_locations = CartaPorteLocationFormSet(instance=carta, prefix="loc")
            fs_goods = CartaPorteGoodsFormSet(instance=carta, prefix="goods")

            # default sugerido: receptor = mismo cliente del ORIGEN
            try:
                if trip.route and trip.route.origen and trip.route.origen.client_id:
                    if not getattr(carta, "customer_id", None):
                        form.fields["customer"].initial = trip.route.origen.client_id
            except Exception:
                pass

        return form, fs_locations, fs_goods

    def ensure_locations_from_route(self, trip: Trip, carta: CartaPorteCFDI):
        """
        Deja EXACTAMENTE 2 ubicaciones: Origen y Destino.
        - nombre = Location.nombre
        - localidad = Location.poblacion
        - cliente viene por Location.client (pero no lo guardamos en CP; lo usas en UI)
        - fechas: si no existen, se sugieren con trip.* o timezone.now()
        """
        r = trip.route
        if not r:
            return

        # borra cualquier cosa que no sea Origen/Destino
        carta.locations.exclude(tipo_ubicacion__in=["Origen", "Destino"]).delete()

        def client_rfc(loc_model):
            return getattr(getattr(loc_model, "client", None), "rfc", "") or ""

        def build(loc_model, tipo, orden, dt):
            return CartaPorteLocation(
                carta_porte=carta,
                tipo_ubicacion=tipo,
                orden=orden,

                # ✅ ubicación = Location.nombre
                nombre=getattr(loc_model, "nombre", "") or "",

                # ✅ población = Location.poblacion
                localidad=getattr(loc_model, "poblacion", "") or "",

                # mínimos obligatorios de tu modelo
                rfc=client_rfc(loc_model),
                codigo_postal=getattr(loc_model, "cp", "") or "",

                pais="MEX",
                fecha_hora_salida_llegada=dt,
            )

        dt_origen = trip.departure_origin_at or timezone.now()
        dt_destino = trip.arrival_destination_at or timezone.now()

        # ----- ORIGEN -----
        o = carta.locations.filter(tipo_ubicacion="Origen").first()
        if not o:
            o = build(r.origen, "Origen", 0, dt_origen)
            o.save()
        else:
            o.orden = 0
            o.nombre = o.nombre or r.origen.nombre
            o.localidad = o.localidad or (r.origen.poblacion or "")
            o.codigo_postal = o.codigo_postal or (r.origen.cp or "")
            o.rfc = o.rfc or client_rfc(r.origen)
            if not o.fecha_hora_salida_llegada:
                o.fecha_hora_salida_llegada = dt_origen
            o.save()

        # ----- DESTINO -----
        d = carta.locations.filter(tipo_ubicacion="Destino").first()
        if not d:
            d = build(r.destino, "Destino", 99, dt_destino)
            d.save()
        else:
            d.orden = 99
            d.nombre = d.nombre or r.destino.nombre
            d.localidad = d.localidad or (r.destino.poblacion or "")
            d.codigo_postal = d.codigo_postal or (r.destino.cp or "")
            d.rfc = d.rfc or client_rfc(r.destino)
            if not d.fecha_hora_salida_llegada:
                d.fecha_hora_salida_llegada = dt_destino
            d.save()

        # seguridad: deja solo esos 2
        carta.locations.exclude(id__in=[o.id, d.id]).delete()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        trip = self.get_trip()
        carta = self.get_carta(trip)

        # ✅ autogenera Origen/Destino al entrar
        self.ensure_locations_from_route(trip, carta)

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

        # en POST no recreamos ubicaciones; solo validamos/guardamos
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

        # ✅ NO forzamos fechas desde trip (fechas editables)
        fs_locations.save()
        fs_goods.save()

        # (opcional) asegurar que no se cuelen más de 2 ubicaciones
        self.ensure_locations_from_route(trip, carta)

        messages.success(request, "Carta Porte guardada.")
        return redirect(self.get_success_url(trip))
