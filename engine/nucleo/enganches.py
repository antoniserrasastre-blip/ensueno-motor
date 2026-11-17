"""Los módulos que se enganchan al núcleo (claves del bloque, validadores del cierre, secciones del briefing,
tipos de orden). El cierre y el briefing los cargan siempre: quien los llame, sea la línea de órdenes, el servidor o
un test, tiene el contrato entero, sin depender de qué se importó antes."""
_hecho = False


def cargar():
    global _hecho
    if _hecho:
        return
    _hecho = True
    from . import amenazas, constitucion, fichas, forja, mundos, ordenes, trueque  # noqa: F401
