from matching.remote_detection import detect_remote_type


def test_detect_remote_russian():
    assert detect_remote_type("младший инженер ИИ удаленно") == "remote"


def test_detect_hybrid():
    assert detect_remote_type("AI Solutions Engineer hybrid Berlin") == "hybrid"
