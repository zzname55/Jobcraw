from matching.compensation import analyze_compensation_and_hours


def test_salary_and_hours_targets_met():
    result = analyze_compensation_and_hours("50.000 EUR Jahr, 36 Stunden pro Woche")
    assert result["salary_target_met"] == "yes"
    assert result["hours_target_met"] == "yes"


def test_unknown_salary_and_hours():
    result = analyze_compensation_and_hours("Junior AI Automation Specialist remote")
    assert result["salary_found"] == "unknown"
    assert result["hours_found"] == "unknown"
