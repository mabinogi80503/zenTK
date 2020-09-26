from time import sleep

from core.preferences import preferences_mgr

from .base import (
    BattleError,
    BattleExecutorBase,
    BattlePointType,
    BattleResult,
    EventInfoBase,
)
from .utils import (
    check_and_get_sally_data,
    decrypte_battle_msg,
    get_alive_member_count,
    get_favorable_formation,
    get_resource_type_name,
)

battle_config = preferences_mgr.get("battle")


class ArmamentExpansionEventInfo(EventInfoBase):
    def __init__(self, api):
        super().__init__("戦力拡充計画")
        self.api = api

    @classmethod
    def create(cls, api):
        data = check_and_get_sally_data(api)
        if data is None:
            return None

        event = data.get("event")
        if event is None:
            print("無活動！")
            return None

        event_info = cls(api)
        # event_info.event_id = event.get("event_id")
        event_info.event_id = 90
        fields = list(event["field"].values())

        not_finished_map_list = [
            field for field in fields if not field.get("is_finish", True)
        ]

        if len(not_finished_map_list) > 0:
            field_id = not_finished_map_list[0]["field_id"]
            layer_id = not_finished_map_list[0]["layer_num"]
            print("優先打尚未完成之地圖")
        else:
            field_id = fields[len(fields) - 1]["field_id"]
            layer_id = fields[len(fields) - 1]["layer_num"]

        event_info.field_id = field_id
        event_info.layer_id = layer_id
        return event_info


class ArmamentExpansionExecutor(BattleExecutorBase):
    def __init__(self, api, team, *args, **kwargs):
        super().__init__(api, team, *args, **kwargs)
        self.event_info = ArmamentExpansionEventInfo.create(api)
        self.event_id = self.event_info.event_id
        self.field_id = self.event_info.field_id

        self._enemy_formation = -1
        self._resource_point_data = None

    def prepare(self):
        print(f">> {self.event_info.name} <<")

        ret = self.api.event_battle_start(self.event_id, self.team_id, self.field_id)

        if not ret["status"]:
            self.team_ref.battle_init()
        else:
            print(f"EventID = {self.event_id}, FIELD = {self.field_id}")
            raise BattleError("初始化活動戰鬥")

    def foward(self):
        ret = self.api.event_forward(direction=0)
        if ret["status"]:
            raise BattleError("活動前進")

        return self.update_info_from_forward(ret)

    def update_info_from_forward(self, data):
        self.finished = data["is_finish"]

        if data.get("scout") is not None:
            self._enemy_formation = data["scout"]["formation_id"]
            return BattlePointType.BATTLE
        else:
            self._resource_point_data = data["reward"]
            return BattlePointType.MATERIAL

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

    def handle_resource_point(self):
        if len(self._resource_point_data) == 0:
            return

        self._check_reward(self._resource_point_data)

    def _check_reward(self, rewards):
        for reward in rewards:
            r_type = reward["item_type"]
            r_id = reward["item_id"]
            r_count = reward["item_num"]

            if r_type == 1:  # 一般道具?
                # id 1 = 富士御扎
                # id 8 = 手傳禮
                pass

            if r_type == 3:
                from core.database import equipment_data

                name = equipment_data.get(r_id)
                print(f"獲得 {name} x {r_count}")
                return None

            if r_type == 5:
                name = get_resource_type_name(r_id)
                print(f"獲得 {name} x {r_count}")
                return None

            print(f"獲得某個道具 Type={r_type}, id={r_id}, count={r_count}")

    def back_to_home(self):
        self.team_ref.battle_end()

        if self.status is BattleResult.TEAM_STATUS_BAD:
            print("隊伍狀況不佳")

        # 隊長受重傷直接回家，不需要呼叫 event return
        if not self.team_ref.member_status_normal(0):
            return None

        print("返回本丸")
        self.api.home()

    def play(self):
        try:
            self.prepare()

            print(f"正在攻略第 {self.field_id} 圖！")

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

                if self.finished or self.status is not BattleResult.NORMAL:
                    break

                sleep(battle_config.get("battle_internal_delay"))

            self.team_ref.show()
            self.back_to_home()
        except BattleError as battle_err:
            print(battle_err)
        else:
            return self.status
