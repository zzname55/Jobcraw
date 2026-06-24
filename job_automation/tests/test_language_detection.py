from matching.language_detection import detect_language


def test_detect_russian():
    assert detect_language("младший инженер ИИ удаленно") == "ru"


def test_detect_german():
    assert detect_language("Werkstudent KI Automatisierung Homeoffice") == "de"


def test_detect_english():
    assert detect_language("Junior AI Automation Engineer Remote") == "en"
