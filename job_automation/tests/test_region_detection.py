from matching.region_detection import detect_region


def test_detect_dach():
    region, country = detect_region("Junior AI Automation Engineer Berlin Germany")
    assert region == "dach"
    assert country == "germany"


def test_detect_europe_remote():
    region, _ = detect_region("Remote Europe Applied AI Engineer")
    assert region == "europe"
