from functools import wraps

import requests

from .exceptions import APICallFailedException
from .notification import Publisher


def update_token(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        ret = func(self, *args, **kwargs)
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException(func.__name__)

    return wrapper


def notify_subject(name):
    def outside(func):
        def wrapper(self, *args, **kwargs):
            ret = func(self, *args, **kwargs)
            if ret["status"] == 0:
                self.boardcast(name, ret)
            return ret

        return wrapper

    return outside


class TkrbApi(Publisher):
    def __init__(self, url, user_id, cookie, token):
        super().__init__()

        self.session = requests.session()
        self.server_url = url
        self.user_id = user_id

        self.params = {"uid": self.user_id}
        self.payload = {"sword": cookie, "t": token}
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/72.0.3626.119 Safari/537.36",
        }

        self.create_event("start")
        self.create_event("home")
        self.create_event("party_list")
        self.create_event("sally")
        self.create_event("set_sword")
        self.create_event("remove_sword")
        self.create_event("swap_team")
        self.create_event("battle_start")
        self.create_event("battle_end")

    def __del__(self):
        self.session.close()

    @notify_subject("set_sword")
    @update_token
    def set_sword(self, team, index, serial):
        url = "party/setsword"
        data = {"party_no": team, "serial_id": serial, "order": index}
        ret = self._request(url, data=data).json()
        return ret

    @notify_subject("remove_sword")
    @update_token
    def remove_sword(self, team, index, serial):
        url = "party/removesword"
        data = {"party_no": team, "order": index, "serial_id": serial}
        ret = self._request(url, data=data).json()
        return ret

    @notify_subject("swap_team")
    @update_token
    def swap_team(self, start, target):
        url = "party/partyreplacement"
        data = {"before_party_no": start, "after_party_no": target}
        ret = self._request(url, data=data).json()
        return ret

    @notify_subject("sally")
    @update_token
    def sally(self):
        url = "sally"
        ret = self._request(url).json()
        return ret

    @update_token
    def recover_event_cost(self, event_id, total):
        url = "sally/recovercost"
        data = {"event_id": event_id, "num": total}
        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def battle_back_to_home(self):
        url = "sally/homereturn"
        ret = self._request(url).json()
        return ret

    @update_token
    def battle(self, formation):
        url = "battle/battle"
        data = {"formation_id": formation}
        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def battle_foward(self):
        url = "sally/forward"
        data = {"direction": "0"}
        ret = self._request(url, data=data).json()
        return ret

    @notify_subject("battle_start")
    @update_token
    def battle_start(self, party, episode, field):
        url = "sally/sally"
        data = {"party_no": party, "episode_id": episode, "field_id": field}
        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def event_battle_start(
        self, event_id, party, field, event_layer_id=0, item_id=0, **kwargs
    ):
        url = "sally/eventsally"

        data = {
            "event_id": event_id,
            "party_no": party,
            "event_field_id": field,
        }

        if item_id != 0:
            data["item_id"] = item_id

        if event_layer_id != 0:
            data["event_layer_id"] = event_layer_id

        if kwargs:
            data = {**data, **kwargs}

        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def event_return(self, **kwargs):
        url = "sally/eventreturn"
        ret = self._request(url).json()
        return ret

    @update_token
    def event_forward(self, **kwargs):
        url = "sally/eventforward"
        data = kwargs
        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def forge_room(self):
        url = "forge"
        ret = self._request(url).json()
        return ret

    @update_token
    def forge_complete(self, slot):
        url = "forge/complete"
        data = {"slot_no": slot}
        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def forge_start(self, slot, steel, charcoal, coolant, files, use_assist=False):
        url = "forge/start"
        data = {
            "slot_no": slot,
            "steel": steel,
            "charcoal": charcoal,
            "coolant": coolant,
            "file": files,
            "use_assist": use_assist,
        }
        ret = self._request(url, data=data).json()
        return ret

    @notify_subject("party_list")
    @update_token
    def party_list(self):
        url = "party/list"
        ret = self._request(url).json()
        return ret

    @update_token
    def event_get_party_info(self):
        url = "party/get_sally_party_info"
        ret = self._request(url).json()
        return ret

    @update_token
    def complete_duty(self):
        url = "duty/complete"
        ret = self._request(url).json()
        return ret

    @update_token
    def go_conquest(self):
        url = "conquest"
        ret = self._request(url).json()
        return ret

    @update_token
    def start_conquest(self, field, party):
        url = "conquest/start"
        data = {"field_id": field, "party_no": party}
        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def receive_conquest_reward(self, party):
        url = "conquest/complete"
        data = {"party_no": party}
        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def alloutbattle(self, party):
        url = "battle/alloutbattle"
        data = {"party_no": party}
        ret = self._request(url, data=data).json()
        return ret

    @notify_subject("home")
    @update_token
    def home(self):
        url = "home"
        ret = self._request(url).json()
        return ret

    @notify_subject("start")
    @update_token
    def start(self):
        url = "login/start"
        ret = self._request(url).json()
        return ret

    @update_token
    def repair_room(self):
        url = "repair"
        ret = self._request(url).json()
        return ret

    @update_token
    def repair_start(self, serial, slot, use_assist=0):
        url = "repair/repair"
        data = {
            "serial_id": serial,
            "slot_no": slot,
            "use_assist": use_assist,
        }
        ret = self._request(url, data=data).json()
        return ret

    @update_token
    def repair_complete(self, slot):
        url = "repair/complete"
        data = {
            "slot_no": slot,
        }
        ret = self._request(url, data=data).json()
        return ret

    def update_payload(self, cookie=None, token=None, **kwargs):
        if cookie is not None:
            self.payload.update({"sword": cookie})

        if token is not None:
            self.payload.update({"t": token})

    def _request(self, url, data=None, **kwargs):
        full_data = None
        if data:
            from copy import deepcopy

            full_data = deepcopy(self.payload)
            full_data.update(data)
        else:
            full_data = self.payload

        full_url = self.server_url + url

        try:
            resp = self.session.request(
                method="POST",
                url=full_url,
                headers=self.headers,
                params=self.params,
                data=full_data,
                allow_redirects=False,
            )
        except ConnectionError:
            print("API 斷線！")

            from sys import exit

            exit(1)
        else:
            return resp
