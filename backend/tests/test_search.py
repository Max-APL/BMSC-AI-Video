from app.models import SearchChunk
from app.search import TfidfSearchEngine


def test_search_returns_best_chunk():
    chunks = [
        SearchChunk(
            id=0,
            segment_ids=[0],
            start_seconds=0,
            end_seconds=10,
            start_timecode="00:00:00.000",
            end_timecode="00:00:10.000",
            text="Bienvenida al curso de seguridad bancaria.",
        ),
        SearchChunk(
            id=1,
            segment_ids=[1],
            start_seconds=10,
            end_seconds=20,
            start_timecode="00:00:10.000",
            end_timecode="00:00:20.000",
            text="La autenticacion multifactor protege las cuentas.",
        ),
    ]

    matches = TfidfSearchEngine().search(
        chunks,
        query="como proteger cuentas con autenticacion",
        top_k=1,
        min_score=0.0,
    )

    assert matches[0].id == 1


def test_search_prioritizes_specific_download_fragment_over_generic_mobile_banking():
    chunks = [
        SearchChunk(
            id=0,
            segment_ids=[3],
            start_seconds=19.31,
            end_seconds=26.19,
            start_timecode="00:00:19.310",
            end_timecode="00:00:26.190",
            text="donde te enviaremos directamente la clave para probar tus transacciones en banca movil y banca por internet.",
        ),
        SearchChunk(
            id=1,
            segment_ids=[5],
            start_seconds=29.87,
            end_seconds=38.35,
            start_timecode="00:00:29.870",
            end_timecode="00:00:38.350",
            text="Primero, descarga o actualiza gratuitamente la aplicacion movil desde la tienda de aplicaciones.",
        ),
    ]

    matches = TfidfSearchEngine().search(
        chunks,
        query="desde donde descargo la app movil",
        top_k=1,
        min_score=0.0,
    )

    assert matches[0].id == 1
