# admin.py
from django.contrib import admin
from .models import SparePart, SparePartPurchase

admin.site.register(SparePart)
admin.site.register(SparePartPurchase)