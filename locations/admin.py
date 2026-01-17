# admin.py
from django.contrib import admin
from .models import Location, Route

admin.site.register(Location)
admin.site.register(Route)