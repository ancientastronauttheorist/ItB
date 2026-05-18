from PIL import Image, ImageDraw

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


def test_setup_verifier_passes_when_all_advanced_and_easy_selected():
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

    assert check.status == "PASS"
    assert check.actual_difficulty == 0
    assert check.missing_advanced == []
    assert check.click_plan == []


def test_setup_verifier_reports_missing_advanced_and_difficulty_clicks():
    img = _blank_setup()
    _paint_icon(img, (558, 274, 616, 344), (84, 184, 92))
    _paint_icon(img, (558, 350, 616, 418), (120, 120, 120))
    _paint_icon(img, (558, 426, 616, 493), (120, 120, 120))
    _paint_icon(img, (558, 503, 616, 570), (62, 198, 212))
    _paint_difficulty_border(img, (909, 326, 1122, 391))

    check = analyze_setup_image(img, expected_difficulty=0)

    assert check.status == "FAIL"
    assert check.actual_difficulty == 1
    assert check.missing_advanced == ["Missions", "Equipment"]
    assert [c["description"] for c in check.click_plan] == [
        "Enable Advanced Content: Missions",
        "Enable Advanced Content: Equipment",
        "Select difficulty: Easy",
    ]
