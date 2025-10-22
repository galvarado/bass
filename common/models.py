from django.db import models
from django.contrib.auth.models import User

from django.db import models

class ExchangeRate(models.Model):
    """Almacena el tipo de cambio diario USD→MXN"""
    date = models.DateField(unique=True)
    usd_mxn = models.DecimalField(max_digits=10, decimal_places=4)
    provider = models.CharField(max_length=100, default="openexchangerates.org")
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} USD/MXN {self.usd_mxn}"



