from feishu.feishuapp import FeishuAuth, LarkException
import requests

class FeishuCalendar(object):
    def __init__(self, feishu_app: FeishuAuth, calendar_id):
        self.app = feishu_app
        self.calendar_id = calendar_id

    def get_event_list(self, start_timestamp: str, end_timestamp: str, clear_canceled: bool = True, user_access_token: str = None):
        """
        查询日程列表
        :param user_access_token: 用户凭据 使用用户态令牌获取日程
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
            "Authorization": "Bearer " + user_access_token
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
