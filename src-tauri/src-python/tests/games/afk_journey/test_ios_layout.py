"""Exercise the original task policy with iOS visual equivalents."""

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import cv2
import pytest
from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.games.afk_journey.base import AFKJourneyBase
from adb_auto_player.games.afk_journey.battle_state import Mode
from adb_auto_player.models.image_manipulation import CropRegions
from adb_auto_player.models.pydantic.adb_settings import AdbSettings

DATA = Path(__file__).with_name("data") / "ios"
CASES = {
    "afk-world-new": "ios/world_modes.png",
    "afk-battle-modes": "battle_modes/afk_stage.png",
    "afk-stage-panel": "afk_stages/season_battle.png",
    "afk-copied": "battle/records.png",
    "afk-records-owned": "battle/copy.png",
    "afk-suggested-result": "retry.png",
    "afk-live-check": "next.png",
}


@pytest.fixture
def game():
    with patch.object(
        SettingsLoader, "adb_settings", return_value=AdbSettings(ios={"enabled": True})
    ):
        yield AFKJourneyBase()


@pytest.mark.parametrize("screen,template", CASES.items())
def test_original_template_names_recognize_iphone_controls(game, screen, template):
    frame = cv2.imread(str(DATA / (screen + ".png")))
    result = game.find_any_template(
        [template], screenshot=frame, crop_regions=CropRegions(top=0.7)
    )
    assert result is not None and result.template == template
    assert 0 <= result.x < 1080 and 0 <= result.y < 1920
    # Popup dimming must not be mistaken for an actionable control underneath.
    assert (
        game.game_find_template_match(
            template, screenshot=(frame * 0.45).astype("uint8")
        )
        is None
    )


@pytest.mark.parametrize("screen", CASES)
def test_next_requires_victory_not_just_a_green_battle_button(game, screen):
    frame = cv2.imread(str(DATA / (screen + ".png")))
    result = game.game_find_template_match("next.png", screenshot=frame)
    assert (result is not None) == (screen == "afk-live-check")


def test_saved_attempts_and_formations_drive_original_engine(game):
    from adb_auto_player.games.afk_journey.settings import Settings

    settings = Settings()
    settings.afk_stages.attempts = 3
    settings.afk_stages.formations = 2
    settings.afk_stages.run_manual_formations_last = False
    settings.afk_stages.use_current_formation_before_suggested_formation = False
    game.battle_state.mode = Mode.AFK_STAGES
    game._copy_suggested_formation = MagicMock(return_value=True)
    game._start_battle = MagicMock(return_value=True)
    game._is_battle_outcome_successful = MagicMock(return_value=False)
    with patch.object(
        AFKJourneyBase, "settings", new_callable=PropertyMock, return_value=settings
    ):
        assert not game._handle_battle_screen(True)
    assert game._start_battle.call_count == 6
    assert game._copy_suggested_formation.call_count == 2
    assert [c.args[0] for c in game._is_battle_outcome_successful.call_args_list] == [
        1,
        2,
        3,
        1,
        2,
        3,
    ]


def test_current_formation_does_not_copy_suggestions(game):
    from adb_auto_player.games.afk_journey.settings import Settings

    settings = Settings()
    game.battle_state.mode = Mode.AFK_STAGES
    game._copy_suggested_formation = MagicMock()
    game._handle_single_stage = MagicMock(return_value=True)
    with patch.object(
        AFKJourneyBase, "settings", new_callable=PropertyMock, return_value=settings
    ):
        assert game._handle_battle_screen(False)
    game._copy_suggested_formation.assert_not_called()


def test_ios_start_uses_one_ready_button_capture_and_keeps_popup_checks(game):
    frame = cv2.imread(str(DATA / "afk-copied.png"))
    game.get_screenshot = MagicMock(return_value=frame)
    game._get_settings_for_mode = MagicMock(return_value=False)
    game.tap = MagicMock()
    game._tap_coordinates_till_template_disappears = MagicMock()
    game.sleep_action = MagicMock()
    game.find_any_template = MagicMock(return_value=None)
    game._click_confirm_on_popup = MagicMock(return_value=False)
    assert game._start_battle() is True
    game.get_screenshot.assert_called_once()
    assert game.tap.call_args.args[0].template == "battle/battle.png"
    game._tap_coordinates_till_template_disappears.assert_called_once()
    game.find_any_template.assert_called_once_with(
        ["battle/spend.png", "battle/gold.png"]
    )
    game._click_confirm_on_popup.assert_called_once()


def test_ios_start_does_not_tap_when_button_never_becomes_ready(game):
    from adb_auto_player.exceptions import GameTimeoutError

    game._get_settings_for_mode = MagicMock(return_value=False)
    game.wait_for_template = MagicMock(side_effect=GameTimeoutError("not ready"))
    game.tap = MagicMock()
    with pytest.raises(GameTimeoutError):
        game._start_battle()
    game.tap.assert_not_called()


def test_faster_copy_still_rejects_locked_formation(game):
    game._tap_till_template_disappears = MagicMock()
    cancel = MagicMock()
    game.game_find_template_match = MagicMock(return_value=cancel)
    game.tap = MagicMock()
    game._click_confirm_on_popup = MagicMock()
    assert game._apply_current_formation() is False
    game.tap.assert_called_once_with(cancel)
    game._click_confirm_on_popup.assert_not_called()


def test_trial_victory_has_its_own_next_control(game):
    frame = cv2.imread(str(DATA / "legend-victory.png"))
    assert game.find_any_template(["next.png"], screenshot=frame).template == "next.png"


def test_season_victory_advances_using_original_battle_handler(game):
    frame = cv2.imread(str(DATA / "season-victory.png"))
    game.battle_state.mode = Mode.SEASON_AFK_STAGES
    game.get_screenshot = MagicMock(return_value=frame)
    game.tap = MagicMock()
    game.sleep_navigation = MagicMock()
    assert game._is_battle_outcome_successful(1) is True
    game.tap.assert_called_once()
    target = game.tap.call_args.args[0]
    assert target.template == "next.png"
    assert 560 <= target.x <= 1002 and 1725 <= target.y <= 1780


@pytest.mark.parametrize(
    "missing", ["ios/victory_rewards.png", "ios/victory_progress.png"]
)
def test_season_next_requires_both_victory_markers(game, missing):
    frame = cv2.imread(str(DATA / "season-victory.png"))
    game.battle_state.mode = Mode.SEASON_AFK_STAGES
    x1, y1, x2, y2 = [
        round(v * (1080 if i % 2 == 0 else 1920))
        for i, v in enumerate(game._ios_visuals[missing][0]["region"])
    ]
    frame[y1:y2, x1:x2] = 0
    assert game.game_find_template_match("next.png", screenshot=frame) is None


def test_season_next_rejects_dimmed_and_wrong_mode_screens(game):
    frame = cv2.imread(str(DATA / "season-victory.png"))
    game.battle_state.mode = Mode.SEASON_AFK_STAGES
    assert (
        game.game_find_template_match(
            "next.png", screenshot=(frame * 0.45).astype("uint8")
        )
        is None
    )
    game.battle_state.mode = Mode.AFK_STAGES
    assert game.game_find_template_match("next.png", screenshot=frame) is None


def test_dura_complete_and_legend_unavailable_states(game):
    frame = cv2.imread(str(DATA / "dura-complete.png"))
    assert game.game_find_template_match("duras_trials/sweep.png", screenshot=frame)
    frame = cv2.imread(str(DATA / "legend-selection.png"))
    assert game.game_find_template_match("legend_trials/s_header.png", screenshot=frame)
    for faction in ["wilder", "graveborn", "mauler"]:
        assert game.game_find_template_match(
            f"legend_trials/faction_icon_{faction}.png", screenshot=frame
        )
    assert (
        game.game_find_template_match(
            "legend_trials/faction_icon_lightbearer.png", screenshot=frame
        )
        is None
    )


def test_manual_label_on_an_unselected_record_is_ignored(game):
    frame = cv2.imread(str(DATA / "afk-records-owned.png"))
    assert (
        game.game_find_template_match("battle/manual_battle.png", screenshot=frame)
        is None
    )
    # Move the observed label into the active tab to exercise the positive case.
    _, marker = game._ios_visuals["battle/manual_battle.png"]
    h, w = marker.shape[:2]
    frame[489 : 489 + h, 185 : 185 + w] = marker
    assert game.game_find_template_match("battle/manual_battle.png", screenshot=frame)


def test_hero_exclusion_uses_iphone_portrait_row(game):
    from adb_auto_player.models import ConfidenceValue

    game.template_dir = (
        Path(__file__).parents[3] / "adb_auto_player/games/afk_journey/templates"
    )
    from adb_auto_player.device.ios.geometry import Canvas

    canvas = Canvas(1320, 2868, 1080, 1920)
    game.device.metadata = {"viewport": canvas.viewport}
    frame = canvas.render(
        cv2.resize(cv2.imread(str(DATA / "legend-records.png")), (1320, 2868))
    )
    assert game.game_find_template_match(
        "heroes/evie.png", threshold=ConfidenceValue("85%"), screenshot=frame
    )
    assert (
        game.game_find_template_match(
            "heroes/ludovic.png", threshold=ConfidenceValue("85%"), screenshot=frame
        )
        is None
    )


@pytest.mark.parametrize("screen,template", CASES.items())
def test_uniform_canvas_recognizes_existing_controls(game, screen, template):
    from adb_auto_player.device.ios.geometry import Canvas

    frame = cv2.imread(str(DATA / (screen + ".png")))
    canvas = Canvas(1320, 2868, 1080, 1920)
    # Fixtures were archived on the old stretched canvas. Reconstruct its
    # native aspect ratio to exercise the new letterbox transform.
    native = cv2.resize(frame, (1320, 2868))
    game.device.metadata = {"viewport": canvas.viewport}
    result = game.game_find_template_match(template, screenshot=canvas.render(native))
    assert result is not None
    canvas.native_point(result.x, result.y)
