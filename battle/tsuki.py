from time import sleep

from core.preferences import preferences_mgr

from .base import (BattleError, BattleExecutorBase, BattlePointType,
                   BattleResult, EventInfoBase)
from .utils import (check_and_get_sally_data, decrypte_battle_msg,
                    get_favorable_formation, get_resource_type_name)

battle_config = preferences_mgr.get("battle")


class TsukiEventInfo(EventInfoBase):
    def __init__(self, api):
        super().__init__("月兔糰子")
        self.api = api
        self._layer_field = -1
        self.collect_item = {}

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
        data = check_and_get_sally_data()
        if data is None:
            return None

        event = list(data.get("event").values())[0]
        if event is None:
            print("無活動！")
            return None

        event_info = cls()
        event_info.event_id = event["event_id"]
        event_info.field_id = list(event["field"].values())[0]["field_id"]
        event_info.layer_field = list(event["field"].values())[0]["layer_num"]
        for key, item in event["collection_item"].items():
            event_info.collect_item[str(key)] = item["num"]
        return event_info


class TsukiExecutor(BattleExecutorBase):
    def __init__(self, api, team):
        super().__init__(api, team)
        self.event_info = TsukiEventInfo.create(api)
        self.event_id = self.event_info.event_id
        self.field = self.event_info.field_id
        self.layer_id = self.event_info.layer_id
        self._next_candidate_points = []
        self._enemy_formation = -1
        self._resource_point_data = None
        self._dango_count = 0  # 糰子數目

    def prepare(self):
        print("準備建立「月兔糰子」活動！")

        ret = self.api.event_battle_start(
            self.event_id, self.team_id, self.field_id, event_layer_id=self.layer_id
        )
        if not ret["status"]:
            self.team_ref.battle_init()
            self._next_candidate_points = ret["tsukimi"]["next"] or []
        else:
            raise BattleError("初始化活動戰鬥")

    def foward(self):
        from random import randint

        # 如果可以選，隨便挑一個點前進！
        count = len(self._next_candidate_points)
        direction = (
            self._next_candidate_points[randint(0, count - 1)] if count != 0 else 0
        )

        ret = self.api.event_forward(direction=direction)
        if ret["status"]:
            raise BattleError("活動前進")
        return self.update_info_from_forward(ret)

    def update_info_from_forward(self, data):
        self._next_square_id = data["square_id"]
        self.finished = data["is_finish"]
        self._next_candidate_points = data["tsukimi"]["next"] or []

        if len(data["scout"]) != 0:
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

    def update_after_battle(self, data):
        super().update_after_battle(data)

        for reward in data["result"]["drop_reward"]:
            if int(reward["item_id"]) == 37:
                self._dango_count += int(reward["item_num"])

        rabbit_drop_data = data["tsukimi"]["rabbit"]
        if int(rabbit_drop_data["item_id"]) == 37:
            self._dango_count += int(rabbit_drop_data["num"])

        self._next_candidate_points = data["tsukimi"]["next"]

    def handle_battle_point(self, formation=-1):
        best_formation = (
            get_favorable_formation(self._enemy_formation)
            if formation == -1
            else formation
        )
        ret = self.battle(best_formation)
        self.update_after_battle(ret)

    def handle_resource_point(self):
        from prettytable import PrettyTable

        table = PrettyTable()
        table.field_names = ["物品名稱", "數量"]

        for resource in self._resource_point_data:
            if int(resource["item_type"]) == 1:
                self._dango_count += int(resource["item_num"])
                continue
            resource_name = get_resource_type_name(resource["item_type"])
            table.add_row([resource_name, str(resource["item_num"])])
        print(table)

    def print_final_takeout(self):
        from prettytable import PrettyTable

        table = PrettyTable()
        table.field_names = ["獲得糰子"]
        table.add_row([self._dango_count])
        print(table)

    def back_to_home(self):
        self.team_ref.battle_end()

    def play(self):
        try:
            self.prepare()

            while True:
                if not self.team_ref.can_foward_in_battle():
                    self.status = BattleResult.TEAM_STATUS_BAD
                    break

                point_type = self.foward()
                if point_type == BattlePointType.BATTLE:
                    self.handle_battle_point()
                else:
                    self.handle_resource_point()

                if self.finished or self.status is not BattleResult.NORMAL:
                    self.print_final_takeout()
                    break

                sleep(battle_config.get("battle_internal_delay"))

            self.team_ref.show()
            self.back_to_home()
        except BattleError as battle_err:
            print(battle_err)
        else:
            return self.status
