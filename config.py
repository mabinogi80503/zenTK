import attr


@attr.s(kw_only=True)
class AppConfig(object):
    debug = attr.ib(type=bool, default=False)
    battle_interval = attr.ib(type=float, default=0.0)

    @classmethod
    def from_json(cls, path):
        if not path or len(path) == 0:
            print("讀取程式基本設定出現問題！")

        with open(path, encoding="UTF-8") as f:
            import json
            config = json.load(f)

        return cls(debug=config["debug"] or False, battle_interval=config["battle_interval"] or 0.0)

    @classmethod
    def default(cls):
        return AppConfig.from_json("app_config.json")


@attr.s(kw_only=True)
class BattleConfig(object):
    grind_mode = attr.ib(default=False)
    battle_interval = attr.ib(type=float, default=0.0)

    @classmethod
    def from_json(cls, path):
        with open(path, encoding="utf-8") as f:
            import json
            data = json.loads(f.read())

        return cls(grind_mode=data.get("grind_mode", False))

    @classmethod
    def default(cls):
        return cls.from_json("battle_config.json")


app_config = AppConfig.default()
battle_config = BattleConfig.default()
