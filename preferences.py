from pathlib import Path

subsystem_name = ("system", "battle")
preferences_file = Path("./configs/settings.json")


def check_name_valid(func):
    def wrapper(self, name, value):
        if not isinstance(name, str):
            raise TypeError("名稱型態錯誤！必須是字串！")

        if len(name) == 0:
            raise ValueError(f"錯誤：名稱空白！")

        if "." not in name:
            raise ValueError(f"錯誤：名稱錯誤！")

        arr = name.split(".", 1)
        if arr[0] not in subsystem_name:
            raise ValueError(f"錯誤：子系統 \"{arr[0]}\" 非允許名單")
        return func(self, name, value)

    return wrapper


def check_name_existed(func):
    def wrapper(self, name, *args, **kwargs):
        name = name.strip()
        if name not in self._configs:
            raise ValueError(f"子系統 {self.name} 不存在 {name} 界面！")
        return func(self, name, *args, **kwargs)

    return wrapper


class SubSystemConfig(object):
    def __init__(self, parent, name):
        self.name = name
        self._configs = {}

    def add(self, name, value):
        name = name.strip()
        self._configs[name] = value

    @check_name_existed
    def update(self, name, value):
        self._configs[name] = value

    @check_name_existed
    def get(self, key, default=None):
        return self._configs.get(key, default)

    def clear(self):
        self._configs.clear()

    def show(self):
        print(self.name)
        for key, value in self._configs.items():
            print(f"- {key} = {value}")
        print()


class PreferenceManager(object):
    def __init__(self):

        self._root = {}
        for sys_name in subsystem_name:
            self._root[sys_name] = SubSystemConfig(self, sys_name)

    def get(self, name):
        if name in self._root.keys():
            return self._root.get(name)
        else:
            raise ValueError(f"不存在 {name} 系統")

    def show(self):
        for sys in self._root.values():
            sys.show()

    @check_name_valid
    def add(self, name, value):
        arr = name.split(".", 1)
        subsys_config = self.get(arr[0])
        subsys_config.add(arr[1], value)

    @check_name_valid
    def update(self, name, value):
        arr = name.split(".", 1)
        subsys_config = self.self.get(arr[0])
        subsys_config.update(arr[1], value)

    def _clean_all_subsystem(self):
        for s in self._root.values():
            s.clear()

    def load_default(self):
        from sys import exit
        if not preferences_file.exists():
            print("錯誤：無法讀取設定！")
            exit(1)

        self._clean_all_subsystem()

        import json
        with preferences_file.open(mode="r") as f:
            try:
                data = json.loads(f.read())
            except json.decoder.JSONDecodeError:
                print("系統設定檔案分析錯誤！")
                exit(1)

        for name, value in data.items():
            try:
                self.add(name, value)
            except ValueError as valueerr:
                print(valueerr)
                exit(1)
            except TypeError as typeerr:
                print(typeerr)
                exit(1)

    @classmethod
    def default(cls):
        obj = cls()
        obj.load_default()
        return obj


preferences_mgr = PreferenceManager.default()
