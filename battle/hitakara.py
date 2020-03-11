from time import sleep

from colorama import Fore

from core.preferences import preferences_mgr

from .base import (BattleError, BattleExecutorBase, BattlePointType,
                   BattleResult, EventInfoBase)
from .utils import (add_passcards, check_and_get_sally_data, check_passcards,
                    decrypte_battle_msg, get_alive_member_count,
                    get_favorable_formation)

battle_config = preferences_mgr.get("battle")


class HitakaraEventInfo(EventInfoBase):
    def __init__(self, api):
        super().__init__("秘寶之里～楽器集めの段")
        self.api = api
        self.rest_passcard = 0  # 現在持有的手形數
        self.rest_passcard_max = 3  # 現在可用的最大手形數

    def check_passcard(self):
        return self.rest_passcard != 0

    @classmethod
    def create(cls, api):
        data = check_and_get_sally_data(api)
        if data is None:
            return None

        event = list(data.get("event").values())[0]
        if event is None:
            print("無活動！")
            return None

        money = data.get("currency").get("money")
        print(f"持有小判：{money}")

        point = list(data.get("point").values())[0]
        print(f"持有玉：{point}")

        event_info = cls(api)
        event_info.money = data.get("currency").get("money")
        event_info.event_id = event.get("event_id")
        fields = list(event["field"].values())
        event_info.field_id = fields[len(fields) - 1]["field_id"]
        event_info.rest_passcard = event.get("cost").get("rest")
        event_info.rest_passcard_max = event.get("cost").get("max")
        return event_info


class HitakaraBattleExecutor(BattleExecutorBase):
    instrument_name = ["笛", "箏", "三味線", "太鼓", "鈴"]
    old_card_map = {
        "16": "太刀",
        "17": "槍",
        "18": "薙刀",
        "55": "毒矢",
        "56": "怪火",
        "59": "落穴",
        "61": "炮烙玉",
    }
    new_card_map = {
        "504": "太刀",
        "505": "脇差",
        "506": "槍",
        "507": "薙刀",
        "243": "毒矢",
        "301": "怪火",
        "203": "炮烙玉",
    }

    def __init__(self, api, team):
        super().__init__(api, team)
        self.event_info = HitakaraEventInfo.create(api)
        self.event_id = self.event_info.event_id
        self.field = self.event_info.field_id
        self._next_square_id = 1
        self._is_battle_card = False
        self._enemy_formation = -1
        self._resource_point_data = []
        self._battle_point = 0
        self._total_point = 0
        self._takeout = None
        self._count_fires = 0

    @staticmethod
    def get_instrument_name(id):
        id = int(id)
        return (
            HitakaraBattleExecutor.instrument_name[id - 25] if 25 <= id <= 29 else "不明"
        )

    @staticmethod
    def get_old_card_name(id):
        if int(id) == 13:
            return "BOSS"
        if 40 <= int(id) <= 52:
            return "玉"

        id = str(id)
        return HitakaraBattleExecutor.old_card_map[id]

    @staticmethod
    def get_new_card_name(id):
        if int(id) == 999:
            return "BOSS"
        if 109 <= int(id) <= 121:
            return "玉"

        id = str(id)
        return HitakaraBattleExecutor.new_card_map[id]

    @staticmethod
    def get_card_name(id):
        try:
            return HitakaraBattleExecutor.get_new_card_name(id)
        except KeyError:
            print(f"遇到奇怪的 id = {id}")
            return "不明"

    def prepare(self):
        print("準備建立「秘寶之里～楽器集めの段～」活動！")

        if not check_passcards(self.event_info):
            if not add_passcards(
                self.api, self.event_id, self.event_info.rest_passcard_max
            ):
                return False

        ret = self.api.event_battle_start(
            self.event_id, self.team_id, self.field, sword_serial_id=0
        )
        if not ret["status"]:
            print("使用手形 1 個")
            self.team_ref.battle_init()
            return True
        else:
            raise BattleError("初始化活動戰鬥")

    def foward(self):
        ret = self.api.event_forward(
            square_id=self._next_square_id,
            direction=0,
            transfer_square_id=0,
            use_item_id=0,
        )
        if ret["status"]:
            raise BattleError("活動前進")

        return self.update_info_from_forward(ret)

    def update_info_from_forward(self, data):
        self._next_square_id = data["square_id"]
        self.finished = data["is_finish"]

        if len(data["scout"]) != 0:
            self._enemy_formation = data["scout"]["formation_id"]
            return BattlePointType.BATTLE
        else:
            self._resource_point_data = data["gimmick"]
            return BattlePointType.MATERIAL

    def battle(self, formation):
        ret = self.api.battle(formation)

        if ret["status"]:
            raise BattleError("活動戰鬥主函數")

        return decrypte_battle_msg(ret["data"], ret["iv"])

    def update_after_battle(self, data):
        super().update_after_battle(data)

        gimmick = data["gimmick"]

        if not gimmick:
            raise BattleError("Gimmick 遺失！")

        self._battle_point = int(gimmick["bonus"])
        self._total_point += self._battle_point

        if "takeout" not in gimmick["settle_up"].keys():
            return

        self._takeout = gimmick["settle_up"]["takeout"]

        # 檢查敗北
        self.finished = gimmick["is_finish"]

    def update_after_return(self, data):
        gimmick = data["gimmick"]

        if not gimmick:
            raise BattleError("Gimmick 遺失！")

        self._total_point = gimmick["settle_up"]["takeout"]["point"]

        if "takeout" not in gimmick["settle_up"].keys():
            return

        self._takeout = gimmick["settle_up"]["takeout"]

    def print_final_takeout(self):
        if self._takeout is None:
            print(Fore.RED + "未取得任何成果！")
            return

        from prettytable import PrettyTable

        table = PrettyTable()
        table.field_names = ["獲得玉", "笛", "箏", "三味線", "太鼓", "鈴"]

        row = [self._takeout["point"]]
        row = row + [v for v in self._takeout["instrument"].values()]
        table.add_row(row)

        print(table)

    def back_to_home(self):
        self.team_ref.battle_end()

    def handle_battle_point(self, formation=-1):
        best_formation = (
            get_favorable_formation(self._enemy_formation)
            if formation == -1
            else formation
        )
        ret = self.battle(best_formation)
        self.update_after_battle(ret)

    def handle_resource_point(self):
        if len(self._resource_point_data) == 0:
            return

        data = self._resource_point_data
        card_id = int(data["draw"])

        # if 40 <= card_id <= 52:
        if 109 <= card_id <= 121:
            # point = card_id - 30
            point = card_id - 99

            # 怪火倍數
            point = point * int(pow(2, self._count_fires))
            self._total_point += point
            print(f"獲得 {point} 玉！")
        else:
            card_name = self.get_card_name(card_id)
            print(f"遭遇到 {card_name}")
            if card_name == "怪火":
                self._count_fires += 1

    def play(self):
        try:
            if not self.prepare():
                return None

            while True:
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

            if self.status == BattleResult.TEAM_STATUS_BAD:
                ret = self.api.event_return()
                self.update_after_return(ret)

            self.print_final_takeout()
            self.team_ref.show()
            self.back_to_home()
        except BattleError as battle_err:
            print(battle_err)
        else:
            return self.status
