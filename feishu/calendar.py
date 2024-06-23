import time
import requests
import json


def get_timestamp():
    """
    获取秒级时间戳
    :return: int()
    """
    return int(time.time())

class TenantAccessToken(object):
    def __init__(self, app_id, app_secret):
        self._app_id = app_id
        self._app_secret = app_secret
        self._tenant_access_token = str()
        self._timestamp = int(0)
        try:
            with open('cache/lark_tat.json', 'r') as f:
                tat = json.load(f)
                self._tenant_access_token = tat.get('tat')
                self._timestamp = tat.get('ts')
        except:
            open('cache/lark_tat.json','w').write('{}')

    @property
    def tenant_access_token(self):
        """
        获取 tenant_access_token
        :return:
        """
        if (get_timestamp() - self._timestamp) > 600 or len(self._tenant_access_token) < 2:
            self._authorize_tenant_access_token()
        return self._tenant_access_token

    def _authorize_tenant_access_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        req_body = {"app_id": self._app_id, "app_secret": self._app_secret}
        response = requests.post(url, req_body)
        self.check_error_response(response)
        self._tenant_access_token = response.json().get("tenant_access_token")
        self._timestamp = get_timestamp()
        with open('cache/lark_tat.json', 'w') as f:
            cacheObj = {
                'tat': self._tenant_access_token,
                'ts': self._timestamp
            }
            f.write(json.dumps(cacheObj))

    @staticmethod
    def check_error_response(resp):
        # check if the response contains error information
        if resp.status_code != 200:
            resp.raise_for_status()
        response_dict = resp.json()
        code = response_dict.get("code", -1)
        if code != 0:
            raise LarkException(code=code, msg=response_dict.get("msg"))
class FeishuCalendar(object):
    def __init__(self, feishu_app: TenantAccessToken, calendar_id):
        self.app = feishu_app
        self.calendar_id = calendar_id

    def get_event_list(self, start_timestamp: str, end_timestamp: str, clear_canceled: bool = True):
        """
        查询日程列表
        :param start_timestamp: 开始时间 秒级时间戳
        :param end_timestamp: 结束时间 秒级时间戳
        :param clear_canceled: 是否清除已经取消的日程 (True)
        :return: list 遵循飞书文档
        """
        event_list = list()
        url = "https://open.feishu.cn/open-apis/calendar/v4/calendars/{}/events".format(
            self.calendar_id
        )
        payload = {
            "start_time": start_timestamp,
            "end_time": end_timestamp
        }
        headers = {
            "Authorization": "Bearer " + self.app.tenant_access_token
        }
        resp = requests.get(url=url, params=payload, headers=headers)
        self.app.check_error_response(resp)
        got = resp.json().get("data").get("items")
        if got is not None:
            event_list = list(got)
            event_list = list(filter(lambda x: x is not None, event_list))
            if clear_canceled:
                self._clear_canceled_event(event_list)
            self._event_sort(event_list)
        return event_list

    @staticmethod
    def _clear_canceled_event(event_list: list):
        count = 0
        for i in range(0, len(event_list)):
            status = event_list[count].get("status")
            if status == "cancelled":
                event_list.pop(count)
            else:
                count += 1

    @staticmethod
    def _event_sort(event_list: list):
        timestamp = list()
        pos = 0
        for i in event_list:
            timestamp.append(i.get("start_time").get("timestamp"))
        timestamp = sorted(timestamp)
        for i in range(0, len(event_list)):
            num = timestamp.index(event_list[pos].get("start_time").get("timestamp"))
            if pos == num:
                timestamp[pos] += 'e'
                pos += 1
                continue
            else:
                t = event_list[pos]
                event_list[pos] = event_list[num]
                event_list[num] = t


class LarkException(Exception):
    def __init__(self, code=0, msg=None):
        self.code = code
        self.msg = msg

    def __str__(self) -> str:
        return "{}:{}".format(self.code, self.msg)

    __repr__ = __str__
