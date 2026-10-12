from app.estado import EstadoCotizacion
from app.repositorios import RepositorioMemoriaCotizacion, RepositorioSesionActiva


# Prueba que la memoria persistente siga funcionando con el mock JSON por defecto.
def test_repositorio_memoria_mock_guarda_y_busca_por_contacto():
    estado = EstadoCotizacion(
        tipo_evento="matrimonio",
        asistentes=80,
        fecha_evento="2027-02-24",
        distrito="Miraflores",
        nombre_cliente="John Manchego",
        contacto="989515182",
        productos_solicitados=["vino"],
    )

    repositorio = RepositorioMemoriaCotizacion()
    repositorio.guardar(estado)
    recuperado = repositorio.buscar_por_contacto("989515182")

    assert recuperado is not None
    assert recuperado.contacto == "989515182"
    assert recuperado.tipo_evento == "matrimonio"
    assert recuperado.productos_solicitados == ["vino"]


# Prueba que la memoria corta siga funcionando con el mock JSON por defecto.
def test_repositorio_sesion_mock_guarda_obtiene_y_reinicia():
    estado = EstadoCotizacion(
        tipo_evento="cumpleanos",
        asistentes=45,
        fecha_evento="2027-03-10",
        distrito="Miraflores",
        contacto="999111222",
    )

    repositorio = RepositorioSesionActiva()
    repositorio.guardar(estado)

    recuperado = repositorio.obtener(estado.id_sesion)
    assert recuperado is not None
    assert recuperado.id_sesion == estado.id_sesion
    assert recuperado.tipo_evento == "cumpleanos"

    repositorio.reiniciar(estado.id_sesion)
    assert repositorio.obtener(estado.id_sesion) is None
