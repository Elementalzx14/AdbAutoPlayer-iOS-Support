"""Tablet recognition, inverse coordinates, and victory guards."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from adb_auto_player.device.ios.geometry import Canvas
from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.games.afk_journey import ios_layout
from adb_auto_player.games.afk_journey.base import AFKJourneyBase
from adb_auto_player.games.afk_journey.battle_state import Mode
from adb_auto_player.models.pydantic.adb_settings import AdbSettings

ASSETS = Path(ios_layout.__file__).parent / "ios_templates/ipad"
# Independently measured screen positions, rather than regions read from the
# matcher manifest. Build black test canvases: no device screenshots are needed.
POSITIONS = {
    "updated": [("world_modes.png", 420, 1669)],
    "battle-modes": [("afk_card.png", 150, 709), ("battle_modes_back.png", 47, 1613)],
    "stage-panel": [
        ("stage_battle.png", 773, 1420),
        ("stage_season.png", 126, 1423),
        ("back.png", 49, 1580),
    ],
    "formation-ready": [("records.png", 193, 1558), ("battle.png", 813, 1574)],
    "records": [("copy.png", 551, 1430), ("formation_next.png", 878, 976)],
    "formation": [("confirm.png", 761, 1310)],
    "result": [
        ("victory_rewards.png", 378, 1155),
        ("victory_progress.png", 171, 1221),
        ("victory_battle.png", 696, 1584),
    ],
    "season-result": [("retry.png", 697, 1599)],
    "dura-cleared": [
        ("dura_overview.png", 954, 464),
        ("dura_sweep.png", 550, 1436),
        ("dura_limit.png", 389, 991),
        ("light_back.png", 40, 1603),
    ],
    "legend-victory": [
        ("trial_rewards.png", 429, 1139),
        ("trial_victory.png", 151, 406),
        ("trial_next.png", 712, 1584),
    ],
    "legend-intro": [
        ("legend_intro.png", 48, 697),
        ("legend_intro_close.png", 464, 1638),
    ],
    "chat-district": [
        ("chat_placeholder.png", 283, 1451),
        ("chat_settings.png", 170, 1427),
        ("chat_world_tab.png", 272, 512),
    ],
}


def make_frame(screen):
    frame = np.zeros((1920, 1080, 3), np.uint8)
    for filename, x, y in POSITIONS[screen]:
        image = cv2.imread(str(ASSETS / filename))
        h, w = image.shape[:2]
        frame[y : y + h, x : x + w] = image
    return frame


CASES = [
    ("updated", "ios/world_modes.png"),
    ("battle-modes", "battle_modes/afk_stage.png"),
    ("battle-modes", "ios/battle_modes_back.png"),
    ("stage-panel", "afk_stages/season_battle.png"),
    ("stage-panel", "ios/stage_season.png"),
    ("stage-panel", "ios/back.png"),
    ("formation-ready", "battle/records.png"),
    ("formation-ready", "battle/battle.png"),
    ("records", "battle/copy.png"),
    ("records", "battle/formation_next.png"),
    ("formation", "navigation/confirm.png"),
    ("result", "next.png"),
    ("season-result", "retry.png"),
    ("dura-cleared", "duras_trials/socketed_charms_overview.png"),
    ("dura-cleared", "duras_trials/sweep.png"),
    ("dura-cleared", "ios/dura_limit.png"),
    ("dura-cleared", "ios/light_back.png"),
    ("legend-victory", "next.png"),
]


@pytest.fixture
def game():
    with patch.object(
        SettingsLoader, "adb_settings", return_value=AdbSettings(ios={"enabled": True})
    ):
        game = AFKJourneyBase()
        game._device = SimpleNamespace(
            metadata={"model": "iPad13,16", "viewport": (0, 183, 1080, 1554)}
        )
        game.__dict__["template_dir"] = Path(ios_layout.__file__).parent / "templates"
        yield game


@pytest.mark.parametrize("screen,name", CASES)
def test_tablet_controls_use_full_frame_and_correct_inverse_taps(game, screen, name):
    frame = make_frame(screen)
    match = game.game_find_template_match(name, screenshot=frame)
    assert match is not None
    filename = game.layout.matcher._ios_visuals[name][0]["file"]
    if screen == "legend-victory" and name == "next.png":
        filename = "trial_next.png"
    expected = next((x, y) for file, x, y in POSITIONS[screen] if file == filename)
    assert (match.box.top_left.x, match.box.top_left.y) == expected
    canvas = Canvas(1640, 2360, 1080, 1920)
    x, y = canvas.native_point(match.x, match.y)
    assert 0 <= x < 1640 and 0 <= y < 2360
    assert (
        game.game_find_template_match(name, screenshot=(frame * 0.45).astype(np.uint8))
        is None
    )


@pytest.mark.parametrize("screen", ["formation-ready", "stage-panel", "season-result"])
def test_tablet_next_never_matches_battle_buttons_or_defeat(game, screen):
    frame = make_frame(screen)
    assert game.game_find_template_match("next.png", screenshot=frame) is None


@pytest.mark.parametrize(
    "missing", ["ios/victory_rewards.png", "ios/victory_progress.png"]
)
def test_tablet_next_requires_both_victory_markers(game, missing):
    frame = make_frame("result")
    region = game.layout.matcher._ios_visuals[missing][0]["region"]
    x1, y1, x2, y2 = [
        round(v * (1080 if i % 2 == 0 else 1554) + (0 if i % 2 == 0 else 183))
        for i, v in enumerate(region)
    ]
    frame[y1:y2, x1:x2] = 0
    assert game.game_find_template_match("next.png", screenshot=frame) is None


def test_tablet_victory_uses_original_result_handler(game):
    game.battle_state.mode = Mode.AFK_STAGES
    game.get_screenshot = MagicMock(return_value=make_frame("result"))
    game.tap = MagicMock()
    game.sleep_navigation = MagicMock()
    assert game._is_battle_outcome_successful(1) is True
    game.tap.assert_called_once()
    assert game.tap.call_args.args[0].template == "next.png"


def test_blank_tablet_frame_does_not_match_trial_images(game):
    frame = np.zeros((1920, 1080, 3), np.uint8)
    assert "ios/trial_victory.png" in game.layout.matcher._ios_visuals
    assert (
        game.game_find_template_match("legend_trials/s_header.png", screenshot=frame)
        is None
    )


def test_profile_can_change_after_device_metadata_arrives(game):
    game._device.metadata = {}
    assert "ios/trial_victory.png" not in game.layout.matcher._ios_visuals
    game._device.metadata = {"model": "iPad13,16"}
    assert "ios/trial_victory.png" in game.layout.matcher._ios_visuals


@pytest.mark.parametrize("missing", ["trial_rewards.png", "trial_victory.png"])
def test_trial_next_requires_victory_and_rewards(game, missing):
    frame = make_frame("legend-victory")
    filename, x, y = next(
        item for item in POSITIONS["legend-victory"] if item[0] == missing
    )
    image = cv2.imread(str(ASSETS / filename))
    frame[y : y + image.shape[0], x : x + image.shape[1]] = 0
    assert game.game_find_template_match("next.png", screenshot=frame) is None


def test_extensionless_profile_names_keep_victory_guards_and_original_name(game):
    assert (
        game.game_find_template_match("next", screenshot=make_frame("formation-ready"))
        is None
    )
    result = game.game_find_template_match("next", screenshot=make_frame("result"))
    assert result is not None and result.template == "next"


def test_legend_intro_is_dismissed_only_when_both_controls_match(game):
    game.get_screenshot = MagicMock(return_value=make_frame("legend-intro"))
    game.tap, game.wait_for_template = MagicMock(), MagicMock()
    assert game.layout.finish_legend_entry(game) is True
    assert game.tap.call_args.args[0].template == "ios/legend_intro_close.png"
    game.tap.reset_mock()
    game.get_screenshot.return_value = make_frame("formation-ready")
    assert game.layout.finish_legend_entry(game) is False
    game.tap.assert_not_called()


def test_original_dura_cleared_state_stops_without_sweeping(game):
    from adb_auto_player.games.afk_journey.mixins.duras_trials import DurasTrialsMixin

    game.get_screenshot = MagicMock(return_value=make_frame("dura-cleared"))
    game.tap = MagicMock()
    game._handle_battle_screen = MagicMock()
    game._dura_resolve_state = lambda: DurasTrialsMixin._dura_resolve_state(game)
    DurasTrialsMixin._handle_dura_screen(game)
    game.tap.assert_not_called()
    game._handle_battle_screen.assert_not_called()


def test_chat_channel_switch_does_not_toggle_an_already_open_panel(game):
    game.get_screenshot = MagicMock(return_value=make_frame("chat-district"))
    game.tap = MagicMock()
    game.wait_for_any_template = MagicMock(
        return_value=SimpleNamespace(template="ios/chat_world_tab.png")
    )
    game.wait_for_template = MagicMock()
    game.layout.open_chat(game)
    game.tap.assert_called_once()
    assert game.tap.call_args.args[0].template == "ios/chat_world_tab.png"
    game.wait_for_template.assert_called_once_with(
        "chat/label_world_chat.png", timeout=game.navigation_timeout
    )


def test_chat_close_requires_input_placeholder_and_settings_marker(game):
    game.get_screenshot = MagicMock(return_value=make_frame("chat-district"))
    game.tap = MagicMock()
    game.press_back_button()
    game.tap.assert_called_once()
    assert (game.tap.call_args.args[0].x, game.tap.call_args.args[0].y) == (540, 100)


def test_dura_navigation_recognizes_existing_screen_without_input(game):
    game.get_screenshot = MagicMock(return_value=make_frame("dura-cleared"))
    game.tap = MagicMock()
    game.navigate_to_duras_trials_screen()
    game.tap.assert_not_called()


def test_tablet_hero_exclusion_searches_portrait_row_but_not_battle_board(game):
    folder = Path(ios_layout.__file__).parent / "templates/heroes"
    game._load_image = lambda name: cv2.imread(str(folder / Path(name).name))
    portrait = cv2.resize(game._load_image("heroes/mehira.png"), None, fx=0.95, fy=0.95)
    h, w = portrait.shape[:2]
    frame = np.zeros((1920, 1080, 3), np.uint8)
    frame[1220 : 1220 + h, 630 : 630 + w] = portrait
    assert game.game_find_template_match(
        "heroes/mehira.png", screenshot=frame, threshold=0.85
    )
    frame[:] = 0
    frame[800 : 800 + h, 630 : 630 + w] = portrait
    assert (
        game.game_find_template_match(
            "heroes/mehira.png", screenshot=frame, threshold=0.85
        )
        is None
    )
