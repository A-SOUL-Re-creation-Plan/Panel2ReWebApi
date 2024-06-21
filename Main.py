import json
import os
import sys

from flask import Flask, request
from flask_restful import Api, Resource
from flask_cors import CORS
import requests
from bili.bili_wbi import getWBI
from datetime import datetime
from as_config import *

app = Flask(__name__)
CORS(app)
api = Api(app)
version = 'V0.0.1_006b9ba6'
base_URL = 'http://127.0.0.1:3007'

bili_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.1.4.514 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com/",
    "Pregma": "no-cache",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    # "Cookie": "",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "",
    "Connection": "keep-alive"
}

bili_cookie = dict()
related_user_id = list()


def importBiliCookie():
    """
    加载基本鉴权信息，调用API使用
    """
    global bili_cookie, related_user_id
    if os.path.exists('user_data.json'):
        with open('user_data.json', 'r') as f:
            bili_cookie = json.loads(f.read())
            bili_cookie = bili_cookie[list(bili_cookie.keys())[0]]
            print("Import from JSON")
    elif os.path.exists('cookies.txt'):
        with open('cookies.txt', 'r') as f:
            print("Import from raw cookie string")
            cookie_raw = f.read()
            cookie_raw = cookie_raw.split('; ')
            for cookie in cookie_raw:
                cookie = cookie.split('=')
                bili_cookie[cookie[0]] = cookie[1]
    else:
        print("Cookie file not found")
        sys.exit(0)
    # 加载受信成员ID
    with open('dynamic_config.json', 'r', encoding='utf-8') as f:
        bili_dynamic = json.loads(f.read())
        for item in bili_dynamic:
            related_user_id.append(item.get('bili_uid'))


def getBiliUserInfo(bili_uid):
    """
    获取用户信息，缓存在本地
    :param bili_uid: UID
    :return: 从bili获取的原JSON
    """
    if bili_uid not in related_user_id:
        raise NotImplementedError('ERR_NOT_A-SOUL_RELATED')
    # 缓存在本地，24小时刷新时限
    if os.path.exists('./cache/bili_user_' + bili_uid + '.json') and (
            datetime.now().timestamp() - os.stat('./cache/bili_user_' + bili_uid + '.json').st_mtime <= 60 * 60 * 24):
        data = json.load(open('./cache/bili_user_' + bili_uid + '.json', 'r'))
    else:
        params = {
            'mid': bili_uid
        }
        params = getWBI(params)
        data = requests.get('https://api.bilibili.com/x/space/wbi/acc/info', params=params,
                            headers=bili_headers, cookies=bili_cookie).json()
        with open('./cache/bili_user_' + bili_uid + '.json', 'w') as f:
            json.dump(data, f)
            f.close()
    return data


# Not Safe
# class proxyBiliImage(Resource):
#     def get(self):
#         addr = request.args.get("img")
#         if re.search("https://i[0-9].hdslb.com/(jpg|webp|avif|png|gif)*", addr):
#             temp = addr.split('/')
#             filename = temp[len(temp) - 1]
#             # print(filename)
#             if os.path.exists('cache/' + filename):
#                 if os.stat('cache/' + filename).st_size == 0:
#                     os.remove('cache/' + filename)
#             if not os.path.exists('cache'):
#                 os.mkdir('cache')
#             if not (os.path.exists('cache/' + filename)):
#                 try:
#                     data = requests.get(addr, headers=bili_headers).content
#                 except Exception as e:
#                     return e
#                 with open('cache/' + filename, 'wb') as f:
#                     f.write(data)
#                     f.close()
#             with open('cache/' + filename, 'rb') as f:
#                 res = f.read()
#                 f.close()
#             resp = Response(res, mimetype='application/octet-stream')
#             return resp
#         else:
#             return "FAILED", 500


class GetBiliList(Resource):
    def get(self):
        """
        获取/刷新 dynamic_config中的用户的信息
        目前作用仅为刷新头像
        :return: 包含头像的信息
        """
        if not os.path.exists('dynamic_config.json'):
            open('dynamic_config.json', 'w').close()
        bili_dynamic = json.loads(open('dynamic_config.json', 'r', encoding='utf-8').read())
        if request.args.get("refresh") == '1':
            # shutil.rmtree('cache')
            # for i in bili_dynamic:
            #     print("deleted" + str(i["bili_uid"]))
            #     os.remove('bili_user_' + i['bili_uid'] + '.json')
            for root, dirs, files in os.walk('.'):
                for name in files:
                    if name.startswith('bili_user_'):
                        if name.endswith('.json'):
                            print(os.path.join(root, name))
                            os.remove(os.path.join(root, name))

        for i in bili_dynamic:
            # i['avatar'] = base_URL + "/bili_img_proxy?img=" + getBiliUserInfo(i['bili_uid'])['data']['face']
            i['avatar'] = getBiliUserInfo(i['bili_uid'])['data']['face']
            # time.sleep(3)
        return bili_dynamic


class GetBiliDynamic(Resource):
    def get(self):
        """
        获取动态信息
        request-param uid: 要获取的用户的UID
        request-param offset: 动态页数（偏置）
        """
        uid = request.args.get("uid")
        offset = ""
        if request.args.get("offset"):
            offset = request.args.get("offset")
        # 仅接受以下几个用户
        if uid in related_user_id:
            params = {
                'host_mid': uid,
                'offset': offset
            }
            data = json.loads(requests.get('https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space',
                                           headers=bili_headers, params=params, cookies=bili_cookie)
                              .text)
            print(data["code"])
            dynamic_items = data['data']
            return dynamic_items
        else:
            return {
                'errno': -1,
                'data': 'ERR_NOT_A-SOUL_RELATED'
            }, 403


class GetASWeeklySchedule(Resource):
    def get(self):
        if not os.path.exists('schedule_table.json'):
            open('schedule_table.json', 'w').close()
            print('schedule data file not exist')
            return {
                "code": -1,
                "data": []
            }, 200
        with open('schedule_table.json', 'r', encoding='utf8') as f:
            data = json.loads(f.read())
            s_data = []
            live_type = ['单播', 'A-SOUL团播', 'A-SOUL特别直播', '双播', '官方测试直播']
            for i in data:
                actor = as_e2c[i['room']]
                url = 'https://live.bilibili.com/' + as_liveroom[i['room']]
                color = as_color[i['room']]
                time = i['time']
                desc = ''
                s_type = int(i['type'])
                if s_type == 0:
                    desc = actor + live_type[s_type]
                elif s_type == 2:
                    desc = live_type[s_type]
                elif s_type == 3:
                    desc += actor + as_e2c[i['partner']] + live_type[s_type]
                else:
                    desc = live_type[s_type]
                desc += " - " + i['desc']
                append_data = {
                    'title': desc,
                    'url': url,
                    'color': color,
                    'start': time,
                    'live_type': s_type,
                    'live_room': as_e2c[i['room']],
                    'pure_title': i['desc'],
                    'fullname': as_e2bn[i['room']],
                    'space': as_space[i['room']]
                }
                if s_type == 3:
                    append_data['partner'] = {
                        'shortName': as_e2c[i['partner']],
                        'fullname': as_e2bn[i['partner']],
                        'space': as_space[i['partner']],
                        'liveRoom': as_liveroom[i['partner']]
                    }
                s_data.append(append_data)
            return {
                "code": 0,
                "data": s_data
            }, 200


class GetPubArchiveList(Resource):
    def get(self):
        params = {
            'pn': request.args.get('pn'),
            'ps': request.args.get('ps'),
        }
        data = json.loads(requests.get("https://member.bilibili.com/x/web/archives",headers=bili_headers,cookies=bili_cookie,params=params).text)
        return data["data"]


class GetVersion(Resource):
    def get(self):
        return version


api.add_resource(GetBiliList, '/bili_dynamic')
api.add_resource(GetVersion, '/version')
api.add_resource(GetBiliDynamic, '/bili_dynamics')
api.add_resource(GetASWeeklySchedule, '/weekly_schedule')
api.add_resource(GetPubArchiveList, '/bili_archives')


# api.add_resource(proxyBiliImage, '/bili_img_proxy')

@app.route('/')
def index():
    return 'Panel2Re is running.\nBackend version: %s' % version


if __name__ == '__main__':
    importBiliCookie()
    app.run(host='0.0.0.0', port=3007, debug=True)
