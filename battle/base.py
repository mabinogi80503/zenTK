from abc import ABCMeta, abstractmethod
from enum import Enum

from colorama import Fore

from core.preferences import preferences_mgr

from .utils import check_new_sword

battle_config = preferences_mgr.get("battle")


class BattleResult(Enum):
    NORMAL = "正常結束"
    BE_DEFEATED = "戰敗"
    TEAM_STATUS_BAD = "隊伍狀況不佳"


class BattlePointType(Enum):
    NONE = 0
    BATTLE = 1
    MATERIAL = 2


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

    MATERIAL = 2


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
