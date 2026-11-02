import logging
from time import sleep

from adb_auto_player.decorators import (
    register_custom_routine_choice,
)
from adb_auto_player.models.geometry import ReferencePoint

from ..base import AFKJourneyBase


class ClaimAFKRewards(AFKJourneyBase):
    @register_custom_routine_choice("Claim AFK Rewards")
    def _claiming_afk_progress_chest(self) -> None:
        self.start_up()
        logging.info("Claiming AFK Rewards.")
        self.navigate_to_afk_stages_screen()

        logging.info("Tapping AFK Rewards chest.")
        for _ in range(3):
            self.tap(ReferencePoint(x=520, y=1400), log=False)
            self.tap(ReferencePoint(x=550, y=1080), log=False)
            sleep(1)
        sleep(1)
        # Make sure the Popup doesn't block collecting AFK Rewards
        self.tap(ReferencePoint(x=550, y=1080), log=False)
        if self.settings.claim_afk_rewards.claim_stage_rewards:
            for _ in range(5):
                self.tap(ReferencePoint(x=770, y=500), log=False)
                self.tap(ReferencePoint(x=770, y=500), log=False)
                sleep(1)
            if cancel := self.game_find_template_match("cancel.png"):
                self.tap(cancel)
        logging.info("AFK Rewards claimed.")
