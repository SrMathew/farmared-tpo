"""Allowed values of the domain fields.

Names are in English like the rest of the code; values are kept exactly as the course
datasets write them, because they are the data.
"""

from enum import StrEnum


class HealthInsurance(StrEnum):
    OSDE = "OSDE"
    SWISS_MEDICAL = "Swiss Medical"
    PAMI = "PAMI"
    IOMA = "IOMA"
    GALENO = "Galeno"
    NONE = "Sin cobertura"


class BranchType(StrEnum):
    PHARMACY = "Farmacia"
    WAREHOUSE = "Droguería"


class PharmacistRole(StrEnum):
    TECHNICAL_DIRECTOR = "Director Técnico"
    PHARMACIST = "Farmacéutico"


class SupplierType(StrEnum):
    LABORATORY = "Laboratorio"
    WAREHOUSE = "Droguería"


class SaleCondition(StrEnum):
    OVER_THE_COUNTER = "Venta libre"
    PRESCRIPTION = "Bajo receta"
    FILED_PRESCRIPTION = "Bajo receta archivada"


class PrescriptionType(StrEnum):
    SIMPLE = "Simple"
    FILED = "Archivada"
    LONG_TERM = "Tratamiento prolongado"


class PrescriptionStatus(StrEnum):
    VALID = "Vigente"
    COMPLETED = "Completada"
    EXPIRED = "Vencida"


class SaleType(StrEnum):
    OVER_THE_COUNTER = "Venta libre"
    WITH_PRESCRIPTION = "Con receta"


class PaymentMethod(StrEnum):
    CASH = "Efectivo"
    DEBIT = "Débito"
    CREDIT = "Crédito"
    TRANSFER = "Transferencia"
    HEALTH_INSURANCE = "Obra social"


class SaleStatus(StrEnum):
    COMPLETED = "Completada"
    PENDING = "Pendiente"
    CANCELLED = "Anulada"
