from app.manual_review import review_manual_content
from app.models import ManualQualityMode, ManualRequest


def test_manual_request_defaults_to_fast_quality_mode():
    request = ManualRequest()

    assert request.quality_mode == ManualQualityMode.fast


def test_manual_request_accepts_quality_mode():
    request = ManualRequest(quality_mode="quality")

    assert request.quality_mode == ManualQualityMode.quality


def test_review_manual_content_flags_generic_short_manual():
    content = """
# Manual operativo: capacitacion

## Objeto
Documentar de forma ordenada el procedimiento explicado en el video sobre capacitacion.

## Alcance
El contenido cubre unicamente los pasos del material base.
""".strip()

    report = review_manual_content(
        content,
        section_count=0,
        word_count=24,
        screenshot_count=0,
    )

    assert not report.passed
    assert report.score < 0.78
    assert {issue.code for issue in report.issues} >= {
        "too_short",
        "missing_sections",
        "few_steps",
        "generic_language",
    }


def test_review_manual_content_passes_specific_manual():
    content = """
# Manual operativo: Registro de celular

## Objeto
Registrar un dispositivo movil desde la aplicacion utilizando el codigo enviado al correo registrado.

## Alcance
Incluye la descarga de la aplicacion, el ingreso con credenciales, el envio del codigo y la confirmacion del equipo.

## Procedimiento detallado

### Registro inicial

#### Procedimiento
1. Descargue o actualice la aplicacion BMSC Movil desde la tienda correspondiente.
2. Ingrese con el usuario y la contrasena de banca por internet.
3. Presione el boton para enviar el codigo al correo electronico registrado.
4. Introduzca el codigo recibido en el campo de validacion.
5. Confirme el registro del dispositivo cuando aparezca el mensaje de finalizacion.
""".strip()

    report = review_manual_content(
        content,
        section_count=1,
        word_count=220,
        screenshot_count=0,
    )

    assert report.passed
    assert report.score >= 0.78
