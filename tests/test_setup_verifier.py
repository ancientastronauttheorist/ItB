from PIL import Image, ImageDraw

from src.strategy import setup_verifier
from src.strategy.setup_verifier import analyze_setup_image


def _blank_setup() -> Image.Image:
    return Image.new("RGB", (1280, 748), (12, 16, 24))


def _paint_icon(img: Image.Image, box, color):
    draw = ImageDraw.Draw(img)
    draw.rectangle(box, fill=color)


def _paint_difficulty_border(img: Image.Image, box):
    draw = ImageDraw.Draw(img)
    for inset in range(4):
        x0, y0, x1, y1 = box
        draw.rectangle(
            (x0 + inset, y0 + inset, x1 - inset, y1 - inset),
            outline=(235, 207, 114),
        )


def _paint_checkbox(img: Image.Image, center, checked: bool):
    draw = ImageDraw.Draw(img)
    cx, cy = center
    box = (cx - 18, cy - 18, cx + 18, cy + 18)
    draw.rectangle(box, fill=(12, 16, 24), outline=(235, 235, 245), width=2)
    if checked:
        draw.rectangle((cx - 12, cy - 12, cx + 12, cy + 12), fill=(235, 235, 245))


def _paint_dim_checked_checkbox(img: Image.Image, center):
    draw = ImageDraw.Draw(img)
    cx, cy = center
    draw.rectangle((cx - 4, cy - 4, cx + 4, cy + 4), fill=(190, 190, 200))


def test_setup_verifier_passes_when_all_advanced_and_easy_selected():
    img = _blank_setup()
    for box, color in [
        ((558, 274, 616, 344), (84, 184, 92)),
        ((558, 350, 616, 418), (78, 118, 210)),
        ((558, 426, 616, 493), (210, 125, 72)),
        ((558, 503, 616, 570), (62, 198, 212)),
    ]:
        _paint_icon(img, box, color)
    for center in [(646, 304), (646, 379), (646, 454), (646, 529)]:
        _paint_checkbox(img, center, checked=True)
    _paint_difficulty_border(img, (909, 250, 1122, 317))

    check = analyze_setup_image(img, expected_difficulty=0)

    assert check.status == "PASS"
    assert check.setup_screen_detected is True
    assert check.actual_difficulty == 0
    assert check.missing_advanced == []
    assert check.click_plan == []


def test_setup_verifier_accepts_dim_checked_enemy_units_when_icon_is_colored():
    img = _blank_setup()
    for box, color in [
        ((558, 274, 616, 344), (84, 184, 92)),
        ((558, 350, 616, 418), (78, 118, 210)),
        ((558, 426, 616, 493), (210, 125, 72)),
        ((558, 503, 616, 570), (62, 198, 212)),
    ]:
        _paint_icon(img, box, color)
    _paint_dim_checked_checkbox(img, (646, 304))
    for center in [(646, 379), (646, 454), (646, 529)]:
        _paint_checkbox(img, center, checked=True)
    _paint_difficulty_border(img, (909, 250, 1122, 317))

    check = analyze_setup_image(img, expected_difficulty=0)

    assert check.status == "PASS"
    assert check.advanced[0]["enabled"] is True
    assert check.advanced[0]["checkbox_present"] is False
    assert check.missing_advanced == []
    assert check.click_plan == []


def test_setup_verifier_reports_missing_advanced_and_difficulty_clicks():
    img = _blank_setup()
    _paint_icon(img, (558, 274, 616, 344), (84, 184, 92))
    _paint_icon(img, (558, 350, 616, 418), (120, 120, 120))
    _paint_icon(img, (558, 426, 616, 493), (120, 120, 120))
    _paint_icon(img, (558, 503, 616, 570), (62, 198, 212))
    _paint_checkbox(img, (646, 304), checked=True)
    _paint_checkbox(img, (646, 379), checked=False)
    _paint_checkbox(img, (646, 454), checked=False)
    _paint_checkbox(img, (646, 529), checked=True)
    _paint_difficulty_border(img, (909, 326, 1122, 391))

    check = analyze_setup_image(img, expected_difficulty=0)

    assert check.status == "FAIL"
    assert check.setup_screen_detected is True
    assert check.actual_difficulty == 1
    assert check.missing_advanced == ["Missions", "Equipment"]
    assert [c["description"] for c in check.click_plan] == [
        "Enable Advanced Content: Missions",
        "Enable Advanced Content: Equipment",
        "Select difficulty: Easy",
    ]


def test_setup_verifier_passes_when_advanced_content_off():
    img = _blank_setup()
    for box in [
        (558, 274, 616, 344),
        (558, 350, 616, 418),
        (558, 426, 616, 493),
        (558, 503, 616, 570),
    ]:
        _paint_icon(img, box, (120, 120, 120))
    for center in [(646, 304), (646, 379), (646, 454), (646, 529)]:
        _paint_checkbox(img, center, checked=False)
    _paint_difficulty_border(img, (909, 250, 1122, 317))

    check = analyze_setup_image(img, expected_difficulty=0, advanced_content="off")

    assert check.status == "PASS"
    assert check.desired_advanced == "off"
    assert check.unexpected_advanced == []
    assert check.click_plan == []


def test_setup_verifier_fails_without_window_focus_proof():
    img = _blank_setup()
    for box in [
        (558, 274, 616, 344),
        (558, 350, 616, 418),
        (558, 426, 616, 493),
        (558, 503, 616, 570),
    ]:
        _paint_icon(img, box, (120, 120, 120))
    for center in [(646, 304), (646, 379), (646, 454), (646, 529)]:
        _paint_checkbox(img, center, checked=False)
    _paint_difficulty_border(img, (909, 250, 1122, 317))

    check = analyze_setup_image(
        img,
        expected_difficulty=0,
        advanced_content="off",
        window_focus_verified=False,
    )

    assert check.status == "FAIL"
    assert check.setup_screen_detected is True
    assert check.window_focus_verified is False
    assert check.to_dict()["window_focus_verified"] is False
    assert check.click_plan == []


def test_capture_setup_uses_verified_bounds_for_screenshot(monkeypatch, tmp_path):
    bounds = {"x": 10, "y": 20, "width": 1280, "height": 748}
    screenshot_bounds = []

    def fake_screenshot(output_path, *, bounds=None):
        screenshot_bounds.append(bounds)
        img = _blank_setup()
        for box in [
            (558, 274, 616, 344),
            (558, 350, 616, 418),
            (558, 426, 616, 493),
            (558, 503, 616, 570),
        ]:
            _paint_icon(img, box, (120, 120, 120))
        for center in [(646, 304), (646, 379), (646, 454), (646, 529)]:
            _paint_checkbox(img, center, checked=False)
        _paint_difficulty_border(img, (909, 250, 1122, 317))
        img.save(output_path)
        return output_path

    monkeypatch.setattr(setup_verifier, "get_window_bounds", lambda: bounds)
    monkeypatch.setattr(setup_verifier, "is_game_frontmost", lambda: True)
    monkeypatch.setattr(setup_verifier, "take_screenshot", fake_screenshot)

    check = setup_verifier.capture_and_check_setup(
        expected_difficulty=0,
        advanced_content="off",
        output_path=tmp_path / "setup.png",
    )

    assert check.status == "PASS"
    assert check.window_focus_verified is True
    assert check.window_bounds == bounds
    assert screenshot_bounds == [bounds]


def test_capture_setup_fails_when_game_window_is_not_frontmost(monkeypatch, tmp_path):
    bounds = {"x": 10, "y": 20, "width": 1280, "height": 748}

    def fake_screenshot(output_path, *, bounds=None):
        img = _blank_setup()
        for box in [
            (558, 274, 616, 344),
            (558, 350, 616, 418),
            (558, 426, 616, 493),
            (558, 503, 616, 570),
        ]:
            _paint_icon(img, box, (120, 120, 120))
        for center in [(646, 304), (646, 379), (646, 454), (646, 529)]:
            _paint_checkbox(img, center, checked=False)
        _paint_difficulty_border(img, (909, 250, 1122, 317))
        img.save(output_path)
        return output_path

    monkeypatch.setattr(setup_verifier, "get_window_bounds", lambda: bounds)
    monkeypatch.setattr(setup_verifier, "is_game_frontmost", lambda: False)
    monkeypatch.setattr(setup_verifier, "take_screenshot", fake_screenshot)

    check = setup_verifier.capture_and_check_setup(
        expected_difficulty=0,
        advanced_content="off",
        output_path=tmp_path / "setup.png",
    )

    assert check.status == "FAIL"
    assert check.setup_screen_detected is True
    assert check.window_focus_verified is False
    assert check.window_bounds == bounds
    assert check.click_plan == []


def test_setup_verifier_fails_colorful_squad_screen_false_positive():
    img = _blank_setup()
    for box, color in [
        ((558, 274, 616, 344), (84, 184, 92)),
        ((558, 350, 616, 418), (78, 118, 210)),
        ((558, 426, 616, 493), (210, 125, 72)),
        ((558, 503, 616, 570), (62, 198, 212)),
    ]:
        _paint_icon(img, box, color)
    _paint_difficulty_border(img, (909, 250, 1122, 317))

    check = analyze_setup_image(img, expected_difficulty=0)

    assert check.status == "FAIL"
    assert check.setup_screen_detected is False
    assert check.actual_difficulty is None
    assert check.click_plan == []
