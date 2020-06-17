from time import sleep

from core.preferences import preferences_mgr

from .base import (BattleError, BattleExecutorBase, BattlePointType,
                   BattleResult, EventInfoBase)
from .utils import (add_passcards, check_and_get_sally_data, check_passcards,
                    decrypte_battle_msg, get_alive_member_count)

battle_config = preferences_mgr.get("battle")


class ConsecutiveTeamEventInfo(EventInfoBase):
    def __init__(self, api):
        super().__init__("連對戰！")
        self.api = api
        self.rest_passcard = 0
        self.rest_passcard_max = 3

    def check_passcard(self):
        return self.rest_passcard != 0

    @classmethod
    def create(cls, api):
        data = check_and_get_sally_data(api)
        if data is None:
            return None

        event = data.get("event")
        if event is None:
            print("無活動！")
            return None

        money = data.get("currency").get("money")
        print(f"持有小判：{money}")

        point = list(data.get("point").values())[0]
        print(f"持有御歲魂：{point}")

        event_info = cls(api)
        event_info.money = data.get("currency").get("money")
        event_info.event_id = event.get("event_id")
        # fields = list(event["field"].values())
        # event_info.field_id = fields[len(fields) - 1]["field_id"]

        special_field_id = int(event.get("allout", {}).get("mode_change_field_id", 0))
        event_info.field_id = special_field_id if special_field_id != 0 else 4

        if special_field_id != 0:
            print(f"特殊活動地圖！id: {special_field_id}")

        event_info.rest_passcard = event.get("cost").get("rest")
        event_info.rest_passcard_max = event.get("cost").get("max")
        print(f"手形剩餘：{event_info.rest_passcard}/{event_info.rest_passcard_max}")
        return event_info


class ConsecutiveTeamExecutor(BattleExecutorBase):
    def __init__(self, api, team, *args, **kwargs):
        super().__init__(api, team, *args, **kwargs)
        self.event_info = ConsecutiveTeamEventInfo.create(api)
        self.event_id = self.event_info.event_id
        self.field = self.event_info.field_id
        self._cur_team_id = self.team_id

    def prepare(self):
        print(f"活動 {self.event_info.name} 準備")

        if not check_passcards(self.event_info):
            if not add_passcards(
                self.api, self.event_id, self.event_info.rest_passcard_max
            ):
                return False

        ret = self.api.event_battle_start(
            self.event_id, self._cur_team_id, self.field, event_layer_id=1
        )

        if not ret["status"]:
            print("使用手形 1 個")
            self.team_ref.battle_init()
            return True
        else:
            print(
                f"EventID = {self.event_id}, FIELD = {self.field_id}, LAYER = {self.layer_id}"
            )
            raise BattleError("初始化活動戰鬥")

    def foward(self):
        ret = self.api.event_get_party_info()
        if ret["status"]:
            raise BattleError("活動前進")

        return BattlePointType.BATTLE

    def _check_reward(self, data):
        if data is None:
            return None

        got_points = data.get("get_point", 0)
        print(f"獲得御歲魂： {got_points} 枚")

        settle_up = data.get("settle_up", {})

        if len(settle_up) == 0:
            return

        takeout = settle_up.get("takeout", None)

        if not takeout:
            return

        bonus = takeout.get("point", -1)

        if bonus < 0:
            print("御歲魂數目異常！")
        else:
            print(f"總共獲得御歲魂 {bonus} 枚")

    def battle(self, party):
        ret = self.api.alloutbattle(party)

        if ret["status"]:
            raise BattleError("活動戰鬥主函數")

        return decrypte_battle_msg(ret["data"], ret["iv"])

    def handle_battle_point(self, party):
        ret = self.battle(party)
        self.update_after_battle(ret)

    def update_after_battle(self, data):
        super().update_after_battle(data)

        self._check_reward(data.get("allout", None))

        # 檢查敗北
        self.finished = data["finish"]["is_finish"]

    def back_to_home(self):
        self.team_ref.battle_end()

        # 隊長受重傷直接回家，不需要呼叫 event return
        if not self.team_ref.member_status_normal(0):
            print("隊長重傷，返回本丸！")
            return None

        if self.status == BattleResult.TEAM_STATUS_BAD:
            print("隊伍狀況不佳，返回本丸！")
            self.api.event_return()
            return

        self.api.home()

    def play(self):
        try:
            if not self.prepare():
                return None

            # 第一次進入地圖，必定進入戰鬥
            self.handle_battle_point(self._cur_team_id)

            while True:
                if not self.team_ref.can_foward_in_battle():
                    self.status = BattleResult.TEAM_STATUS_BAD
                    break

                alive = get_alive_member_count(self.team_ref.sword_refs)

                if alive < battle_config.get("event_min_alive"):
                    self.status = BattleResult.TEAM_STATUS_BAD
                    break

                point_type = self.foward()

                if point_type == BattlePointType.BATTLE:
                    self.handle_battle_point(self._cur_team_id)
                else:
                    break

                if self.finished or self.status is not BattleResult.NORMAL:
                    break

                sleep(battle_config.get("battle_internal_delay"))

            self.team_ref.show()
            self.back_to_home()
        except BattleError as battle_err:
            print(battle_err)
        else:
            return self.status
