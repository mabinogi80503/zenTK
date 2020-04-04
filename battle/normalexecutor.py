from time import sleep

from core.preferences import preferences_mgr

from .base import (BattleError, BattleExecutorBase, BattlePointType,
                   BattleResult)
from .utils import (decrypte_battle_msg, get_favorable_formation,
                    get_resource_id_name)

battle_config = preferences_mgr.get("battle")


class CommonBattleExecutor(BattleExecutorBase):
    def __init__(self, api, team, episode_id, field_id, sakura=False, *args, **kwargs):
        super().__init__(api, team, *args, **kwargs)
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

        from core.database import static_lib

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
