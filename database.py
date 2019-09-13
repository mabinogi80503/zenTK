import json

import attr

from colorama import Fore

from common import singleton
from datatype import Sword, Equipment


@attr.s
class DataMap(object):
    dictionary = attr.ib(factory=dict)

    @classmethod
    def from_json(cls, path, datatype):
        dictionary = {}
        with open(path, encoding="utf-8") as f:
            for key, data in json.load(f).items():
                dictionary[key] = datatype.from_json(data)
        return cls(dictionary)

    def get(self, id):
        return self.dictionary.get(id)


@attr.s
class SwordData(object):
    """
    表示刀男固定的資訊
    """

    name = attr.ib()

    @classmethod
    def from_json(cls, data):
        return cls(data["name"])


@attr.s
class EquipmentData(object):
    """
    表示刀裝固定的資訊
    """

    name = attr.ib()
    soilder = attr.ib(converter=int)

    @classmethod
    def from_json(cls, data):
        return cls(data["name"], data["soilder"])


@attr.s
class GuardPoints(object):
    points = attr.ib()

    @classmethod
    def from_json(cls, data):
        return cls(data)

    def get_points(self):
        return self.points


@singleton
class TkrbStaticLibrary(object):
    def __init__(self):
        self.sword_map = DataMap.from_json("swords.json", SwordData)
        self.equipment_map = DataMap.from_json("equipments.json", EquipmentData)
        self.guard_points = DataMap.from_json("guard_map.json", GuardPoints)

    def get_sword(self, id):
        return self.sword_map.get(id)

    def get_equipment(self, id):
        return self.equipment_map.get(id)

    def get_mapid_before_boss(self, episode, field):
        map_id = f"{episode}-{field}"
        return self.guard_points.get(map_id)


class UserLibrary(object):
    def __init__(self, api):
        self.api = api

        # Serial ID 映射到對應的實體
        self.sword_map = {}
        self.equipment_map = {}

        self.api.subscribe("party_list", self.update_from_party_list)

    def get_sword(self, id):
        return self.sword_map.get(id)

    def get_equipment(self, id):
        return self.equipment_map.get(id)

    def update_data(self, tgt_list, tgt_type, data):
        for serial, inner_data in data.items():
            ref = tgt_list.get(serial)
            if ref:
                tgt_list[serial] = tgt_type.from_old_one(ref, inner_data)
            else:
                tgt_list[serial] = tgt_type.from_json(static_lib, inner_data)

    def update_sword(self, serial, new):
        if serial in self.sword_map.keys() and new is None:
            del self.sword_map[serial]
            return

        if isinstance(new, Sword):
            self.sword_map[serial] = new

    def update_equipment(self, serial, new):
        if serial in self.equipment_map.keys() and new is None:
            del self.equipment_map[serial]
            return

        if isinstance(new, Equipment):
            self.equipment_map[serial] = new

    def update_swords(self, data):
        self.sword_map.clear()
        for serial, innerdata in data.items():
            self.sword_map[serial] = Sword.from_json(static_lib, innerdata)

    def update_equipments(self, data):
        self.equipment_map.clear()
        for serial, innerdata in data.items():
            self.equipment_map[serial] = Equipment.from_json(static_lib, innerdata)

    def update_from_party_list(self, data):
        sword_data = data.get("sword")
        if sword_data:
            self.update_swords(sword_data)
        else:
            print(Fore.RED + "無法取得 sword 資料！")

        equipment_data = data.get("equip")
        if equipment_data:
            self.update_equipments(equipment_data)
        else:
            print(Fore.RED + "無法取得 equip 資料！")


static_lib = TkrbStaticLibrary()
