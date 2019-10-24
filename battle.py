from abc import ABCMeta, abstractmethod
from enum import Enum
from time import sleep

from colorama import Fore

from preferences import preferences_mgr

battle_config = preferences_mgr.get("battle")


# 解密加密的戰報
def decrypte_battle_msg(data, iv):
    utf8_key = "9ij8pNKv7qVJnpj4".encode("utf-8")
    hex_iv = bytes.fromhex(iv)
    hex_data = bytes.fromhex(data)

    from Crypto.Cipher import AES

    cryptor = AES.new(utf8_key, AES.MODE_CBC, iv=hex_iv)
    decrypted: str = cryptor.decrypt(hex_data).decode("utf-8")

    import json

    return json.loads(decrypted[: decrypted.rfind("}") + 1])


def get_favorable_formation(enemy_formation):
    from random import randint

    # 對應的有利陣型
    formation = [None, "6", "1", "2", "3", "4", "5"]
    if not enemy_formation:
        return formation[randint(1, 6)]

    enemy_formation = int(enemy_formation)
    return formation[enemy_formation] if enemy_formation != 0 else str(randint(1, 6))


def get_formation_name(formation):
    return ["不明", "魚鱗", "鶴翼", "橫隊", "方", "雁行", "逆行"][formation] + "陣"


def get_resource_type_name(type):
    type = int(type)
    names = ["", "活動物品", "木炭", "玉鋼", "冷卻材", "砥石"]
    return names[type] if type < len(names) else "不明"


def get_resource_id_name(resource_id):
    resource_id = str(resource_id)
    names = {
        "0": "小判",
        "1": "依賴札",
        "2": "木炭",
        "3": "玉鋼",
        "4": "冷卻材",
        "5": "砥石",
        "37": "月兔糰子",
    }
    return names[resource_id] if resource_id in names.keys() else "不明"


def check_new_sword(data):
    """
    檢查戰鬥結束時，是否有獲取新的刀劍男士
    """
    if not data:
        return
    get_sword_id = data.get("get_sword_id", None)
    if not get_sword_id:
        return

    from database import static_lib

    sword_data = static_lib.get_sword(get_sword_id)
    if sword_data:
        print("獲得新刀劍：" + Fore.YELLOW + f"{static_lib.get_sword(get_sword_id).name}")
    else:
        print(Fore.YELLOW + "獲得一把沒有在資料庫內的刀！請聯絡專案作者更新資料庫！")


class BattleResult(Enum):
    NORMAL = "正常結束"
    BE_DEFEATED = "戰敗"
    TEAM_STATUS_BAD = "隊伍狀況不佳"


class BattleError(Exception):
    def __init__(self, msg):
        super().__init__(self)
        self.msg = msg

    def __str__(self):
        return f"戰鬥發生錯誤 ({self.msg})"


class BattleExecutorBase(object, metaclass=ABCMeta):
    def __init__(self, api, team):
        self.api = api
        self.team_ref = team
        self.team_id = team.id
        self.finished = False
        self.status = BattleResult.NORMAL

    # 創造一個活動
    @abstractmethod
    def prepare(self):
        raise NotImplementedError()

    # 前進
    @abstractmethod
    def foward(self):
        raise NotImplementedError()

    # 戰鬥
    @abstractmethod
    def battle(self, formation):
        """
        處理戰鬥內容
        """
        raise NotImplementedError()

    # 整體流程
    @abstractmethod
    def play(self):
        """
        處理地圖內的整體戰鬥流程
        """
        raise NotImplementedError()

    @abstractmethod
    def back_to_home(self):
        """
        處理全部的戰鬥結束後返回本丸之動作
        """
        raise NotImplementedError()

    def _update_team_info(self, data):
        # [None, "一騎打", "S", "A", "B", "C", "敗北"]
        rank = data["rank"]
        mvp_serial = data["mvp"]
        resutl_team_data = data["player"]["party"]["slot"]
        self.team_ref.update_from_battle_report(rank, mvp_serial, resutl_team_data)

        if rank == "6":
            self.status = BattleResult.BE_DEFEATED

    def update_after_battle(self, data):
        if data is None or not data["result"]:
            print(Fore.RED + "戰報異常！")
            return

        result = data["result"]
        check_new_sword(result)
        self._update_team_info(result)


class BattlePointType(Enum):
    NONE = 0
    BATTLE = 1
    MATERIAL = 2


class CommonBattleExecutor(BattleExecutorBase):
    def __init__(self, api, team, episode_id, field_id, sakura=False, *args, **kwargs):
        super().__init__(api, team)
        self.episode = int(episode_id)
        self.field = int(field_id)
        self.sakura = sakura
        self._square_id = 0
        self._enemy_formation = 0
        self._resource_point_data = []

    def prepare(self):
        ret = self.api.battle_start(self.team_id, self.episode, self.field)

        if not ret["status"]:
            self.team_ref.battle_init()
        else:
            raise BattleError("初始化戰鬥")

    def foward(self):
        """
        往前走一格，並給出該格是否為結束點，並確認該點屬性為戰鬥點或資源點
        回傳點的屬性
        """
        ret = self.api.battle_foward()

        if ret["status"]:
            raise BattleError("戰鬥前進")

        # 紀錄走到的地圖格號碼
        self._square_id = ret["square_id"]

        # 是否為終末格
        self.finished = ret["is_finish"]

        # 戰鬥格
        if len(ret["scout"]) != 0:
            self._enemy_formation = ret["scout"]["formation_id"]
            return BattlePointType.BATTLE
        else:
            self._resource_point_data = ret["reward"]
            return BattlePointType.MATERIAL

    def battle(self, formation):
        ret = self.api.battle(formation)

        if ret["status"]:
            raise BattleError("戰鬥主函數")

        return decrypte_battle_msg(ret["data"], ret["iv"])

    def back_to_home(self):
        ret = self.api.battle_back_to_home()

        if not ret["status"]:
            self.team_ref.battle_end()
        else:
            raise BattleError("返回本丸")

    def update_after_battle(self, data):
        super().update_after_battle(data)

        # 檢查敗北或戰鬥結束
        self.finished = data["finish"]["is_finish"]

    def check_grind_finish(self):
        if not battle_config.get("grind_mode", False):
            return

        from database import static_lib

        points = static_lib.get_mapid_before_boss(self.episode, self.field)
        if points:
            if self._square_id in points.get_points():
                self.finished = True

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

        for material in self._resource_point_data:
            material_name = get_resource_id_name(material["item_id"])
            material_count = material["item_num"]
            print(f"獲得 {material_name} x{material_count}")

    def play(self):
        try:
            self.prepare()

            while True:
                if not self.team_ref.can_foward_in_battle():
                    self.status = BattleResult.TEAM_STATUS_BAD
                    break

                next_point_type = self.foward()
                if next_point_type == BattlePointType.BATTLE:
                    self.handle_battle_point(formation=6)
                else:
                    self.handle_resource_point()

                self.check_grind_finish()

                if (
                    self.finished
                    or self.sakura
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


def check_and_get_sally_data(api):
    from api import APICallFailedException

    try:
        data = api.sally()
    except APICallFailedException:
        print(Fore.RED + "存取 sally 失敗！")
        return None
    else:
        return data


class EventInfoBase(object):
    def __init__(self, event_name=None):
        self.name = event_name if event_name else "未知活動名稱"
        self._event_id = -1
        self._field_id = -1
        self.money = 0  # 小判數

    @property
    def evnet_id(self):
        return self._event_id

    @evnet_id.setter
    def event_id(self, value):
        if value is None:
            return None
        if not isinstance(value, int):
            value = int(value)
        self._event_id = value

    @property
    def field_id(self):
        return self._field_id

    @field_id.setter
    def field_id(self, value):
        if value is None:
            return None
        if not isinstance(value, int):
            value = int(value)
        self._field_id = value


class HitakaraEventInfo(EventInfoBase):
    def __init__(self, api):
        super().__init__("秘寶之里～楽器集めの段")
        self.api = api
        self.reset_passcard = 0  # 現在持有的手形數
        self.rest_passcard_max = 3  # 現在可用的最大手形數

    def check_passcard(self):
        return self.reset_passcard != 0

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


class TsukiEventInfo(object):
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

        event = list(data.get("event").values())[0]
        if event is None:
            print("無活動！")
            return None

        money = data.get("currency").get("money")
        print(f"持有小判：{money}")

        event_info = cls(api)
        event_info.money = data.get("currency").get("money")
        event_info.event_id = event.get("event_id")
        fields = list(event["field"].values())
        event_info.field_id = fields[len(fields) - 1]["field_id"]
        event_info.layer_id = fields[len(fields) - 1]["layer_num"]
        return event_info


def new_event_info(event_name, api):
    if event_name == "hitakara":
        return HitakaraEventInfo.create(api)
    elif event_name == "tsuki":
        return TsukiEventInfo.create(api)
    elif event_name == "osakaji":
        return OsakajiEventInfo.create(api)

    raise ValueError(f"{event_name} 錯誤！")


def get_alive_member_count(swordref):
    return len(
        [
            battleable
            for battleable in [sword.battleable for sword in swordref if sword]
            if battleable
        ]
    )


# 秘寶之里～楽器集めの段～
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
        self.event_info = new_event_info("hitakara", api)
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

        return HitakaraBattleExecutor.old_card_map[id]

    @staticmethod
    def get_new_card_name(id):
        if int(id) == 999:
            return "BOSS"
        if 109 <= int(id) <= 121:
            return "玉"

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

        ret = self.api.event_battle_start(
            self.event_id, self.team_id, self.field, sword_serial_id=0
        )
        if not ret["status"]:
            self.team_ref.battle_init()
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
            self.prepare()

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


# 月兔糰子
class TsukiExecutor(BattleExecutorBase):
    def __init__(self, api, team):
        super().__init__(api, team)
        self.event_info = new_event_info("tsuki", api)
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


class OsakajiExecutor(BattleExecutorBase):
    def __init__(self, api, team, layer=None):
        super().__init__(api, team)
        self.event_info = new_event_info("osakaji", api)
        self.event_id = self.event_info.event_id
        self.field = self.event_info.field_id

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


def new_event(name, api, team, **kwargs):
    if name == "hitakara":
        return HitakaraBattleExecutor(api, team)
    if name == "tsuki":
        return TsukiExecutor(api, team)
    if name == "osakaji":
        layer = kwargs.get("layer", None)
        return OsakajiExecutor(api, team, layer=layer)

    return None
