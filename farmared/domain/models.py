"""Entities of the system.

Field names are the ones of the course datasets. Every entity carries `activo`: nothing is
ever deleted, a logical delete sets it to False (business rule 2.11). Each model checks the
rules that involve a single record; rules across entities live in `rules.py`.
"""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from farmared.domain.enums import (
    BranchType,
    HealthInsurance,
    PaymentMethod,
    PharmacistRole,
    PrescriptionStatus,
    PrescriptionType,
    SaleCondition,
    SaleStatus,
    SaleType,
    SupplierType,
)

# A prescription can be dispensed at most this many times (long-term treatments).
MAX_DISPENSES = 3


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    activo: bool = True


class Customer(Entity):
    id_cliente: str
    nombre: str
    apellido: str
    dni: str = Field(pattern=r"^\d+$")
    email: str | None = None
    telefono: str | None = None
    ciudad: str | None = None
    provincia: str | None = None
    obra_social: HealthInsurance
    nro_afiliado: str | None = None

    @model_validator(mode="after")
    def _member_number_matches_insurance(self) -> Self:
        if self.obra_social == HealthInsurance.NONE and self.nro_afiliado:
            raise ValueError("Un cliente sin cobertura no lleva número de afiliado")
        if self.obra_social != HealthInsurance.NONE and not self.nro_afiliado:
            raise ValueError("Un cliente con cobertura necesita número de afiliado")
        return self


class Branch(Entity):
    id_sucursal: str
    nombre: str
    tipo: BranchType
    direccion: str | None = None
    ciudad: str | None = None
    provincia: str | None = None
    telefono: str | None = None


class Pharmacist(Entity):
    id_farmaceutico: str
    nombre: str
    apellido: str
    matricula: str
    cargo: PharmacistRole
    id_sucursal: str


class Supplier(Entity):
    id_proveedor: str
    razon_social: str
    cuit: str
    tipo: SupplierType
    ciudad: str | None = None
    provincia: str | None = None
    telefono: str | None = None


class Product(Entity):
    id_producto: str
    nombre: str
    principio_activo: str
    categoria: str
    presentacion: str
    condicion_venta: SaleCondition
    precio_unit: int = Field(gt=0)
    id_proveedor: str


class Batch(Entity):
    """Stock of one product in one branch, with its own expiry date."""

    id_lote: str
    id_producto: str
    id_sucursal: str
    nro_lote: str
    unidades: int = Field(ge=0)  # stock can never be negative
    vencimiento: date


class Prescription(Entity):
    id_receta: str
    id_cliente: str
    medico: str
    matricula_medico: str
    fecha_emision: date
    tipo: PrescriptionType
    dispensas_autorizadas: int = Field(ge=1, le=MAX_DISPENSES)
    dispensas_realizadas: int = Field(ge=0)
    proxima_dispensa: date | None = None
    estado: PrescriptionStatus

    @model_validator(mode="after")
    def _dispenses_and_status_agree(self) -> Self:
        long_term = self.tipo == PrescriptionType.LONG_TERM
        used_up = self.dispensas_realizadas == self.dispensas_autorizadas
        if self.dispensas_realizadas > self.dispensas_autorizadas:
            raise ValueError("Hay más dispensas realizadas que autorizadas")
        if not long_term and self.dispensas_autorizadas != 1:
            raise ValueError("Las recetas simples y archivadas admiten una sola dispensa")
        if used_up != (self.estado == PrescriptionStatus.COMPLETED):
            raise ValueError("La receta está 'Completada' si y solo si agotó sus dispensas")
        # The next dispense is only scheduled while a valid long-term treatment is in progress.
        in_progress = (
            long_term
            and self.estado == PrescriptionStatus.VALID
            and 0 < self.dispensas_realizadas < self.dispensas_autorizadas
        )
        if in_progress != (self.proxima_dispensa is not None):
            raise ValueError(
                "proxima_dispensa corresponde solo a un tratamiento prolongado vigente en curso"
            )
        return self


class SaleItem(BaseModel):
    """A line of a sale. It is part of the sale and has no life of its own."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id_detalle: str
    id_producto: str
    cantidad: int = Field(gt=0)
    precio_unit: int = Field(gt=0)  # price at the time of the sale, not the current list price

    @property
    def subtotal(self) -> int:
        return self.cantidad * self.precio_unit


class Sale(Entity):
    id_venta: str
    id_cliente: str
    id_farmaceutico: str
    id_sucursal: str  # branch of the pharmacist when the sale was registered
    id_receta: str | None = None
    fecha: date
    tipo: SaleType
    medio_pago: PaymentMethod
    total: int = Field(ge=0)
    estado: SaleStatus
    items: list[SaleItem] = Field(min_length=1)
    stock_aplicado: bool = False  # True once the stock of this sale has been discounted

    @model_validator(mode="after")
    def _type_and_total_agree_with_content(self) -> Self:
        if (self.tipo == SaleType.WITH_PRESCRIPTION) != (self.id_receta is not None):
            raise ValueError("La venta es 'Con receta' si y solo si tiene una receta asociada")
        if self.total != sum(item.subtotal for item in self.items):
            raise ValueError("El total de la venta no coincide con la suma de sus ítems")
        if self.stock_aplicado and self.estado != SaleStatus.COMPLETED:
            raise ValueError("Solo una venta 'Completada' descuenta stock")
        return self
