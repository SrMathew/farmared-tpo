"""q13 - Customer management: sign-up, change of contact and coverage data, logical delete."""

import pytest
from fakes.customers import InMemoryCustomers

from farmared.adapters.mongo.customers import MongoCustomers
from farmared.adapters.mongo.documents import COUNTERS
from farmared.cli import main
from farmared.domain.errors import BusinessRuleError
from farmared.domain.models import Customer
from farmared.services.q13_customer_management import (
    create_customer,
    deactivate_customer,
    update_customer,
)

ANA = Customer(
    id_cliente="C001",
    nombre="Ana",
    apellido="Gil",
    dni="30111222",
    email="ana@mail.com",
    obra_social="OSDE",
    nro_afiliado="OS-1",
)
INACTIVE = Customer(
    id_cliente="C002", nombre="Luis", apellido="Rey", dni="20333444", obra_social="Sin cobertura"
).model_copy(update={"activo": False})


@pytest.fixture
def customers():
    return InMemoryCustomers([ANA, INACTIVE], last_number=2)


# --- The rules, without database engines ------------------------------------------------


@pytest.mark.unit
def test_sign_up_stores_an_active_customer_with_a_new_identifier(customers):
    result = create_customer(
        customers, "Eva", "Sosa", "35000111", obra_social="PAMI", nro_afiliado="PA-9"
    )

    assert result["antes"] is None
    assert result["despues"] == {
        "activo": True,
        "id_cliente": "C003",
        "nombre": "Eva",
        "apellido": "Sosa",
        "dni": "35000111",
        "email": None,
        "telefono": None,
        "ciudad": None,
        "provincia": None,
        "obra_social": "PAMI",
        "nro_afiliado": "PA-9",
    }
    assert customers.get("C003") is not None


@pytest.mark.unit
def test_sign_up_without_coverage_by_default(customers):
    result = create_customer(customers, "Eva", "Sosa", "35000111")

    assert result["despues"]["obra_social"] == "Sin cobertura"
    assert result["despues"]["nro_afiliado"] is None


@pytest.mark.unit
def test_sign_up_rejects_a_dni_that_already_exists(customers):
    with pytest.raises(BusinessRuleError, match="Ya existe un cliente con DNI 30111222: C001"):
        create_customer(customers, "Otra", "Persona", "30111222")

    assert len(customers.stored) == 2


@pytest.mark.unit
def test_the_dni_of_an_inactive_customer_is_still_taken(customers):
    with pytest.raises(BusinessRuleError, match="Ya existe un cliente con DNI 20333444"):
        create_customer(customers, "Otra", "Persona", "20333444")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"dni": "35.000.111"}, "El DNI debe tener solo números"),
        ({"obra_social": "Medifé", "nro_afiliado": "M-1"}, "Obra social no válida: Medifé"),
        ({"obra_social": "OSDE"}, "Un cliente con cobertura necesita número de afiliado"),
        ({"nro_afiliado": "X-1"}, "Un cliente sin cobertura no lleva número de afiliado"),
    ],
)
def test_sign_up_rejects_invalid_data_and_uses_up_no_identifier(customers, data, message):
    eva = {"nombre": "Eva", "apellido": "Sosa", "dni": "35000111"}

    with pytest.raises(BusinessRuleError, match=message):
        create_customer(customers, **eva | data)

    assert len(customers.stored) == 2
    assert create_customer(customers, "Eva", "Sosa", "35000111")["despues"]["id_cliente"] == "C003"


@pytest.mark.unit
def test_update_changes_only_the_fields_received(customers):
    result = update_customer(customers, "C001", telefono="1155550000", ciudad="Rosario")

    assert result["antes"] == ANA.model_dump()
    assert result["despues"] == ANA.model_dump() | {"telefono": "1155550000", "ciudad": "Rosario"}
    assert customers.get("C001").telefono == "1155550000"


@pytest.mark.unit
def test_moving_to_no_coverage_clears_the_member_number(customers):
    result = update_customer(customers, "C001", obra_social="Sin cobertura")

    assert result["despues"]["nro_afiliado"] is None


@pytest.mark.unit
def test_update_rejects_name_and_dni(customers):
    with pytest.raises(BusinessRuleError, match="No se puede modificar: dni, nombre"):
        update_customer(customers, "C001", dni="1", nombre="Otra")

    assert customers.get("C001") == ANA


@pytest.mark.unit
@pytest.mark.parametrize(
    ("id_cliente", "changes", "message"),
    [
        ("C999", {"email": "x@mail.com"}, "El cliente C999 no existe"),
        ("C002", {"email": "x@mail.com"}, "El cliente C002 está dado de baja"),
        ("C001", {}, "No se indicó ningún dato para modificar"),
        ("C001", {"obra_social": "Medifé"}, "Obra social no válida"),
        ("C001", {"nro_afiliado": None}, "Un cliente con cobertura necesita número"),
    ],
)
def test_update_rejections_leave_the_customer_as_it_was(customers, id_cliente, changes, message):
    before = dict(customers.stored)

    with pytest.raises(BusinessRuleError, match=message):
        update_customer(customers, id_cliente, **changes)

    assert customers.stored == before


@pytest.mark.unit
def test_deactivation_is_logical_the_customer_is_kept(customers):
    result = deactivate_customer(customers, "C001")

    assert result["antes"]["activo"] is True
    assert result["despues"] == ANA.model_dump() | {"activo": False}
    assert customers.get("C001") is not None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("id_cliente", "message"),
    [("C999", "El cliente C999 no existe"), ("C002", "El cliente C002 está dado de baja")],
)
def test_deactivation_rejections(customers, id_cliente, message):
    with pytest.raises(BusinessRuleError, match=message):
        deactivate_customer(customers, id_cliente)


# --- Against MongoDB --------------------------------------------------------------------


@pytest.mark.integration
def test_sign_up_continues_the_numbering_of_the_loaded_customers(loaded_for_writing):
    result = create_customer(MongoCustomers(loaded_for_writing), "Eva", "Sosa", "35000111")

    # The course data ends at C008 and the additional records at C110.
    assert result["despues"]["id_cliente"] == "C111"
    assert loaded_for_writing.clientes.find_one({"_id": "C111"}) == {
        "_id": "C111",
        "activo": True,
        "nombre": "Eva",
        "apellido": "Sosa",
        "dni": "35000111",
        "email": None,
        "telefono": None,
        "ciudad": None,
        "provincia": None,
        "obra_social": "Sin cobertura",
        "nro_afiliado": None,
    }


@pytest.mark.integration
def test_rejected_sign_up_stores_nothing_and_leaves_no_gap(loaded_for_writing):
    customers = MongoCustomers(loaded_for_writing)
    count = loaded_for_writing.clientes.count_documents({})

    with pytest.raises(BusinessRuleError, match="Ya existe un cliente con DNI 31245678: C001"):
        create_customer(customers, "Otra", "Persona", "31245678")
    with pytest.raises(BusinessRuleError, match="necesita número de afiliado"):
        create_customer(customers, "Eva", "Sosa", "35000111", obra_social="OSDE")

    assert loaded_for_writing.clientes.count_documents({}) == count
    assert create_customer(customers, "Eva", "Sosa", "35000111")["despues"]["id_cliente"] == "C111"


@pytest.mark.integration
def test_unique_index_stops_a_duplicate_the_service_did_not_see(loaded_for_writing):
    # Two simultaneous sign-ups both pass the check of the service; the index decides.
    customers = MongoCustomers(loaded_for_writing)
    twin = Customer(
        id_cliente="C000",
        nombre="Otra",
        apellido="Persona",
        dni="31245678",
        obra_social="Sin cobertura",
    )

    with pytest.raises(BusinessRuleError, match="Ya existe un cliente con ese DNI"):
        customers.add(lambda id_cliente: twin.model_copy(update={"id_cliente": id_cliente}))

    # The transaction was aborted: the counter went back with it.
    assert loaded_for_writing[COUNTERS].find_one({"_id": "CUSTOMER"})["seq"] == 110


@pytest.mark.integration
def test_update_and_logical_delete_are_stored(loaded_for_writing):
    customers = MongoCustomers(loaded_for_writing)
    count = loaded_for_writing.clientes.count_documents({})

    update_customer(customers, "C003", email="carla@nuevo.com", obra_social="Sin cobertura")
    stored = loaded_for_writing.clientes.find_one({"_id": "C003"})
    assert (stored["email"], stored["obra_social"], stored["nro_afiliado"]) == (
        "carla@nuevo.com",
        "Sin cobertura",
        None,
    )
    assert stored["dni"] == "40123456"  # the rest is untouched

    deactivate_customer(customers, "C003")
    assert loaded_for_writing.clientes.find_one({"_id": "C003"})["activo"] is False
    assert loaded_for_writing.clientes.count_documents({}) == count  # nothing was removed

    with pytest.raises(BusinessRuleError, match="El cliente C003 está dado de baja"):
        update_customer(customers, "C003", email="otro@mail.com")


@pytest.mark.integration
def test_command_line_runs_the_three_operations(loaded_for_writing, capsys):
    assert main(["q13", "alta", "--nombre", "Eva", "--apellido", "Sosa", "--dni", "35000111"]) == 0
    assert '"id_cliente": "C111"' in capsys.readouterr().out

    assert main(["q13", "modificar", "C111", "--obra-social", "PAMI", "--nro-afiliado", "P-9"]) == 0
    assert '"obra_social": "PAMI"' in capsys.readouterr().out

    assert main(["q13", "baja", "C111"]) == 0
    assert "q13 - Baja lógica del cliente C111" in capsys.readouterr().out

    assert main(["q13", "alta", "--nombre", "X", "--apellido", "Y", "--dni", "35000111"]) == 1
    assert "Ya existe un cliente con DNI 35000111: C111" in capsys.readouterr().out
