import sqlite3

import attr
from colorama import Fore

from .datatype import Equipment, Sword
from .notification import Subscriber

DATA_SOURCE_FILENAME = "data.sqlite3"


@attr.s
class SwordData(object):
    serial = attr.ib(converter=str, default="不明")
    name = attr.ib(converter=str, default="不明")
    type = attr.ib(converter=str, default="不明")
    rare = attr.ib(converter=bool, default=False)

    @property
    def is_unknown(self):
        return self.serial == "不明"

    @classmethod
    def unknown(cls):
        return cls()

    @classmethod
    def from_raw(cls, data):
        return cls(data[0], data[1], data[2], data[3])


class SwordDatabase(object):
    def __init__(self, database=None):
        self.db = database

    def get(self, key):
        command = "SELECT * FROM swords WHERE id=?"

        cursor = self.db.cursor()
        data = cursor.execute(command, (key,)).fetchone()
        return SwordData.from_raw(data) if data else SwordData.unknown()

    @classmethod
    def build(cls, file_name):
        db = sqlite3.connect(f"file:{file_name}?mode=ro", uri=True)
        return cls(db)


@attr.s
class EquipmentData(object):
    serial = attr.ib(converter=str, default="不明")
    name = attr.ib(converter=str, default="不明")
    soilder = attr.ib(converter=int, default=0)

    @property
    def is_unknown(self):
        return self.serial == "不明"

    @classmethod
    def unknown(cls):
        return cls()

    @classmethod
    def from_raw(cls, data):
        return cls(data[0], data[1], data[2])


class EquipmentDatabase(object):
    def __init__(self, database=None):
        self.db = database

    def get(self, key):
        command = "SELECT * FROM equipments WHERE id=?"

        cursor = self.db.cursor()
        data = cursor.execute(command, (key,)).fetchone()
        return EquipmentData.from_raw(data) if data else EquipmentData.unknown()

    @classmethod
    def build(cls, file_name):
        db = sqlite3.connect(f"file:{file_name}?mode=ro", uri=True)
        return cls(db)


sword_data = SwordDatabase.build(DATA_SOURCE_FILENAME)
equipment_data = EquipmentDatabase.build(DATA_SOURCE_FILENAME)


class UserLibrary(object):
    def __init__(self, api):
        self.api = api

        # Serial ID 映射到對應的實體
        self.sword_map = {}
        self.equipment_map = {}
        self.api.registe(
            "party_list", Subscriber("UserLibrary", self.update_from_party_list)
        )

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
                tgt_list[serial] = tgt_type.from_json(inner_data)

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
            self.sword_map[serial] = Sword.from_json(innerdata)

    def update_equipments(self, data):
        self.equipment_map.clear()
        for serial, innerdata in data.items():
            self.equipment_map[serial] = Equipment.from_json(innerdata)

    def update_from_party_list(self, data):
        sword_info = data.get("sword")
        self.update_swords(sword_info)

        equipment_data = data.get("equip")
        self.update_equipments(equipment_data)
