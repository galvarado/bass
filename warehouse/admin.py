# admin.py
from django.contrib import admin
from .models import SparePart, SparePartPurchase, SparePartMovement, SparePartPurchaseItem

admin.site.register(SparePart)
admin.site.register(SparePartPurchase)
admin.site.register(SparePartPurchaseItem)
admin.site.register(SparePartMovement)
