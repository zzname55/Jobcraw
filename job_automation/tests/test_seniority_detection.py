from matching.seniority_detection import detect_seniority


def test_detect_junior_russian():
    assert detect_seniority("младший инженер ИИ удаленно") == "junior"


def test_detect_working_student_german():
    assert detect_seniority("Werkstudent KI Automatisierung Homeoffice") == "working_student"
