from app.language_detection import detect_language_from_texts, resolve_transcript_language


def test_detect_language_from_spanish_training_words():
    language = detect_language_from_texts(
        [
            "Primero vamos a revisar la pantalla de configuracion.",
            "Luego selecciona la opcion para ingresar con usuario y contrasena.",
        ]
    )

    assert language == "es"


def test_detect_language_from_english_training_words():
    language = detect_language_from_texts(
        [
            "First we review the configuration screen.",
            "Then select the option to enter the user password.",
        ]
    )

    assert language == "en"


def test_resolve_language_returns_undetermined_when_text_is_not_enough():
    language = resolve_transcript_language(None, ["OK"])

    assert language == "und"
