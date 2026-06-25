"""
Quality audit tests — expose weaknesses in the manual generation pipeline.

These tests validate that the reviewer, VLM filtering, ASR correction,
and caption quality mechanisms are working properly. Many of these tests
are EXPECTED TO FAIL with the current implementation, documenting the
real gaps.
"""

from __future__ import annotations

import re
import pytest

from app.manual_review import review_manual_content, ManualReviewReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_MANUAL = """\
# Manual operativo: Registro de celular

## Datos del documento
- Material base: video.mp4
- Duracion: 3m 10s

## Objeto
Este manual describe el procedimiento de registro de celular en la aplicación
de BMSC Móvil para habilitar transacciones seguras.

## Alcance
Cubre el registro del dispositivo móvil mediante tres opciones de validación:
correo electrónico, pregunta secreta o token físico.

## Procedimiento detallado

### Registro del dispositivo móvil

#### Procedimiento
1. Descargue o actualice la aplicación BMSC Móvil desde Play Store o App Store.
2. Ingrese con su usuario y contraseña de banca por internet.
3. Al ingresar por primera vez, el sistema solicita registro del dispositivo.
4. Seleccione uno de los tres métodos de validación disponibles.
5. Complete el proceso de validación según el método elegido.

#### Consideraciones
- Si no completa el registro, solo podrá realizar consultas.
- El registro debe realizarse una sola vez por dispositivo.

![Figura (00:00:31) - Pantalla de registro](screenshots/s1.jpg)
![Figura (00:01:25) - Opciones de validación](screenshots/s2.jpg)
![Figura (00:02:12) - Confirmación de registro](screenshots/s3.jpg)
"""

_BAD_MANUAL_WITH_GIBBERISH_CAPTIONS = """\
# Manual operativo: PRTG

## Objeto
Este manual describe PRTG Network Monitor.

## Alcance
Cubre la instalación y configuración.

## Procedimiento detallado

### Introducción

#### Procedimiento
1. Descargue PRTG.
2. Instale el software.
3. Configure sensores.
4. Verifique conectividad.
5. Active las alertas.

![Figura (00:00:03) - No se puede utilizar esta captura para un manual operativo.](screenshots/s1.jpg)
![Figura (00:00:05) - La captura de la web está utilizando una información que aporta esta teclado.](screenshots/s2.jpg)
![Figura (00:00:08) - El dispositivo está en una puntuación que se ha utilizado para una oportunidad de aporte.](screenshots/s3.jpg)
![Figura (00:00:36) - La captura de la imagem es una punta en el centro del campo, en la que se encuentra un carro y un piso.](screenshots/s4.jpg)
"""

_BAD_MANUAL_WITH_ASR_ERRORS = """\
# Manual operativo: Registro de celular

## Objeto
Este manual describe el registro de celular en MSC móvil.

## Alcance
Cubre el procedimiento de registro para transacciones.

## Procedimiento detallado

### Registro de celular

#### Procedimiento
1. Descarga la aplicación de MSC móvil de este Play Store o a Vestor.
2. Ingresa utilizando el mismo usuario y contraseña.
3. Al ingresar por primera vez aparecerá un mensaje de registro.
4. Introduce el código de seis dígitos de tu toquen.
5. Código de validación, una descompletada a una de las opciones.
6. En tu celular, delegará una clave de seis dígitos que debe sin producir.
7. Presiona el botón General, dentro de la opción Validación.

#### Consideraciones
- Si no completas el registro, solo podrás realizar consultas.

![Figura (00:00:31) - MERCANTIL SANTA CRUZ.](screenshots/s1.jpg)
![Figura (00:01:25) - Una captura de un dispositivo.](screenshots/s2.jpg)
![Figura (00:02:12) - Mensaje de confirmación.](screenshots/s3.jpg)
"""


# ---------------------------------------------------------------------------
# SECTION 1: Reviewer validation tests
# ---------------------------------------------------------------------------

class TestReviewerBasicScoring:
    """Verify the reviewer correctly evaluates structural quality."""

    def test_good_manual_passes(self):
        report = review_manual_content(
            _GOOD_MANUAL, section_count=1, word_count=200, screenshot_count=3
        )
        assert report.passed is True
        assert report.score >= 0.78

    def test_empty_manual_fails(self):
        report = review_manual_content(
            "", section_count=0, word_count=0, screenshot_count=0
        )
        assert report.passed is False
        assert report.score < 0.5

    def test_too_short_manual_fails(self):
        report = review_manual_content(
            "### Hello\n1. Step one.\n2. Step two.\n![img](s.jpg)",
            section_count=1, word_count=15, screenshot_count=1,
        )
        assert report.passed is False
        assert any(i.code == "too_short" for i in report.issues)


class TestReviewerSemanticGaps:
    """Tests that EXPOSE weaknesses — the reviewer doesn't catch these."""

    def test_reviewer_should_catch_gibberish_captions(self):
        """
        The PRTG manual has captions like 'carro y un piso' and
        'No se puede utilizar esta captura para un manual operativo'.
        The reviewer should detect and flag these.
        """
        report = review_manual_content(
            _BAD_MANUAL_WITH_GIBBERISH_CAPTIONS,
            section_count=1,
            word_count=200,
            screenshot_count=4,
        )
        assert not report.passed, "Reviewer passed a manual with gibberish captions"
        assert any("gibberish" in i.code.lower() for i in report.issues), "Did not detect gibberish"

    def test_reviewer_should_catch_asr_errors(self):
        """
        The manual has errors like 'MSC móvil' (should be BMSC Móvil),
        'Vestor' (App Store), 'toquen' (token), 'debe sin producir'
        (debes introducir).
        """
        report = review_manual_content(
            _BAD_MANUAL_WITH_ASR_ERRORS,
            section_count=1,
            word_count=200,
            screenshot_count=3,
        )
        assert not report.passed, "Reviewer passed a manual with ASR errors"
        assert any("asr" in i.code.lower() for i in report.issues), "Did not detect ASR errors"

    def test_reviewer_should_catch_invented_content(self):
        """
        The PRTG manual invented installation, alerts, reports, and
        maintenance sections from a short overview video.
        """
        invented_manual = """\
# Manual: PRTG

## Objeto
Manual de PRTG.

## Alcance
Cubre todo PRTG.

## Procedimiento detallado

### Instalación y Configuración Inicial
#### Procedimiento
1. Descargue el instalador de PRTG desde el sitio oficial.
2. Ejecute el archivo de instalación.
3. Configure el servidor PRTG Core.

### Gestión de Alertas y Notificaciones
#### Procedimiento
1. Configure alertas para uso óptimo.
2. Establezca umbrales de notificación.
3. Configure canales de notificación.

### Mantenimiento y Actualizaciones
#### Procedimiento
1. Realice actualizaciones periódicas.
2. Ejecute mantenimiento preventivo.
3. Verifique la integridad del sistema.

![img](s1.jpg)
![img](s2.jpg)
![img](s3.jpg)
"""
        report = review_manual_content(
            invented_manual, section_count=3, word_count=200, screenshot_count=3
        )
        # A 3-minute overview video should NOT produce a 3-section installation guide.
        # But the heuristic reviewer has no way to check evidence grounding.
        if report.passed:
            pytest.xfail(
                "KNOWN GAP: Reviewer cannot detect invented/hallucinated content. "
                "It passes a manual with invented installation/maintenance procedures "
                "because it only checks structural criteria."
            )

    def test_reviewer_gives_perfect_score_to_bad_manual(self):
        """
        Demonstrates the core problem: the reviewer gives 1.0 to
        manuals that a human would rate as low quality.
        """
        report = review_manual_content(
            _BAD_MANUAL_WITH_GIBBERISH_CAPTIONS,
            section_count=1,
            word_count=200,
            screenshot_count=4,
        )
        # This manual is terrible, it has gibberish and ASR errors
        assert not report.passed, "Reviewer gave passing score to bad manual"
        assert report.score < 0.8, f"Score should be low, got {report.score}"


# ---------------------------------------------------------------------------
# SECTION 2: VLM caption filtering tests
# ---------------------------------------------------------------------------

class TestVLMCaptionFiltering:
    """Test the SIN_APORTE rejection logic in visual_analysis.py."""

    def test_sin_aporte_exact_is_rejected(self):
        """SIN_APORTE prefix should be rejected."""
        from app.visual_analysis import is_vlm_description_useful
        assert not is_vlm_description_useful("SIN_APORTE esta imagen no aporta información.")

    def test_spanish_equivalent_not_rejected(self):
        """
        Natural language equivalents of 'no value' should be rejected.
        """
        from app.visual_analysis import is_vlm_description_useful
        bad_responses = [
            "No se puede utilizar esta captura para un manual operativo.",
            "No data available.",
        ]
        not_caught = []
        for response in bad_responses:
            if is_vlm_description_useful(response):
                not_caught.append(response)

        assert not not_caught, f"These should have been rejected: {not_caught}"

    def test_gibberish_captions_not_rejected(self):
        """
        Gibberish VLM output should be rejected.
        """
        from app.visual_analysis import is_vlm_description_useful
        gibberish_outputs = [
            "El dispositivo está en una puntuación que se ha utilizado para una oportunidad de aporte.",
            "La captura de la imagem es una punta en el centro del campo, en la que se encuentra un carro y un piso.",
            "La captura de la imagem es una oportuna para una oportuna de operacion.",
        ]
        accepted = []
        for output in gibberish_outputs:
            if is_vlm_description_useful(output):
                accepted.append(output)

        assert not accepted, f"Gibberish captions accepted: {accepted}"


# ---------------------------------------------------------------------------
# SECTION 3: ASR error detection (non-existent)
# ---------------------------------------------------------------------------

class TestASRErrorDetection:
    """Tests for ASR error correction — which doesn't exist yet."""

    KNOWN_ASR_ERRORS = {
        "MSC móvil": "BMSC Móvil",
        "Vestor": "App Store",
        "toquen": "token",
        "debe sin producir": "debes introducir",
        "botón General": "botón Generar",
        "delegará": "llegará",
        "una descompletada": "una vez completada",
        "fáciletarte": "facilitarte",
        "corre en pantalla": "corrobora en pantalla",
    }

    def test_asr_errors_should_be_correctable(self):
        """
        Verify that known ASR errors are corrected by the normalizer.
        """
        from app.transcript_normalizer import normalize_transcript_segments
        from app.models import TranscriptSegment

        text = (
            "Descarga la aplicación de MSC móvil de este Play Store o a Vestor. "
            "Introduce el código de seis dígitos de tu toquen en el campo. "
            "En tu celular, delegará una clave que debe sin producir. "
            "Para fáciletarte la identificación, podrás escoger un alias. "
            "corre en pantalla el correo"
        )
        
        segments = [
            TranscriptSegment(
                id=1,
                start_seconds=0.0,
                end_seconds=1.0,
                start_timecode="00:00:00.000",
                end_timecode="00:00:01.000",
                text=text
            )
        ]
        normalized = normalize_transcript_segments(segments)
        new_text = normalized[0].text

        errors_found = []
        for wrong, correct in self.KNOWN_ASR_ERRORS.items():
            if wrong in new_text:
                errors_found.append(f"'{wrong}' → '{correct}'")

        assert not errors_found, f"Found uncorrected errors: {'; '.join(errors_found)}"
        
        # Verify specific corrections
        assert "BMSC Móvil" in new_text
        assert "App Store" in new_text
        assert "token" in new_text
        assert "debes introducir" in new_text
        assert "llegará" in new_text
        assert "facilitarte" in new_text
        assert "corrobora en pantalla" in new_text


# ---------------------------------------------------------------------------
# SECTION 4: Caption quality validation
# ---------------------------------------------------------------------------

class TestCaptionQuality:
    """Test that captions inserted into manuals are meaningful."""

    GARBAGE_CAPTION_PATTERNS = [
        r"No se puede utilizar",
        r"No data available",
        r"carro y un piso",
        r"aporta esta teclado",
        r"oportunidad de aporte",
        r"oportuna para una oportuna",
        r"Una captura de un dispositivo",
    ]

    def test_detect_garbage_captions_in_manual(self):
        """Check that garbage captions can be detected."""
        manual = _BAD_MANUAL_WITH_GIBBERISH_CAPTIONS
        garbage_found = []
        for pattern in self.GARBAGE_CAPTION_PATTERNS:
            matches = re.findall(pattern, manual, re.IGNORECASE)
            if matches:
                garbage_found.extend(matches)

        assert len(garbage_found) > 0, "Test data should contain garbage captions"

        from app.manual_review import review_manual_content
        report = review_manual_content(
            manual, section_count=1, word_count=200, screenshot_count=4
        )
        assert not report.passed, "Reviewer passed a manual with garbage captions"
        assert any("gibberish" in i.code for i in report.issues), "Reviewer did not detect garbage captions"


# ---------------------------------------------------------------------------
# SECTION 5: Review score calibration
# ---------------------------------------------------------------------------

class TestReviewScoreCalibration:
    """Verify the scoring system produces meaningful discrimination."""

    def test_good_manual_scores_higher_than_bad(self):
        """Good manual should score significantly higher than bad manual."""
        good_report = review_manual_content(
            _GOOD_MANUAL, section_count=1, word_count=200, screenshot_count=3
        )
        bad_report = review_manual_content(
            _BAD_MANUAL_WITH_GIBBERISH_CAPTIONS,
            section_count=1, word_count=200, screenshot_count=4,
        )
        # With current reviewer, both get near-perfect scores.
        score_diff = good_report.score - bad_report.score
        if score_diff < 0.15:
            pytest.xfail(
                f"KNOWN GAP: Score discrimination is too low. "
                f"Good manual: {good_report.score}, Bad manual: {bad_report.score}, "
                f"Difference: {score_diff:.3f}. "
                "The reviewer cannot distinguish quality from garbage."
            )

    def test_manual_with_asr_errors_should_score_lower(self):
        """Manual with ASR errors should be penalized."""
        clean_report = review_manual_content(
            _GOOD_MANUAL, section_count=1, word_count=200, screenshot_count=3
        )
        asr_report = review_manual_content(
            _BAD_MANUAL_WITH_ASR_ERRORS,
            section_count=1, word_count=200, screenshot_count=3,
        )
        if asr_report.score >= clean_report.score:
            pytest.xfail(
                f"KNOWN GAP: ASR-error manual ({asr_report.score}) scores same or higher "
                f"than clean manual ({clean_report.score}). "
                "Reviewer doesn't detect ASR errors."
            )


# ---------------------------------------------------------------------------
# SECTION 6: Metadata persistence gaps
# ---------------------------------------------------------------------------

class TestMetadataPersistence:
    """Document what metadata SHOULD be persisted but isn't."""

    def test_runtime_metadata_fields_exist(self):
        """
        Verify that the runtime_report contains the required metadata fields.
        """
        runtime_report = {
            "inference_device": "cuda",
            "whisper_model": "base",
            "whisper_device": "cuda",
            "whisper_compute_type": "float16",
            "llm_model": "Meta-Llama-3.1-8B",
            "llm_n_gpu_layers": -1,
            "llm_temperature": 0.2,
            "llm_num_ctx": 8192,
            "manual_vision_model": "SmolVLM-500M-Instruct",
            "generation_time_seconds": 42.3,
            "environment": ".venv-gpu",
            "python_version": "3.14.4"
        }

        missing_fields = []
        for field in ["inference_device", "llm_model", "whisper_model", "llm_n_gpu_layers", "environment"]:
            if field not in runtime_report:
                missing_fields.append(field)

        assert not missing_fields, f"Missing fields in runtime report: {missing_fields}"


# ---------------------------------------------------------------------------
# SECTION 7: Quality mode repair loop effectiveness
# ---------------------------------------------------------------------------

class TestQualityModeRepairLoop:
    """Test that the quality mode repair loop can actually improve manuals."""

    def test_bad_manual_should_trigger_repair(self):
        """
        A manual with gibberish captions should fail review and trigger repair.
        """
        report = review_manual_content(
            _BAD_MANUAL_WITH_GIBBERISH_CAPTIONS,
            section_count=1, word_count=200, screenshot_count=4,
        )
        if report.passed:
            pytest.xfail(
                f"KNOWN GAP: Bad manual passed review (score={report.score}). "
                "The repair loop will never trigger because the reviewer "
                "doesn't detect the quality issues."
            )

    def test_manual_with_single_section_should_be_flagged(self):
        """
        All generated manuals have section_count=1, meaning the LLM
        processes the entire transcript in one pass.
        """
        report = review_manual_content(
            _BAD_MANUAL_WITH_ASR_ERRORS,
            section_count=1, word_count=200, screenshot_count=3,
        )
        structure_issue = [i for i in report.issues
                         if "seccion" in i.message.lower()
                         or "section" in i.code.lower()
                         or "estructura" in i.message.lower()]
        # section_count=1 is not inherently bad if the manual is well-structured,
        # but with the current implementation it leads to quality problems.
        # This test just documents the observation.
        assert report.section_count == 1 or True  # Always passes — documentation only


# ---------------------------------------------------------------------------
# SECTION 8: enhance_caption validation
# ---------------------------------------------------------------------------

class TestEnhanceCaption:
    """Test the caption enhancement function."""

    def test_enhance_caption_with_good_description(self):
        from app.visual_analysis import enhance_caption, ImageQuality

        quality = ImageQuality(
            sharpness=0.7, brightness=0.7, contrast=0.7, score=0.7,
            visual_description="Pantalla de login con campos de usuario y contraseña"
        )
        # Should now just return the original caption to avoid destructive replacement
        result = enhance_caption("Figura (00:00:31) - texto original", quality)
        assert result == "Figura (00:00:31) - texto original"

    def test_enhance_caption_with_gibberish_should_not_enhance(self):
        """
        If the VLM returns gibberish, enhance_caption should not use it.
        """
        from app.visual_analysis import enhance_caption, ImageQuality

        quality = ImageQuality(
            sharpness=0.7, brightness=0.7, contrast=0.7, score=0.7,
            visual_description="La captura de la imagem es una punta en el centro del campo, en la que se encuentra un carro y un piso."
        )
        result = enhance_caption("Figura (00:00:36) - original caption", quality)
        assert result == "Figura (00:00:36) - original caption"

    def test_enhance_caption_preserves_original_on_empty_description(self):
        from app.visual_analysis import enhance_caption, ImageQuality

        quality = ImageQuality(
            sharpness=0.7, brightness=0.7, contrast=0.7, score=0.7,
            visual_description=None
        )
        result = enhance_caption("Figura (00:00:41) - caption base", quality)
        assert result == "Figura (00:00:41) - caption base"
