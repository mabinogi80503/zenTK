from time import sleep

from core.preferences import preferences_mgr

from .base import (BattleError, BattleExecutorBase, BattlePointType,
                   BattleResult, EventInfoBase)
from .utils import (check_and_get_sally_data, decrypte_battle_msg,
                    get_alive_member_count, get_favorable_formation,
                    get_resource_id_name)

battle_config = preferences_mgr.get("battle")


class OsakajiEventInfo(EventInfoBase):
    def __init__(self, api):
        super().__init__("地下に眠る千両箱")
        self.api = api
        self._layer_field = -1

    @property
    def layer_field(self):
        return self._layer_field

    @layer_field.setter
    def layer_field(self, value):
        if value is None:
            return None
        if not isinstance(value, int):
            value = int(value)
        self._layer_field = value

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

        event_info = cls(api)
        event_info.money = data.get("currency").get("money")
        event_info.event_id = 85
        fields = list(event["field"].values())
        event_info.field_id = fields[len(fields) - 1]["field_id"]
        event_info.layer_id = fields[len(fields) - 1]["layer_num"]
        return event_info


class OsakajiExecutor(BattleExecutorBase):
    def __init__(self, api, team, *args, **kwargs):
        super().__init__(api, team, *args, **kwargs)
        self.event_info = OsakajiEventInfo.create(api)
        self.event_id = self.event_info.event_id
        self.field = self.event_info.field_id

        layer = kwargs.get("layer", None)
        # 優先打指定樓層
        self.layer_id = layer if layer else self.event_info.layer_id
        self._enemy_formation = -1
        self._resource_point_data = None
        self._rare_boss = False
        self._boss_defeated = False

    def prepare(self):
        print(f"活動 {self.event_info.name} 準備")

        ret = self.api.event_battle_start(
            self.event_id, self.team_id, self.field, event_layer_id=self.layer_id
        )

        if not ret["status"]:
            self.team_ref.battle_init()
        else:
            print(
                f"EventID = {self.event_id}, FIELD = {self.field_id}, LAYER = {self.layer_id}"
            )
            raise BattleError("初始化活動戰鬥")

    def foward(self):
        ret = self.api.event_forward(direction=0)
        if ret["status"]:
            raise BattleError("活動前進")

        return self.update_info_from_forward(ret)

    def update_info_from_forward(self, data):
        self.finished = data["is_finish"]
        self._rare_boss = False if data["koban"]["is_rare_boss"] == 0 else True

        if len(data["scout"]) != 0:
            self._enemy_formation = data["scout"]["formation_id"]
            return BattlePointType.BATTLE
        else:
            self._resource_point_data = data["reward"]
            return BattlePointType.MATERIAL

    def _check_reward(self, rewards):
        if rewards is None:
            return None

        for reward in rewards:
            # 小判
            rid = reward.get("item_id", None)
            name = get_resource_id_name(rid)
            if name == "小判":
                point = int(reward.get("item_num", "0")) + int(reward.get("bonus", "0"))
                if point > 0:
                    print(f"獲得 {point} 小判")
            else:
                print(f"獲得 {name}")

    def battle(self, formation):
        ret = self.api.battle(formation)

        if ret["status"]:
            raise BattleError("活動戰鬥主函數")

        return decrypte_battle_msg(ret["data"], ret["iv"])

    def handle_battle_point(self, formation=-1):
        best_formation = (
            get_favorable_formation(self._enemy_formation)
            if formation == -1
            else formation
        )
        ret = self.battle(best_formation)
        self.update_after_battle(ret)

    def update_after_battle(self, data):
        super().update_after_battle(data)

        result = data["result"]
        self._check_reward(result.get("reward", None))

        # 檢查敗北
        self.finished = data["finish"]["is_finish"]

        # 戰勝樓層 BOSS
        self._boss_defeated = data["koban"]["is_boss_defeat"]

    def handle_resource_point(self):
        if len(self._resource_point_data) == 0:
            return

        self._check_reward(self._resource_point_data)

    def back_to_home(self):
        self.team_ref.battle_end()

        if self.status is BattleResult.TEAM_STATUS_BAD:
            print("隊伍狀況不佳")

        # 隊長受重傷直接回家，不需要呼叫 event return
        if not self.team_ref.member_status_normal(0):
            return None

        self.api.event_return()

    def play(self):
        try:
            self.prepare()

            print(f"正在攻略 {self.layer_id} 樓")

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
                    self.handle_battle_point()
                else:
                    self.handle_resource_point()

                if (
                    self.finished
                    or self._boss_defeated
                    or self.status is not BattleResult.NORMAL
                ):
                    break

                sleep(battle_config.get("battle_internal_delay"))

            self.team_ref.show()
            self.back_to_home()
        except BattleError as battle_err:
            print(battle_err)
        else:
            return self.status
