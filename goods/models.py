# mercancias/models.py
from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        # Soft delete en lote
        return super().update(deleted=True)

    def hard_delete(self):
        # Borrado físico
        return super().delete()

    def alive(self):
        return self.filter(deleted=False)

    def dead(self):
        return self.filter(deleted=True)


class SoftDeleteManager(models.Manager):
    """Devuelve SOLO registros no eliminados por defecto."""
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted=False)

    def with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return self.with_deleted().dead()


class Mercancia(models.Model):
    """
    Catálogo de mercancías (para Carta Porte / Comercio Exterior).
    - clave: clave interna o del catálogo que uses
    - nombre: descripción
    - fraccion_arancelaria: 8 dígitos típicamente (puede venir con más, por eso string)
    - comercio_exterior_uuid: UUID del complemento de Comercio Exterior (si aplica)
    """

    clave = models.CharField(max_length=50, unique=True, db_index=True)
    nombre = models.CharField(max_length=255)

    fraccion_arancelaria = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Fracción arancelaria",
        help_text="Ej: 01012101 (se guarda como texto por posibles variantes/formato).",
    )

    comercio_exterior_uuid = models.UUIDField(
        blank=True,
        null=True,
        unique=True,
        verbose_name="UUID Comercio Exterior",
        help_text="UUID asociado a comercio exterior (si aplica).",
    )

    # --- Soft delete ---
    deleted = models.BooleanField(default=False, db_index=True)

    # Managers
    objects = models.Manager()       
    alive = SoftDeleteQuerySet.as_manager()   


    class Meta:
        verbose_name = "Mercancía"
        verbose_name_plural = "Mercancías"
        ordering = ["clave", "nombre"]
        indexes = [
            models.Index(fields=["deleted", "clave"]),
            models.Index(fields=["deleted", "nombre"]),
        ]

    def __str__(self):
        return f"{self.clave} - {self.nombre}"

    def soft_delete(self, using=None, keep_parents=False):
        """Soft delete individual."""
        if not self.deleted:
            self.deleted = True
            self.save(update_fields=["deleted"])
