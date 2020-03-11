from time import sleep
from abc import ABCMeta, abstractmethod

from colorama import Fore

from core.preferences import preferences_mgr

from .base import (
    BattleError,
    BattleExecutorBase,
    BattlePointType,
    BattleResult,
    EventInfoBase,
)

from .utils import (
    add_passcards,
    check_and_get_sally_data,
    check_passcards,
    decrypte_battle_msg,
    get_alive_member_count,
    get_favorable_formation,
)

battle_config = preferences_mgr.get("battle")

MAP4 = {
    "map": [
        [0],
        [3, 4, 5],
        [2, 4, 6, 7],
        [2, 3, 5, 8],
        [2, 4, 9],
        [3, 7, 11],
        [3, 6, 8, 12],
        [4, 7, 9, 17],
        [5, 8, 10, 13],
        [9, 14, 15],
        [6, 12, 16],
        [7, 11, 17],
        [9, 14, 17, 18],
        [10, 13, 19],
        [10, 19],
        [11, 17],
        [8, 12, 13, 16, 18, 20],
        [13, 17, 19],
        [14, 15, 18],
        [17],
    ],
    "target": 20,
}


class FreesearchEventInfo(EventInfoBase):
    def __init__(self, api):
        super().__init__("江戸城潜入調査")
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

        event = list(data.get("event").values())[0]
        if event is None:
            print("無活動！")
            return None

        money = data.get("currency").get("money")
        print(f"持有小判：{money}")

        # point = list(data.get("point").values())[0]
        # print(f"持有金鑰：{point}")

        event_info = cls(api)
        event_info.money = data.get("currency").get("money")
        event_info.event_id = event.get("event_id")
        fields = list(event["field"].values())
        event_info.field_id = fields[len(fields) - 1]["field_id"]

        event_info.rest_passcard = event.get("cost").get("rest")
        event_info.rest_passcard_max = event.get("cost").get("max")
        print(f"手形剩餘：{event_info.rest_passcard}/{event_info.rest_passcard_max}")
        return event_info


class FreesearchExecutor(BattleExecutorBase):
    def __init__(self, api, team, *args, **kwargs):
        super().__init__(api, team)
        self.event_info = FreesearchEventInfo.create(api)
        self.event_id = self.event_info.event_id
        self.field = self.event_info.field_id

        self._enemy_formation = -1
        self._next_candidate_points = []
        # self._fix_path = [5, 9, 13, 17, 20]

        self._left_move = 6
        self._takeout = None

        self.path_selector = MaxPathSelector(MAP4["map"], MAP4["target"])
        self._next_square_id = 1

    def prepare(self):
        print(f"活動 {self.event_info.name} 準備")

        if not check_passcards(self.event_info):
            if not add_passcards(
                self.api, self.event_id, self.event_info.rest_passcard_max
            ):
                return False

        ret = self.api.event_battle_start(self.event_id, self.team_id, self.field)

        if not ret["status"]:
            print("使用手形 1 個")
            self.team_ref.battle_init()
            self._next_candidate_points = ret["freesearch"]["next"] or []
            return True
        else:
            raise BattleError("初始化活動戰鬥")

    def foward(self):

        direction = self.path_selector.next(self._next_square_id, self._left_move)

        ret = self.api.event_forward(direction=direction)

        if ret["status"]:
            raise BattleError("活動前進")
        return self.update_info_from_forward(ret)

    def update_info_from_forward(self, data):
        self._next_square_id = data["square_id"]
        self.finished = data["is_finish"]
        self._next_candidate_points = data["freesearch"]["next"] or []

        if len(data["scout"]) != 0:
            self._enemy_formation = data["scout"]["formation_id"]
            return BattlePointType.BATTLE
        else:
            self._resource_point_data = data["freesearch"]
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

        freesearch = data["freesearch"]

        if not freesearch:
            raise BattleError("Freesearch 遺失！")

        self._check_reward(freesearch)

        self.finished = freesearch["is_finish"]
        self._next_candidate_points = data["freesearch"]["next"]

    def handle_resource_point(self):
        if len(self._resource_point_data) == 0:
            return

        self._check_reward(self._resource_point_data)

    def _check_reward(self, data):
        if data is None:
            return None

        if data.get("incident", None) is None:
            reward = data.get("bonus", None)
        else:
            reward = data.get("incident", None)

        if reward is not None:
            got_points = reward.get("key_num", 0)
            print(f"獲得金鑰： {got_points} 把")

        self._left_move = data.get("movement", 0)
        # print(f"剩餘移動： {self._left_move } 步")

        if "takeout" not in data["settle_up"].keys():
            return
        self._takeout = data["settle_up"]["takeout"]

    def print_final_takeout(self):
        if self._takeout is None:
            print(Fore.RED + "未取得任何成果！")
            return

        print(Fore.YELLOW + f"總共獲得金鑰: {self._takeout} 把")

    def back_to_home(self):
        self.team_ref.battle_end()
        self.api.home()

    def play(self):
        try:
            if not self.prepare():
                return None

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

            self.print_final_takeout()
            self.team_ref.show()
            self.back_to_home()
        except BattleError as battle_err:
            print(battle_err)
        else:
            return self.status


class PathSelectorBase(object, metaclass=ABCMeta):
    def __init__(self, graph, target):
        self.graph = graph
        self.target = target

    @abstractmethod
    def next(self):
        raise NotImplementedError()


class MaxPathSelector(PathSelectorBase):
    def __init__(self, grpah, target):
        super().__init__(grpah, target)
        self.trace = []

    def init_path(self, start, step):
        self.start = start
        self.left_step = step
        self.trace.append(start)
        self.best_path = []
        self.process = []
        self.max_score = -1

    def add_next_step(self, vec):
        node = vec[-1]
        for i in self.graph[node - 1]:
            temp = vec[:]
            temp.append(i)

            if i == self.target:
                if self._get_score(temp) >= self.max_score:
                    self.best_path = temp[:]
                    self.max_score = self._get_score(temp)
            else:
                self.process.append(temp)

    def search_path(self):
        self.process.append([self.start])
        for i in range(1, self.left_step + 1):
            while len(self.process[0]) <= i:
                self.add_next_step(self.process.pop(0))

    def _get_score(self, vec):
        score = len(set(vec)) - 1
        for i in vec:
            if i in set(self.trace):
                score = score - 1
        return score

    def _find_next_node(self):
        self.search_path()
        if self.best_path:
            return self.best_path[1]
        else:
            from random import randint

            direction = self.graph[self.start][
                randint(0, len(self.graph[self.start]) - 1)
            ]
            return direction

    def next(self, start, step):
        self.init_path(start, step)

        direction = self._find_next_node()

        return direction
