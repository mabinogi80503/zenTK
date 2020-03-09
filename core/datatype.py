from enum import IntEnum
from functools import wraps

import attr
from colorama import Back, Fore
from prettytable import PrettyTable

from .notification import Subscriber
from .preferences import preferences_mgr

battle_cfg = preferences_mgr.get("battle")


def filter_by(key):
    def decorator(func):
        @wraps(func)
        def wrapper(self, data):
            if data is None or key not in data.keys():
                return func(self, None)
            return func(self, data[key])

        return wrapper

    return decorator


class Resources(object):
    """
    描述本丸資源
    """

    def __init__(self, api):
        self.api = api
        self.bill = 0  # 依賴札
        self.charcoal = 0  # 木炭
        self.steel = 0  # 玉鋼
        self.coolant = 0  # 冷卻材
        self.file = 0  # 砥石
        self.api.registe("start", Subscriber("Resource", self.update_from_json))

    @filter_by(key="resource")
    def update_from_json(self, resource):
        if resource is None:
            return

        self.bill = resource["bill"]
        self.charcoal = resource["charcoal"]
        self.steel = resource["steel"]
        self.coolant = resource["coolant"]
        self.file = resource["file"]

    def show(self):
        table = PrettyTable()
        table.field_names = ["依賴札", "木炭", "玉鋼", "冷卻水", "砥石"]
        table.add_row([self.bill, self.charcoal, self.steel, self.coolant, self.file])
        print(table)


@attr.s
class Sword(object):
    """
    描述玩家身上持有的刀男之詳細訊息
    """

    serial_id = attr.ib()
    sword_id = attr.ib()
    name = attr.ib()
    symbol = attr.ib()
    level = attr.ib(type=int, converter=int)
    protect = attr.ib(type=int, converter=int)
    hp = attr.ib(type=int, converter=int)
    hp_max = attr.ib(type=int, converter=int)
    exp = attr.ib(type=int, converter=int)
    raw_fatigue = attr.ib(type=int, converter=int)
    equipment1 = attr.ib()
    equipment2 = attr.ib()
    equipment3 = attr.ib()
    horse = attr.ib()
    recover_time = attr.ib()
    action_status = attr.ib(type=int, converter=int)
    in_battle = attr.ib(init=False, default=False)
    battle_fatigue = attr.ib(init=False, converter=int, default=-1)

    class HPInjuryPercentage(IntEnum):
        MINOR = 90
        MEDIUM = 65
        SERIOUS = 31

    class HPStatus(IntEnum):
        NORMAL = 0
        MINOR = 1
        MEDIUM = 2
        SERIOUS = 3
        DEAD = 4

    class FatigueStatus(IntEnum):
        RED = 8
        ORANGE = 20
        NORMAL = 49
        SAKURA = 100

    @classmethod
    def from_json(cls, static_lib, data):
        sword_id = data.get("sword_id")
        sword_data = static_lib.get_sword(sword_id)
        if not sword_data:
            print(f"建構錯誤：不存在的刀劍 ID: {sword_id}")

        return cls(
            data.get("serial_id"),
            data.get("sword_id"),
            sword_data.name,
            data.get("symbol"),
            data.get("level"),
            data.get("protect"),
            data.get("hp"),
            data.get("hp_max"),
            data.get("exp"),
            data.get("fatigue"),
            data.get("equip_serial_id1"),
            data.get("equip_serial_id2"),
            data.get("equip_serial_id3"),
            data.get("horse_serial_id"),
            data.get("recovered_at"),
            data.get("status"),
        )

    @classmethod
    def from_old_one(cls, old, data):
        return attr.evolve(
            old,
            level=data.get("level"),
            hp=data.get("hp"),
            exp=data.get("exp"),
            raw_fatigue=data.get("fatigue"),
            symbol=data.get("symbol"),
            equipment1=data.get("equip_serial_id1"),
            equipment2=data.get("equip_serial_id2"),
            equipment3=data.get("equip_serial_id3"),
            horse=data.get("horse_serial_id"),
            recover_time=data.get("recovered_at"),
            action_status=data.get("status"),
        )

    def get_new_from_battle_report(self, user_data, data):
        for i in range(1, 4):
            equip_serial_id = self.__dict__[f"equipment{i}"]
            if equip_serial_id is None or len(equip_serial_id) == 0:
                continue

            equip = user_data.get_equipment(equip_serial_id).get_new_from_battle_report(
                data[f"soldier{i}"]
            )
            user_data.update_equipment(equip_serial_id, equip)

        new_one = attr.evolve(
            self,
            level=data.get("level"),
            hp=data.get("hp"),
            exp=data.get("exp"),
            raw_fatigue=data.get("fatigue"),
            symbol=data.get("symbol"),
            horse=data.get("horse_serial_id"),
            recover_time=data.get("recovered_at"),
            action_status=data.get("status"),
        )

        new_one.in_battle = self.in_battle
        new_one.battle_fatigue = self.battle_fatigue
        return new_one

    @property
    def fatigue(self):
        now_fatigue = int(self.raw_fatigue)

        if self.in_battle and self.battle_fatigue != -1:
            return self.battle_fatigue

        if now_fatigue < Sword.FatigueStatus.NORMAL:
            if self.recover_time:
                from datetime import timedelta
                from .utils import get_datime_diff_from_now

                # 三分鐘恢復一次，計算次數
                diff = (int)(
                    get_datime_diff_from_now(self.recover_time) / timedelta(minutes=3)
                )

                # 時間自動恢復，一次恢復三點
                real_fatigue = now_fatigue + diff * 3
                # 最大不超過 normal(49)
                real_fatigue = min(real_fatigue, (int)(Sword.FatigueStatus.NORMAL))
                return real_fatigue

        return now_fatigue

    @property
    def equipments(self):
        return [self.equipment1, self.equipment2, self.equipment3]

    @property
    def red_face(self):
        return self.fatigue <= Sword.FatigueStatus.RED

    @property
    def fatigue_text(self):
        if self.fatigue <= Sword.FatigueStatus.RED:
            return Fore.RED + "過勞" + Fore.RESET
        elif self.fatigue <= Sword.FatigueStatus.ORANGE:
            return Fore.YELLOW + "疲勞" + Fore.RESET
        elif self.fatigue <= Sword.FatigueStatus.NORMAL:
            return "通常"
        else:
            return "飄花"

    @property
    def hp_flag(self):
        if int(self.hp) <= 0:
            return Sword.HPStatus.DEAD

        hp_percent = (float(self.hp) / float(self.hp_max)) * 100.0
        if hp_percent >= int(Sword.HPInjuryPercentage.MINOR):
            return Sword.HPStatus.NORMAL
        elif hp_percent >= int(Sword.HPInjuryPercentage.MEDIUM):
            return Sword.HPStatus.MINOR
        elif hp_percent >= int(Sword.HPInjuryPercentage.SERIOUS):
            return Sword.HPStatus.MEDIUM
        else:
            return Sword.HPStatus.SERIOUS

    @property
    def status_text(self):
        medium = Fore.YELLOW + "中傷" + Fore.RESET
        serious = Back.WHITE + Fore.RED + "重傷" + Fore.RESET + Back.RESET
        dead = Back.YELLOW + Fore.BLACK + "刀劍破壞" + Fore.RESET + Back.RESET
        return ["正常", "輕傷", medium, serious, "戰線破壞", dead][self.hp_flag]

    def battle_init(self):
        self.battle_fatigue = self.fatigue
        self.battle_fatigue -= 10  # 進入戰鬥就少十點
        self.battle_fatigue = max(0, self.battle_fatigue)
        self.in_battle = True

    def battle_end(self):
        self.raw_fatigue = self.battle_fatigue
        self.battle_fatigue = -1
        self.in_battle = False

    def calculate_battle_fatigue(self, rank, leader=False, mvp=False):
        """
        戰鬥結束時對，計算對應的疲勞度
        MVP： +10
        隊長： +3
        S: +1, A: +0, B: -1, C: -2, 敗北: -3
        """
        if mvp:
            self.battle_fatigue += 10

        if leader:
            self.battle_fatigue += 3

        upper = [-3, 0, 1, 0, -1, -2, -3][rank]
        self.battle_fatigue += upper
        self.battle_fatigue = max(0, self.battle_fatigue)
        self.battle_fatigue = min(100, self.battle_fatigue)

    @property
    def battleable(self):
        return self.hp_flag not in [Sword.HPStatus.SERIOUS, Sword.HPStatus.DEAD]


class SwordTeam(object):
    """
    描述一隊隊伍的組成訊息
    """

    def __init__(self, api, user_data, team_id):
        self.api = api
        self.user_data = user_data
        self.id = team_id
        self.name = "不明"
        self.swords = {}
        self.status = 0

        sub_name = f"SwordTeam{self.id}"
        self.api.registe("party_list", Subscriber(sub_name, self.build))
        self.api.registe("set_sword", Subscriber(sub_name, self.update_from_set_sword))
        self.api.registe("remove_sword", Subscriber(sub_name, self.handle_remove_sword))
        self.api.registe("swap_team", Subscriber(sub_name, self.handle_swap_team))

    @property
    def captain_serial_id(self):
        return self.swords.get("1")

    @property
    def sword_refs(self):
        return [self.user_data.get_sword(id) for id in self.swords.values()]

    @property
    def status_text(self):
        return ["未開放", "通常", Fore.GREEN + "遠征中" + Fore.RESET, "活動地圖中"][self.status]

    @property
    def opened(self):
        return self.status != 0

    def available(self):
        if self.status != 1:
            print("指定的隊伍正在遠征中！")
            return False

        red_face_sword = []
        for sword in self.sword_refs:
            # 略過隊伍內空的刀位
            if not sword:
                continue

            # 紅臉大於一位不出陣
            if len(red_face_sword) > 1:
                print(f"太多刀紅臉了...{red_face_sword}")
                return False

            # 檢查是否中傷以上或狀態不正常(比如正在遠征)
            if not sword.battleable:
                print(
                    Fore.YELLOW
                    + sword.name
                    + Fore.RESET
                    + f"的狀態不佳({sword.status_text})"
                )
                return False

            if sword.red_face:
                red_face_sword.append(sword.name)
        return True

    def can_foward_in_battle(self):
        """
        檢查每一位成員的狀態是否可以戰鬥
        """
        return not (False in [sword.battleable for sword in self.sword_refs if sword])

    def member_status_normal(self, index):
        sword = self.sword_refs[index]

        if sword is None:
            return None

        if 0 <= index <= 5:
            return sword.battleable
        return False

    def set_sword(self, index, serial_id):
        if self.swords[str(index)] == serial_id:
            return

        if 1 <= int(index) <= 6:
            self.api.set_sword(self.id, index, serial_id)
        else:
            raise ValueError(f"貌似隊伍沒有欄位 {index} 可以排隊耶？")

    def remove(self, index):
        if index in self.swords.keys():
            if self.id == "1" and index == "1":
                return

            if self.swords[index]:
                self.api.remove_sword(self.id, index, self.swords[index])
        else:
            raise ValueError(f"欄位 {index} 好像不存在耶？")

    def update(self, index, serial_id):
        if index in self.swords.keys():
            self.swords[index] = serial_id

    def update_from_battle_report(self, rank, mvp, data):
        for idx, slot in data.items():
            serial_id = slot.get("serial_id")
            if not serial_id:
                return

            old = self.user_data.get_sword(serial_id)
            new = old.get_new_from_battle_report(self.user_data, slot)

            self.user_data.update_sword(serial_id, new)

            is_leader = idx == "1"
            is_mvp = mvp == slot.get("serial_id")
            new.calculate_battle_fatigue(rank, leader=is_leader, mvp=is_mvp)

        if battle_cfg.get("show_team_info_on_battle", False):
            self.show()

    def clear(self):
        for i in range(6, 0, -1):
            self.remove(str(i))

    @filter_by(key="party")
    def build(self, data):
        data = data.get(str(self.id))

        if not data:
            return

        self.name = data.get("party_name")
        for index, sword_data in data.get("slot").items():
            self.swords[index] = sword_data.get("serial_id")
        self.status = int(data.get("status"))

    def battle_init(self):
        for sword in self.sword_refs:
            if sword:
                sword.battle_init()

    def battle_end(self):
        for sword in self.sword_refs:
            if sword:
                sword.battle_end()

    def update_from_set_sword(self, data):
        data = data.get(self.id)
        for index, sword_data in data.get("slot").items():
            self.update(index, sword_data.get("serial_id"))

    def handle_remove_sword(self, data):
        self.swords.clear()

        team_data = data[self.id]

        if not team_data or len(team_data) == 0:
            return

        for index, sword_data in team_data["slot"].items():
            if sword_data:
                self.swords[index] = sword_data.get("serial_id")
            else:
                self.swords[index] = None

        self.status = int(data.get("status"))

    def handle_swap_team(self, data):
        self.swords.clear()
        team_data = data[self.id]

        if not team_data or len(team_data) == 0:
            return

        for index, sword_data in team_data["slot"].items():
            if sword_data:
                self.swords[index] = sword_data.get("serial_id")
            else:
                self.swords[index] = None

    def show(self):
        print(Fore.YELLOW + f"{self.name}" + " - " + self.status_text)

        if not self.opened:
            return

        total_level = num_sword = 0

        table = PrettyTable()
        table.field_names = [
            "順",
            "Serial",
            "名稱",
            "狀態",
            "疲勞",
            "等級",
            "血量",
            "刀裝-1",
            "刀裝-2",
            "刀裝-3",
        ]
        table.align["名稱"] = table.align["疲勞"] = "l"

        for index, sword in enumerate(self.sword_refs):
            row = [str(index + 1)]
            if not sword:
                row += [""] * (len(table.field_names) - 1)
            else:
                num_sword += 1
                total_level += sword.level

                hp_text = str(sword.hp) + "/" + str(sword.hp_max)
                fatigue = sword.fatigue_text + "(" + str(sword.fatigue) + ")"

                equipments = [
                    self.user_data.get_equipment(e).name
                    for e in sword.equipments
                    if e and not self.user_data.get_equipment(e).is_destroyed
                ]
                if len(equipments) < 3:
                    equipments += ["-"] * (3 - len(equipments))

                row += [
                    sword.serial_id,
                    sword.name,
                    sword.status_text,
                    fatigue,
                    sword.level,
                    hp_text,
                ] + equipments
            table.add_row(row)

        print("平均等級：" + (f"{int(total_level / num_sword)}" if num_sword != 0 else "0"))
        print(table.get_string(title="f{self.name}"))

    def make_min_fatigue_be_captain(self):
        org_captain_serial_id = self.captain_serial_id

        # 如果是空刀位，設定成 101 讓他最飄花（？）而擺到後面去
        sorted_swords = sorted(
            self.sword_refs, key=lambda sword: sword.fatigue if sword else 101
        )

        if sorted_swords[0].serial_id == org_captain_serial_id:
            return

        ret = self.api.set_sword(
            team=self.id, index=1, serial=sorted_swords[0].serial_id
        )
        if ret["status"] == 0:
            print(Fore.YELLOW + f"{sorted_swords[0].name}" + Fore.RESET + " 最為疲勞，成為隊長！")


@attr.s
class Equipment(object):
    """
    表示玩家身上持有刀裝的詳細訊息
    """

    name = attr.ib()
    serial_id = attr.ib()
    equip_id = attr.ib()
    priority = attr.ib()
    soldier = attr.ib(type=int, converter=int)
    is_destroyed = attr.ib(init=False, default=False)

    def __attrs_post_init__(self):
        if self.soldier <= 0:
            self.is_destroyed = True

    @classmethod
    def from_json(cls, static_lib, data):
        equip_id = data.get("equip_id")
        try:
            name = static_lib.get_equipment(equip_id).name
        except AttributeError:
            print(Fore.RED + f"新道具？ ID: {equip_id}，請聯絡管理者！")
            from sys import exit

            exit(1)

        return cls(
            name,
            data.get("serial_id"),
            data.get("equip_id"),
            data.get("priority"),
            data.get("soldier"),
        )

    def get_new_from_battle_report(self, hp):
        return attr.evolve(self, soldier=hp)
