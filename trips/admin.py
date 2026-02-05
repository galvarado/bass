# admin.py
from django.contrib import admin
from .models import Trip, CartaPorteCFDI, CartaPorteGoods, CartaPorteItem, CartaPorteLocation

admin.site.register(Trip)
admin.site.register(CartaPorteCFDI)
admin.site.register(CartaPorteGoods)
admin.site.register(CartaPorteItem)
admin.site.register(CartaPorteLocation)