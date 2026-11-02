"""Platform navigation and formation layout policies for AFK Journey."""

from adb_auto_player.image_manipulation import Cropping
from adb_auto_player.models.geometry import Box, Point, ReferencePoint
from adb_auto_player.models.image_manipulation import CropRegions, CropResult

from .battle_state import Mode
from .ios_layout import AppleTemplateMatcher
from .layout_types import NOT_HANDLED


class AndroidLayout:
    """Original Android navigation and battle controls."""

    formation_poll_seconds = 1.5

    def resolve_point(self, game, coordinates):
        return coordinates

    def resolve_box(self, game, box):
        return box

    def crop_reference(self, game, frame, regions):
        return Cropping.crop(frame, regions)

    def offset_point(self, game, origin, dx=0, dy=0):
        return Point(origin.x + dx, origin.y + dy)

    def match_template(self, *args, **kwargs):
        return NOT_HANDLED

    def match_all(self, *args, **kwargs):
        return NOT_HANDLED

    def worst_match(self, *args, **kwargs):
        return NOT_HANDLED

    def open_chat(self, game):
        game.device.press_enter()

    def prepare_overview(self, game):
        pass

    def press_back(self, game):
        game.device.press_back_button()

    def capture_debug(self, category):
        return NOT_HANDLED

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

    def finish_legend_entry(self, game):
        return False

    def select_afk_stage(self, game):
        return False


class AppleLayout(AndroidLayout):
    """Apple navigation uses verified controls rather than Android fixed points."""

    formation_poll_seconds = 0.5

    def __init__(self, game):
        self.matcher = AppleTemplateMatcher(game)

    def resolve_point(self, game, coordinates):
        if not isinstance(coordinates, ReferencePoint):
            return coordinates
        width, height = game.base_resolution.dimensions
        metadata = getattr(game.device, "metadata", {})
        left, top, w, h = metadata.get("viewport", (0, 0, width, height))
        return Point(
            left + round(min(coordinates.x, width - 1) * (w - 1) / (width - 1)),
            top + round(min(coordinates.y, height - 1) * (h - 1) / (height - 1)),
        )

    def match_template(self, *args, **kwargs):
        return self.matcher.match(*args, **kwargs)

    def offset_point(self, game, origin, dx=0, dy=0):
        width, height = game.base_resolution.dimensions
        _, _, w, h = getattr(game.device, "metadata", {}).get(
            "viewport", (0, 0, width, height)
        )
        return Point(
            origin.x + round(dx * w / width), origin.y + round(dy * h / height)
        )

    def resolve_box(self, game, box):
        if not isinstance(box.top_left, ReferencePoint):
            return box
        top_left = self.resolve_point(game, box.top_left)
        bottom_right = self.resolve_point(
            game,
            ReferencePoint(box.right, box.bottom),
        )
        return Box(top_left, bottom_right.x - top_left.x, bottom_right.y - top_left.y)

    def match_all(self, template, threshold, grayscale, crop_regions, min_distance):
        game = self.matcher.game
        frame = game.get_screenshot()
        return self.matcher.shared_templates.match_all(
            str(template),
            frame,
            self.matcher._ios_viewport(frame),
            crop_regions,
            threshold or game.default_threshold,
            grayscale,
            min_distance,
        )

    def crop_reference(self, game, frame, regions):
        vx, vy, width, height = self.matcher._ios_viewport(frame)
        reference_width, reference_height = game.base_resolution.dimensions
        values = {}
        for side in ("left", "right", "top", "bottom"):
            value = getattr(regions, side)
            scale = (
                width / reference_width
                if side in ("left", "right")
                else height / reference_height
            )
            values[side] = (
                round(value.value * scale) if value.is_pixels else value.value
            )
        cropped = Cropping.crop(
            frame[vy : vy + height, vx : vx + width], CropRegions(**values)
        )
        return CropResult(
            cropped.image, Point(vx + cropped.offset.x, vy + cropped.offset.y)
        )

    def worst_match(self, template, grayscale, crop_regions):
        game = self.matcher.game
        frame = game.get_screenshot()
        return self.matcher.shared_templates.worst(
            str(template),
            frame,
            self.matcher._ios_viewport(frame),
            crop_regions,
            grayscale,
        )

    def open_chat(self, game):
        frame = game.get_screenshot()
        if self.matcher._ios_match("ios/chat_panel.png", frame) is None:
            game.tap(
                game.wait_for_template(
                    "ios/chat_open.png", timeout=game.navigation_timeout
                )
            )
        world = "chat/label_world_chat.png"
        state = game.wait_for_any_template(
            [world, "ios/chat_world_tab.png", "ios/chat_channel.png"],
            timeout=game.navigation_timeout,
        )
        if state.template == world:
            return
        game.tap(state)
        if state.template == "ios/chat_channel.png":
            state = game.wait_for_any_template(
                [world, "ios/chat_world_tab.png"],
                timeout=game.navigation_timeout,
            )
            if state.template != world:
                game.tap(state)
        game.wait_for_template(world, timeout=game.navigation_timeout)

    def press_back(self, game):
        self.matcher.press_back()

    def prepare_overview(self, game):
        if self.matcher._ios_match("ios/chat_panel.png", game.get_screenshot()):
            self.matcher.press_back()
            game.sleep_navigation()

    def capture_debug(self, category):
        self.matcher.capture_debug(category)

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

    def finish_legend_entry(self, game):
        frame = game.get_screenshot()
        intro = self.matcher._ios_match("ios/legend_intro.png", frame)
        close = self.matcher._ios_match("ios/legend_intro_close.png", frame)
        if intro is None or close is None:
            return False
        game.tap(close)
        game.wait_for_template(
            "legend_trials/s_header.png", timeout=game.navigation_timeout
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
        game._click_confirm_on_popup()
        return True
