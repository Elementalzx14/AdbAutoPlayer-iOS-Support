"""Platform navigation and formation layout policies for AFK Journey."""

from adb_auto_player.models.geometry import Point
from adb_auto_player.models.image_manipulation import CropRegions
from .battle_state import Mode


class AndroidLayout:
    """Original Android navigation and battle controls."""

    formation_poll_seconds = 1.5

    def battle_ready(self, game):
        return game.wait_for_any_template(
            templates=[
                "battle/records.png",
                "battle/formations_icon.png",
                "battle/battle.png",
            ],
            crop_regions=CropRegions(top=0.5),
            timeout=10,
        )

    def battle_point(self, result):
        return Point(x=850, y=1780)

    def battle_modes_point(self, game):
        return game.BATTLE_MODES_POINT

    def at_battle_modes(self, game):
        return False

    def finish_afk_entry(self, game):
        return False

    def select_afk_stage(self, game):
        return False


class AppleLayout(AndroidLayout):
    """Apple navigation uses verified controls rather than Android fixed points."""

    formation_poll_seconds = 0.5

    def battle_ready(self, game):
        return game.wait_for_template("battle/battle.png", timeout=10)

    def battle_point(self, result):
        return result

    def battle_modes_point(self, game):
        return game.wait_for_template(
            "ios/world_modes.png", timeout=game.navigation_timeout
        )

    def at_battle_modes(self, game):
        return game.game_find_template_match("battle_modes/afk_stage.png") is not None

    def finish_afk_entry(self, game):
        game.wait_for_template(
            "afk_stages/season_battle.png", timeout=game.navigation_timeout
        )
        return True

    def select_afk_stage(self, game):
        template = (
            "ios/stage_season.png"
            if game.battle_state.mode == Mode.SEASON_AFK_STAGES
            else "afk_stages/season_battle.png"
        )
        game.tap(game.wait_for_template(template, timeout=game.min_timeout))
        game.sleep_navigation()
        return True
