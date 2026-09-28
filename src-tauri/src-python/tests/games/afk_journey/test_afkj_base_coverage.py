from unittest.mock import MagicMock, PropertyMock, patch

from adb_auto_player.exceptions import GameActionFailedError, GameTimeoutError
from adb_auto_player.games.afk_journey.base import AFKJourneyBase
from adb_auto_player.models import ConfidenceValue
from adb_auto_player.models.geometry import Box, Point
from adb_auto_player.models.template_matching.template_match_result import (
    TemplateMatchResult,
)


class TestAFKJourneyBaseCoverage:
    def test_start_battle_failure_coverage(self):
        """Test _start_battle failure path to cover GameActionFailedError block."""
        # Create a minimal instance of AFKJourneyBase without calling __init__
        # to avoid setup overhead
        bot = AFKJourneyBase.__new__(AFKJourneyBase)
        bot._get_settings_for_mode = MagicMock(return_value="No")
        bot.tap = MagicMock()

        # Mock wait_for_any_template to return a valid result
        match_result = TemplateMatchResult(
            template="battle/records.png",
            confidence=ConfidenceValue(1.0),
            box=Box(top_left=Point(100, 100), width=50, height=50),
        )
        bot.wait_for_any_template = MagicMock(return_value=match_result)

        # Mock _tap_coordinates_till_template_disappears to raise GameActionFailedError
        with (
            patch.object(
                bot,
                "_tap_coordinates_till_template_disappears",
                side_effect=GameActionFailedError("test"),
            ),
            patch.object(
                AFKJourneyBase,
                "using_ios",
                new_callable=PropertyMock,
                return_value=False,
            ),
        ):
            # The method should return False when GameActionFailedError is caught
            assert bot._start_battle() is False

    def test_find_any_excluded_hero(self):
        """Test _find_any_excluded_hero success path."""
        bot = AFKJourneyBase.__new__(AFKJourneyBase)

        match_result = TemplateMatchResult(
            template="heroes/evie.png",
            confidence=ConfidenceValue(1.0),
            box=Box(Point(0, 0), 10, 10),
        )
        bot.wait_for_any_template = MagicMock(return_value=match_result)

        excluded = {"heroes/evie.png": "Evie"}
        result = bot._find_any_excluded_hero(excluded)
        assert result == "Evie"

    def test_find_any_excluded_hero_timeout(self):
        """Test _find_any_excluded_hero timeout path."""
        bot = AFKJourneyBase.__new__(AFKJourneyBase)
        bot.wait_for_any_template = MagicMock(side_effect=GameTimeoutError("timeout"))

        excluded = {"heroes/evie.png": "Evie"}
        result = bot._find_any_excluded_hero(excluded)
        assert result is None
