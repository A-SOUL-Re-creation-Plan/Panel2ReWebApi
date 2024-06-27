import json
import os
import sys
import time

from flask import Flask, request, redirect, Response
from flask_restful import Api, Resource
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
from loguru import logger
from urllib.parse import quote

from bili.bili_wbi import getWBI
from bili.bili_api import BiliApis
from as_config import *
from feishu.calendar import TenantAccessToken, FeishuCalendar
from feishu.user import User
from utils import ColorConverter

app = Flask(__name__)
CORS(app)
api = Api(app)
version = 'V0.0.1_51e2b13'

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
bili_apis = None

feishu_app = None
feishu_app_id = str()
feishu_userAuthApiAddr = str()


def loadLarkBotConfig():
    global feishu_app, feishu_app_id, feishu_userAuthApiAddr
    if (os.path.exists('lark_bot.json')):
        with open('lark_bot.json', 'r') as f:
            bot_conf = json.load(f)
            app_id = bot_conf.get('app_id')
            feishu_app_id = app_id
            app_secret = bot_conf.get('app_secret')
            feishu_userAuthApiAddr = bot_conf.get('lark_userCallbackURI')
            feishu_app = TenantAccessToken(app_id, app_secret)
            logger.info("飞书AppInfo实例化完成")
            f.close()
        return
    else:
        logger.warning("飞书企业自建应用凭据读取失败，相关功能可能出现异常。")


def importBiliCookie():
    """
    加载基本鉴权信息，调用API使用
    """
    global bili_cookie, related_user_id
    if os.path.exists('user_data.json'):
        with open('user_data.json', 'r') as f:
            bili_cookie = json.loads(f.read())
            bili_cookie = bili_cookie[list(bili_cookie.keys())[0]]
            logger.info("从JSON文件导入cookies")
    elif os.path.exists('cookies.txt'):
        with open('cookies.txt', 'r') as f:
            logger.info("从原始raw字符串导入cookies")
            cookie_raw = f.read()
            cookie_raw = cookie_raw.split('; ')
            for cookie in cookie_raw:
                cookie = cookie.split('=')
                bili_cookie[cookie[0]] = cookie[1]
    else:
        logger.error("找不到符合的Cookies文件")
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
        pn = request.args.get('pn')
        ps = request.args.get('ps')
        status = request.args.get('status')
        return bili_apis.get_member_video_list(page=pn, size=ps, targer_type=status)


class GetFeishuOrgCalendarList(Resource):
    def get(self):
        '''
        飞书机器人关联组织公共日历事件列表获取
        request-config lark_bot.json:飞书自建机器人的app_id与app_secret键值
        '''
        lark_cal = list()
        calendar_id = json.loads(open('lark_bot.json', 'r').read()).get('lark_calendarID')
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        firstDay = str(int((now - timedelta(days=now.weekday())).timestamp()))
        # firstDay = str(int((now - timedelta(days=now.weekday()) - timedelta(days=50)).timestamp())) # For Debug
        endDay = str(int((now + timedelta(days=7 - now.weekday())).timestamp()))
        lark_calRaw = FeishuCalendar(feishu_app, calendar_id).get_event_list(start_timestamp=firstDay,
                                                                             end_timestamp=endDay)
        '''
        提取API元数据并返回
        '''
        for i in lark_calRaw:
            a = lark_cal_color.get(ColorConverter.int32ToHex(i.get('color')))
            c = as_color.get(a)
            s = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(int(i.get('start_time').get('timestamp'))))
            e = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(int(i.get('end_time').get('timestamp'))))
            lark_cal_item = {
                'color': c,
                'live_title': i.get('description').replace('\n', ''),
                'title': i.get('summary'),
                'start': s,
                'end': e,
                'url': 'https://live.bilibili.com/' + as_liveroom.get(a),
                'live_owner': as_e2c.get(a),
                'live_owner_room': as_liveroom.get(a),
                'live_owner_space': as_space.get(a),
                'live_owner_full': as_e2bn.get(a)
            }
            if "双播" in i.get('summary') or '&' in i.get('summary'):
                name1, name2 = i.get('summary')[0:2], i.get('summary')[3:5]
                if (name1 == as_e2c.get(a)):
                    partner = as_c2e.get(name2)
                else:
                    partner = as_c2e.get(name1)
                lark_cal_item['partner'] = {
                    'partner_short': as_e2c.get(partner),
                    'partner_full': as_e2bn.get(partner),
                    'partner_space': as_space.get(partner),
                    'partner_liveroom': as_liveroom.get(partner)
                }
            lark_cal.append(lark_cal_item)
        return lark_cal


class GetPubArchiveDetail(Resource):
    def get(self):
        bvid = request.args.get('bvid')
        return bili_apis.get_member_info(bvid=bvid)


class GetVersion(Resource):
    def get(self):
        return version


class GetPubArchiveFailMsg(Resource):
    def get(self):
        return {
            'msg': bili_apis.get_rejection_reason(bvid=request.args.get('bvid'))
        }


class GetFeishuUserAuthURI(Resource):
    def get(self):
        return_uri = str()
        x_f_f = request.headers.get('X-Forwarded-For')
        if x_f_f:
            if(x_f_f == '127.0.0.1'):
                return_uri = 'http://127.0.0.1:1213/api/lark_user_callback'
            return_uri = feishu_userAuthApiAddr
        else:
            return_uri = 'http://127.0.0.1:1211/api/lark_user_callback'
        uri = f'https://open.feishu.cn/open-apis/authen/v1/authorize?app_id={feishu_app_id}&redirect_uri={return_uri}'
        return {
            'u_auth_uri': uri
        }


class GetFeishuLoginCallback(Resource):
    def get(self):
        if request.args.get('error'):
            return redirect('/', code=302)
        code = request.args.get('code') if request.args.get('code') else ''
        data = '<script>location.replace("/#/user/lark_sso_callback?code=' + code + '")</script>'
        resp = Response(data)
        resp.headers['Content-Type'] = 'text/html;charset=utf-8'
        return resp


class GetFeishuUserInfo(Resource):
    def get(self):
        if request.args.get('error') == 'access_denied':
            return {
                'code': 403,
                'data': 'LARK_ACCESS_DENIED',
            }
        code = request.args.get('code')
        u = User(app=feishu_app)
        u.codeResolve(code)
        return {
            'code': 0,
            'data': u.getUserInfo()
        }


api.add_resource(GetBiliList, '/bili_dynamic')
api.add_resource(GetVersion, '/version')
api.add_resource(GetBiliDynamic, '/bili_dynamics')
api.add_resource(GetASWeeklySchedule, '/weekly_schedule')
api.add_resource(GetPubArchiveList, '/bili_archives')
api.add_resource(GetPubArchiveDetail, '/bili_archives_detail')
api.add_resource(GetPubArchiveFailMsg, '/bili_xcode_msg')
api.add_resource(GetFeishuOrgCalendarList, '/lark_calendar_list')
api.add_resource(GetFeishuUserAuthURI, '/lark_auth_uri')
api.add_resource(GetFeishuUserInfo, '/lark_identity')
api.add_resource(GetFeishuLoginCallback, '/lark_user_callback')


# api.add_resource(proxyBiliImage, '/bili_img_proxy')

@app.route('/')
def index():
    return 'Panel2Re is running.\n%s<br/>It works, but why?' % version


if __name__ == '__main__':
    importBiliCookie()
    loadLarkBotConfig()
    bili_apis = BiliApis(headers=bili_headers, cookies=bili_cookie)
    app.run(host='0.0.0.0', port=3007, debug=True)
