# trips/views_carta_porte.py
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from .models import Trip, CartaPorteCFDI, CartaPorteLocation, CartaPorteItem
from .forms import (
    CartaPorteCFDIForm,
    get_carta_porte_location_formset,
    get_carta_porte_goods_formset,
    get_carta_porte_item_formset,
)

# ✅ Facturapi service
from .services.facturapi import create_invoice_in_facturapi, FacturapiError


class CartaPorteEditView(TemplateView):
    template_name = "trips/carta_porte_form.html"

    # ======================================================
    # SAT helpers
    # ======================================================
    ESTADO_SAT_MAP = {
        "Aguascalientes": "AGS",
        "Baja California": "BCN",
        "Baja California Sur": "BCS",
        "Campeche": "CAM",
        "Chiapas": "CHP",
        "Chihuahua": "CHH",
        "Ciudad de México": "CMX",
        "Coahuila": "COA",
        "Colima": "COL",
        "Durango": "DUR",
        "Guanajuato": "GUA",
        "Guerrero": "GRO",
        "Hidalgo": "HID",
        "Jalisco": "JAL",
        "México": "MEX",
        "Michoacán": "MIC",
        "Morelos": "MOR",
        "Nayarit": "NAY",
        "Nuevo León": "NLE",
        "Oaxaca": "OAX",
        "Puebla": "PUE",
        "Querétaro": "QUE",
        "Quintana Roo": "ROO",
        "San Luis Potosí": "SLP",
        "Sinaloa": "SIN",
        "Sonora": "SON",
        "Tabasco": "TAB",
        "Tamaulipas": "TAM",
        "Tlaxcala": "TLA",
        "Veracruz": "VER",
        "Yucatán": "YUC",
        "Zacatecas": "ZAC",
    }

    @staticmethod
    def estado_sat(nombre):
        return CartaPorteEditView.ESTADO_SAT_MAP.get(nombre, "")[:3]

    @staticmethod
    def pais_sat(_):
        return "MX"

    # ======================================================
    # Helpers base
    # ======================================================
    def get_trip(self):
        return get_object_or_404(Trip, pk=self.kwargs["trip_id"], deleted=False)

    def get_carta(self, trip: Trip):
        carta, _ = CartaPorteCFDI.objects.get_or_create(trip=trip)
        return carta

    def get_success_url(self, trip: Trip):
        return reverse("trips:detail", kwargs={"pk": trip.id})

    # ======================================================
    # Subtotal snapshot (del viaje)
    # ======================================================
    def ensure_subtotal_from_trip(self, trip: Trip, carta: CartaPorteCFDI):
        current = getattr(carta, "subtotal", None)
        if current is not None and current != Decimal("0.00"):
            return

        subtotal = Decimal("0.00")

        if getattr(trip, "tarifa_cliente_snapshot", None):
            subtotal = trip.tarifa_cliente_snapshot or Decimal("0.00")

        if subtotal == Decimal("0.00") and trip.route:
            subtotal = getattr(trip.route, "tarifa_cliente", None) or Decimal("0.00")

        carta.subtotal = subtotal
        carta.save(update_fields=["subtotal"])

    # ======================================================
    # ✅ EXACTAMENTE 1 CONCEPTO
    # - precio = subtotal
    # - si hay 2+, borra extras
    # ======================================================
    def ensure_single_item_from_subtotal(self, trip: Trip, carta: CartaPorteCFDI):
        subtotal = (carta.subtotal or Decimal("0.00")).quantize(Decimal("0.01"))

        # texto por default
        route_str = str(trip.route) if trip.route_id else "Servicio de transporte"
        default_desc = f"Flete {route_str}"[:255]

        qs = carta.items.order_by("orden", "id")
        first = qs.first()

        if not first:
            # crea 1
            CartaPorteItem.objects.create(
                carta_porte=carta,
                orden=0,
                cantidad=Decimal("1.000"),
                unidad="E48",  # mejor solo clave (evita texto largo)
                producto="FLETE",
                descripcion=default_desc,
                precio=subtotal,
                descuento=Decimal("0.00"),
                iva_pct=Decimal("16.00"),
                ret_iva_pct=Decimal("0.00"),
            )
            return

        # borra extras (si existían)
        qs.exclude(id=first.id).delete()

        changed = False

        # normaliza cantidad
        if (first.cantidad is None) or (first.cantidad <= Decimal("0")):
            first.cantidad = Decimal("1.000")
            changed = True

        # fuerza precio = subtotal si viene vacío/0
        if subtotal > Decimal("0.00") and ((first.precio is None) or (first.precio <= Decimal("0.00"))):
            first.precio = subtotal
            changed = True

        if not (first.descripcion or "").strip():
            first.descripcion = default_desc
            changed = True

        if (first.unidad or "").strip() == "":
            first.unidad = "E48"
            changed = True

        if (first.producto or "").strip() == "":
            first.producto = "FLETE"
            changed = True

        if changed:
            first.orden = 0
            first.save()

    # ======================================================
    # Forms
    # ======================================================
    def build_forms(self, *, request, carta: CartaPorteCFDI, trip: Trip, bound: bool):
        LocationFS = get_carta_porte_location_formset()
        GoodsFS = get_carta_porte_goods_formset()
        ItemsFS = get_carta_porte_item_formset()

        if bound:
            form = CartaPorteCFDIForm(request.POST, instance=carta)
            fs_locations = LocationFS(request.POST, instance=carta, prefix="loc")
            fs_goods = GoodsFS(request.POST, instance=carta, prefix="goods")
            fs_items = ItemsFS(request.POST, instance=carta, prefix="cpitem")
            return form, fs_locations, fs_goods, fs_items

        initial = {}

        try:
            if trip.route and trip.route.origen and trip.route.origen.client_id:
                if not getattr(carta, "customer_id", None):
                    initial["customer"] = trip.route.origen.client_id
        except Exception:
            pass

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
        fs_items = ItemsFS(instance=carta, prefix="cpitem")
        return form, fs_locations, fs_goods, fs_items

    # ======================================================
    # Locations from route (SAT-safe)
    # ======================================================
    def ensure_locations_from_route(self, trip: Trip, carta: CartaPorteCFDI):
        r = trip.route
        if not r:
            return

        carta.locations.exclude(tipo_ubicacion__in=["Origen", "Destino"]).delete()

        def client_rfc(loc_model):
            rfc = getattr(getattr(loc_model, "client", None), "rfc", "")
            return rfc or "XAXX010101000"

        def build(loc_model, tipo, orden, dt):
            return CartaPorteLocation(
                carta_porte=carta,
                tipo_ubicacion=tipo,
                orden=orden,
                rfc=client_rfc(loc_model),
                nombre=loc_model.nombre or "",
                localidad=loc_model.poblacion or "",
                codigo_postal=loc_model.cp or "",
                calle=loc_model.calle or "",
                numero_exterior=loc_model.no_ext or "",
                numero_interior="",
                colonia=loc_model.colonia_sat or loc_model.colonia or "",
                municipio=loc_model.municipio or "",
                estado=self.estado_sat(loc_model.estado),
                pais="MX",
                referencia=loc_model.referencias or "",
            )

        dt_origen = getattr(trip, "departure_origin_at", None) or timezone.now()
        dt_destino = getattr(trip, "arrival_destination_at", None) or timezone.now()

        o = carta.locations.filter(tipo_ubicacion="Origen").first()
        if not o:
            o = build(r.origen, "Origen", 0, dt_origen)
            o.save()
        else:
            o.orden = 0
            o.rfc = o.rfc or client_rfc(r.origen)
            o.estado = o.estado or self.estado_sat(r.origen.estado)
            o.pais = "MX"
            o.save()

        d = carta.locations.filter(tipo_ubicacion="Destino").first()
        if not d:
            d = build(r.destino, "Destino", 99, dt_destino)
            d.save()
        else:
            d.orden = 99
            d.rfc = d.rfc or client_rfc(r.destino)
            d.estado = d.estado or self.estado_sat(r.destino.estado)
            d.pais = "MX"
            d.save()

        carta.locations.exclude(id__in=[o.id, d.id]).delete()

    # ======================================================
    # Context
    # ======================================================
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        trip = self.get_trip()
        carta = self.get_carta(trip)

        self.ensure_locations_from_route(trip, carta)
        self.ensure_subtotal_from_trip(trip, carta)

        # ✅ asegura 1 concepto antes de construir formset
        self.ensure_single_item_from_subtotal(trip, carta)

        form, fs_locations, fs_goods, fs_items = self.build_forms(
            request=self.request, carta=carta, trip=trip, bound=False
        )

        ctx.update({
            "trip": trip,
            "carta": carta,
            "form": form,
            "fs_locations": fs_locations,
            "fs_goods": fs_goods,
            "fs_items": fs_items,
            # ✅ UX: solo mostrar botón "Generar CFDI" después de guardar (flag en sesión)
            "can_generate_cfdi": self.request.session.get(f"cp_saved_{trip.id}", False),
        })
        return ctx

    # ======================================================
    # POST
    # ======================================================
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        trip = self.get_trip()
        carta = self.get_carta(trip)

        form, fs_locations, fs_goods, fs_items = self.build_forms(
            request=request, carta=carta, trip=trip, bound=True
        )

        if not (form.is_valid() and fs_locations.is_valid() and fs_goods.is_valid() and fs_items.is_valid()):
            messages.error(request, "Revisa los errores del formulario.")
            return self.render_to_response({
                "trip": trip,
                "carta": carta,
                "form": form,
                "fs_locations": fs_locations,
                "fs_goods": fs_goods,
                "fs_items": fs_items,
                "can_generate_cfdi": request.session.get(f"cp_saved_{trip.id}", False),
            })

        # Acción (guardar o generar)
        action = (request.POST.get("action") or "save").strip()

        carta = form.save(commit=False)
        carta.customer = form.cleaned_data.get("customer")
        carta.save()  # ✅ guarda cambios del form (incluye timestamps)

        # Si fue un guardado normal y aún está draft => listo para generar
        if carta.status == "draft":
            carta.status = "ready"
            carta.last_error = ""
            carta.save(update_fields=["status", "last_error", "updated_at"])

        # ---- Locations
        fs_locations.save()

        # ---- Goods
        goods = fs_goods.save(commit=False)

        for obj in fs_goods.deleted_objects:
            obj.delete()

        for g in goods:
            if not g.mercancia_id:
                if g.pk:
                    g.delete()
                continue
            g.carta_porte = carta
            g.save()

        # ======================================================
        # ✅ ITEMS: forzar EXACTAMENTE 1
        # ======================================================
        carta.items.all().delete()

        items = fs_items.save(commit=False)
        for obj in fs_items.deleted_objects:
            obj.delete()

        it = items[0] if items else None

        subtotal = (carta.subtotal or Decimal("0.00")).quantize(Decimal("0.01"))
        route_str = str(trip.route) if trip.route_id else "Servicio de transporte"
        default_desc = f"Flete {route_str}"[:255]

        if it is None:
            CartaPorteItem.objects.create(
                carta_porte=carta,
                orden=0,
                cantidad=Decimal("1.000"),
                unidad="E48",
                producto="FLETE",
                descripcion=default_desc,
                precio=subtotal,
                descuento=Decimal("0.00"),
                iva_pct=Decimal("16.00"),
                ret_iva_pct=Decimal("0.00"),
            )
        else:
            it.carta_porte = carta
            it.orden = 0

            if (it.cantidad is None) or (it.cantidad <= Decimal("0")):
                it.cantidad = Decimal("1.000")

            if subtotal > Decimal("0.00") and ((it.precio is None) or (it.precio <= Decimal("0.00"))):
                it.precio = subtotal

            if not (it.descripcion or "").strip():
                it.descripcion = default_desc

            if not (it.unidad or "").strip():
                it.unidad = "E48"

            if not (it.producto or "").strip():
                it.producto = "FLETE"

            it.save()

        # ======================================================
        # Totales:
        # - subtotal VIENE DEL VIAJE (snapshot)
        # - total = subtotal + iva - ret
        # (NO recalculamos subtotal desde items)
        # ======================================================
        carta.compute_total()
        carta.save(update_fields=["total", "updated_at"])

        # por si cambió ruta/locs
        self.ensure_locations_from_route(trip, carta)

        # ✅ Marca que ya se guardó (para mostrar botón "Generar CFDI")
        request.session[f"cp_saved_{trip.id}"] = True

        # ======================================================
        # Generar CFDI (Facturapi)
        # ======================================================
        if action == "generate_cfdi":
            if carta.status == "stamped" and carta.uuid:
                messages.info(request, f"Este CFDI ya fue generado (UUID: {carta.uuid}).")
                return redirect(self.get_success_url(trip))

            if carta.status == "canceled":
                messages.error(request, "Este CFDI está cancelado y no puede generarse de nuevo desde aquí.")
                return redirect(self.get_success_url(trip))

            try:
                result = create_invoice_in_facturapi(carta=carta, trip=trip)

                carta.payload_snapshot = result.get("payload")
                carta.response_snapshot = result.get("response")

                resp = result.get("response") or {}
                carta.uuid = resp.get("uuid") or carta.uuid
                carta.pdf_url = resp.get("pdf_url") or resp.get("pdf") or carta.pdf_url
                carta.xml_url = resp.get("xml_url") or resp.get("xml") or carta.xml_url

                carta.status = resp.get("status") or "ready"
                carta.last_error = ""
                carta.save(update_fields=[
                    "payload_snapshot",
                    "response_snapshot",
                    "uuid",
                    "pdf_url",
                    "xml_url",
                    "status",
                    "last_error",
                    "updated_at",
                ])

                messages.success(request, "CFDI enviado a Facturapi correctamente.")
                return redirect(self.get_success_url(trip))

            except FacturapiError as e:
                carta.status = "error"
                carta.last_error = str(e)
                carta.save(update_fields=["status", "last_error", "updated_at"])
                messages.error(request, f"No se pudo generar CFDI: {e}")
                return redirect(self.get_success_url(trip))

        messages.success(request, "Carta Porte guardada.")
        return redirect(self.get_success_url(trip))
