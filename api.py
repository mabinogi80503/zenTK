import requests

from notification import Observable


class APICallFailedException(Exception):
    def __init__(self, msg):
        super().__init__(self)
        self.msg = msg

    def __str__(self):
        return f"API 呼叫者 {self.msg} 失敗"


class TkrbApi(object):
    def __init__(self, url, user_id, cookie, token):
        self.session = requests.session()
        self.server_url = url
        self.user_id = user_id

        self.params = {"uid": self.user_id}
        self.payload = {"sword": cookie, "t": token}
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/72.0.3626.119 Safari/537.36"
        }

        self.subjects = {
            "start": Observable(),
            "home": Observable(),
            "party_list": Observable(),
            "sally": Observable(),
            "set_sword": Observable(),
            "remove_sword": Observable(),
            "swap_team": Observable(),
            "battle_start": Observable(),
            "battle_end": Observable()
        }

    def __del__(self):
        self.session.close()

    def subscribe(self, target, func):
        if target in self.subjects.keys():
            self.subjects[target].subscribe(func)

    def set_sword(self, team, index, serial):
        url = "party/setsword"
        data = {"party_no": team, "serial_id": serial, "order": index}
        ret = self._request(url, data=data).json()

        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            self.subjects["set_sword"].notify(ret)
            return ret
        else:
            raise APICallFailedException("設定刀劍位置")

    def remove_sword(self, team, index, serial):
        url = "party/removesword"
        data = {"party_no": team, "order": index, "serial_id": serial}

        ret = self._request(url, data=data).json()

        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            self.subjects["remove_sword"].notify(ret)
            return ret
        else:
            raise APICallFailedException("移除刀劍位置")

    def swap_team(self, start, target):
        url = "party/partyreplacement"
        data = {"before_party_no": start, "after_party_no": target}
        ret = self._request(url, data=data).json()

        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            self.subjects["swap_team"].notify(ret)
            return ret
        else:
            raise APICallFailedException("交換兩隊隊伍")

    def sally(self):
        url = "sally"

        ret = self._request(url).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            self.subjects["sally"].notify(ret)
            return ret
        else:
            raise APICallFailedException("Sally")

    def recover_event_cost(self, event_id, total):
        url = "sally/recovercost"

        data = {"event_id": event_id, "num": total}
        ret = self._request(url, data=data).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("recover_event_cost")

    def battle_back_to_home(self):
        url = "sally/homereturn"

        ret = self._request(url).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("battle_back_to_home")

    def battle(self, formation):
        url = "battle/battle"

        data = {"formation_id": formation}
        ret = self._request(url, data=data).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("battle")

    def battle_foward(self):
        url = "sally/forward"

        data = {"direction": "0"}
        ret = self._request(url, data=data).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("battle_foward")

    def battle_start(self, party, episode, field):
        url = "sally/sally"

        data = {"party_no": party, "episode_id": episode, "field_id": field}
        ret = self._request(url, data=data).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            self.subjects["battle_start"].notify(None)
            return ret
        else:
            raise APICallFailedException("battle_start")

    def event_battle_start(self, event_id, party, field, event_layer_id=0, item_id=0, **kwargs):
        url = "sally/eventsally"

        data = {
            "item_id": item_id,
            "event_id": event_id,
            "party_no": party,
            "event_field_id": field,
            "event_layer_id": event_layer_id
        }

        if kwargs:
            data = {**data, **kwargs}

        ret = self._request(url, data=data).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("event_battle_start")

    def event_forward(self, **kwargs):
        url = "sally/eventforward"

        data = kwargs
        ret = self._request(url, data=data).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("event_forward")

    def forge_complete(self, req):
        url = "forge/complete"

        data = {"slot_no": req["slot"]}
        ret = self._request(url, data=data).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("forge_complete")

    def forge_start(self, slot, steel, charcoal, coolant, files, use_assist=False):
        url = "forge/start"

        data = {
            "slot_no": slot,
            "steel": steel,
            "charcoal": charcoal,
            "coolant": coolant,
            "file": files,
            "use_assist": use_assist
        }
        ret = self._request(url, data=data).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("forge_start")

    def party_list(self):
        url = "party/list"

        ret = self._request(url).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            self.subjects["party_list"].notify(ret)
            return ret
        else:
            raise APICallFailedException("party_list")

    def complete_duty(self):
        url = "duty/complete"

        ret = self._request(url).json()
        if not ret["status"]:
            self.update_payload(token=ret["t"])
            return ret
        else:
            raise APICallFailedException("complete_duty")

    def home(self):
        url = "home"

        ret = self._request(url).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            self.subjects["home"].notify(ret)
            return ret
        else:
            raise APICallFailedException("home")

    def start(self):
        url = "login/start"

        ret = self._request(url).json()
        if ret["status"] == 0:
            self.update_payload(token=ret["t"])
            self.subjects["start"].notify(ret)
            return ret
        else:
            raise APICallFailedException("home")

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

        resp = self.session.request(
            method="POST",
            url=full_url,
            headers=self.headers,
            params=self.params,
            data=full_data,
            allow_redirects=False)
        return resp


class TkrbLoginFailException(Exception):
    def __init__(self):
        super().__init__(self)

    def __str__(self):
        return "登入失敗"


class TkrbNoCommandException(Exception):
    def __init__(self, command):
        super().__init__(self)
        self.command = command

    def __str__(self):
        return f"{self.command} 不存在"
