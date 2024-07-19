import requests
import time
from loguru import logger


def get_timestamp():
    """
    获取秒级时间戳
    :return: int()
    """
    return int(time.time())


class FeishuAuth(object):
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self._app_secret = app_secret
        self._tenant_access_token = str()
        self._app_access_token = str()
        self._expired_at = int(0)

    @property
    def tenant_access_token(self):
        """
        获取 tenant_access_token
        :return:
        """
        if get_timestamp() > self._expired_at or len(self._tenant_access_token) < 2:
            self._authorize_access_token()
            logger.info(f'飞书AppInfo更新完成.{self._tenant_access_token}')
            logger.info(f'凭据到期时间: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._expired_at))}')
        return self._tenant_access_token

    @property
    def app_access_token(self):
        """
        获取 app_access_token
        :return:
        """
        if get_timestamp() > self._expired_at or len(self._app_access_token) < 2:
            self._authorize_access_token()
            logger.info(f'飞书AppInfo更新完成.{self._app_access_token}')
            logger.info(f'凭据到期时间: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._expired_at))}')
        return self._app_access_token

    def _authorize_access_token(self):
        # doc：https://open.feishu.cn/document/server-docs/authentication-management/access-token/app_access_token_internal
        url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
        req_body = {"app_id": self.app_id, "app_secret": self._app_secret}
        response = requests.post(url, req_body)
        self.check_error_response(response)
        self._tenant_access_token = response.json().get("tenant_access_token")
        self._app_access_token = response.json().get("app_access_token")
        self._expired_at = get_timestamp() + response.json().get("expire")

    @staticmethod
    def check_error_response(resp):
        # check if the response contains error information
        if resp.status_code != 200:
            resp.raise_for_status()
        response_dict = resp.json()
        code = response_dict.get("code", -1)
        if code != 0:
            raise LarkException(code=code, msg=response_dict.get("msg"))


class LarkException(Exception):
    def __init__(self, code=0, msg=None):
        self.code = code
        self.msg = msg

    def __str__(self) -> str:
        return "{}:{}".format(self.code, self.msg)

    __repr__ = __str__
