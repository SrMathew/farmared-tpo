"""q13 - Customer management: sign-up, change of contact and coverage data, logical delete.

Purpose:    the three write operations on customers.
Engine:     MongoDB (collection `clientes`, counter of identifiers in `counters`).
Relation:   none to resolve: a customer is a document on its own. Nothing here feeds a
            Redis key, so Redis is not touched.

create_customer(customers, nombre, apellido, dni, obra_social, nro_afiliado, email,
                telefono, ciudad, provincia)
    Signs a customer up. The DNI must not belong to any other customer, active or not.
    The identifier is generated (C119...). The customer starts active.

update_customer(customers, id_cliente, **changes)
    Changes contact data (email, telefono, ciudad, provincia) and coverage (obra_social,
    nro_afiliado) of an active customer. Only the fields received are changed. Name and
    DNI cannot be changed. Moving to "Sin cobertura" clears the member number.

deactivate_customer(customers, id_cliente)
    Logical delete: sets `activo` to False. The document is never removed, so the sales and
    prescriptions of the customer keep their reference.

Parameters: `customers` is the repository (MongoDB in the application, in memory in the
            unit tests); the rest are the data of the operation, always as arguments.
Returns:    {"antes": ..., "despues": ...}: the customer before and after the operation
            ("antes" is None in a sign-up).
Raises:     BusinessRuleError if a rule is not met. Nothing is modified in that case.
"""

from typing import Any

from pydantic import ValidationError

from farmared.domain.enums import HealthInsurance
from farmared.domain.errors import BusinessRuleError
from farmared.domain.models import Customer
from farmared.repositories.customers import CustomerRepository

# Contact and coverage data: the only fields a modification can change.
EDITABLE_FIELDS = ("email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado")


def _customer(data: dict[str, Any]) -> Customer:
    """Build the customer, turning any broken rule into a rejection."""
    insurances = [insurance.value for insurance in HealthInsurance]
    if data["obra_social"] not in insurances:
        raise BusinessRuleError(
            f"Obra social no válida: {data['obra_social']}. "
            f"Valores permitidos: {', '.join(insurances)}"
        )
    if not str(data["dni"]).isdigit():
        raise BusinessRuleError("El DNI debe tener solo números")
    try:
        return Customer.model_validate(data)
    except ValidationError as error:
        raise BusinessRuleError(
            [detail["msg"].removeprefix("Value error, ") for detail in error.errors()]
        ) from error


def _result(before: Customer | None, after: Customer) -> dict[str, Any]:
    return {"antes": before.model_dump() if before else None, "despues": after.model_dump()}


def _existing(customers: CustomerRepository, id_cliente: str) -> Customer:
    customer = customers.get(id_cliente)
    if customer is None:
        raise BusinessRuleError(f"El cliente {id_cliente} no existe")
    if not customer.activo:
        raise BusinessRuleError(f"El cliente {id_cliente} está dado de baja")
    return customer


def create_customer(
    customers: CustomerRepository,
    nombre: str,
    apellido: str,
    dni: str,
    obra_social: str = HealthInsurance.NONE.value,
    nro_afiliado: str | None = None,
    email: str | None = None,
    telefono: str | None = None,
    ciudad: str | None = None,
    provincia: str | None = None,
) -> dict[str, Any]:
    owner = customers.find_by_dni(dni)
    if owner is not None:
        raise BusinessRuleError(f"Ya existe un cliente con DNI {dni}: {owner.id_cliente}")
    data = {
        "nombre": nombre,
        "apellido": apellido,
        "dni": dni,
        "obra_social": obra_social,
        "nro_afiliado": nro_afiliado,
        "email": email,
        "telefono": telefono,
        "ciudad": ciudad,
        "provincia": provincia,
    }
    created = customers.add(lambda id_cliente: _customer({**data, "id_cliente": id_cliente}))
    return _result(None, created)


def update_customer(
    customers: CustomerRepository, id_cliente: str, **changes: str | None
) -> dict[str, Any]:
    not_editable = sorted(set(changes) - set(EDITABLE_FIELDS))
    if not_editable:
        raise BusinessRuleError(
            f"No se puede modificar: {', '.join(not_editable)}. "
            f"Solo datos de contacto y cobertura: {', '.join(EDITABLE_FIELDS)}"
        )
    if not changes:
        raise BusinessRuleError("No se indicó ningún dato para modificar")
    before = _existing(customers, id_cliente)
    if changes.get("obra_social") == HealthInsurance.NONE.value:
        changes.setdefault("nro_afiliado", None)
    after = _customer({**before.model_dump(), **changes})
    customers.update(after)
    return _result(before, after)


def deactivate_customer(customers: CustomerRepository, id_cliente: str) -> dict[str, Any]:
    before = _existing(customers, id_cliente)
    after = before.model_copy(update={"activo": False})
    customers.update(after)
    return _result(before, after)
