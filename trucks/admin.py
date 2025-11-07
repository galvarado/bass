# admin.py
from django.contrib import admin
from .models import Truck, ReeferBox

admin.site.register(Truck)
admin.site.register(ReeferBox)