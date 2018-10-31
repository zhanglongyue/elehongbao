import configparser
import datetime
import json
import re
import threading
import traceback
from urllib.parse import unquote
import itchat, time
import os
import requests
import sys
import threadpool
from itchat.content import *


class User:
    def __init__(self, type: str) -> None:
        super().__init__()
        self.cookies = {}
        self.nick_name = conf.get(type, 'nickname')
        user_cookies = conf.get(type, 'cookies').replace(' ', '')
        for cookie in user_cookies.split(';'):
            cookie_split = cookie.split('=')
            cookie_key = cookie_split[0]
            cookie_val = cookie_split[1]
            self.cookies[cookie_key] = cookie_val
            if 'snsInfo' in cookie_key:
                self.sign = re.findall('(?<=eleme_key%22%3A%22).+?(?=%22%2C%22)', cookie_val)[0]
                self.openid = re.findall('(?<=openid%22%3A%22).+?(?=%22%2C%22)', cookie_val)[0]
                self.unionid = re.findall('(?<=unionid%22%3A%22).+?(?=%22%2C%22)', cookie_val)[0]
                self.weixin_avatar = unquote(re.findall('(?<=headimgurl%22%3A%22).+?(?=%22%2C%22)', cookie_val)[0])


class HongBao:
    def __init__(self, lucky_num, sn) -> None:
        super().__init__()
        self.lucky_num = lucky_num
        self.sn = sn
        self.count = 0

    def update(self, json):
        self.json = json
        self.count = len(json['promotion_records'])

    def __format__(self) -> str:
        msg = []
        [msg.append({i['sns_username']: i['amount']}) for i in self.json['promotion_records']]
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), threading.currentThread().name, \
               "监控数%d 红包%s 进度%d/%d 信息%s" % (len(hongbao_array), self.sn, self.count, self.lucky_num, str(msg))


def hongbao_query(hongbao: HongBao):
    global PRT_PROCESS
    try:
        session = requests.session()
        while True:
            content = session.post('https://h5.ele.me/restapi/marketing/promotion/weixin/%s' % (query_user.openid),
                                   cookies=query_user.cookies, data=request_data(query_user, hongbao)).content
            content = str(content, "utf-8")
            hongbao.update(json.loads(content))
            if get_user.nick_name in str(hongbao.json):
                prt_send("你已抢过该红包!", hongbao.__format__())
                hongbao_array.remove(hongbao.sn)
                break
            else:
                if PRT_PROCESS:
                    prt_send(hongbao.__format__())
                else:
                    print(hongbao.__format__())

                # 根据大红包进度做后续处理
                if hongbao.count == hongbao.lucky_num - 1:
                    # 下一个是大红包！
                    hongbao_get(hongbao)
                    hongbao_array.remove(hongbao.sn)
                    prt_send("获得大红包!", hongbao.__format__())
                    break
                elif hongbao.count >= hongbao.lucky_num:
                    hongbao_array.remove(hongbao.sn)
                    prt_send("最佳红包已被领取!", hongbao.__format__())
                    break
                elif hongbao.count < hongbao.lucky_num:
                    session.close()
                    time.sleep(SECONDS)
    except:
        traceback.print_exc(file=sys.stdout)


# 领取红包，该方法将使用需要获得大红包的用户cookie
def hongbao_get(hongbao: HongBao):
    session = requests.session()
    get_user['nickname'] = get_user['nickname'] + str(int(time.time()))
    content = session.post('https://h5.ele.me/restapi/marketing/promotion/weixin/%s' % (get_user.openid),
                           cookies=get_user.cookies, data=request_data(get_user, hongbao)).content
    content = str(content, "utf-8")
    hongbao.update(json.loads(content))
    print(hongbao.__format__())
    session.close()


def request_data(user, hongbao):
    return '{"method": "phone", "group_sn":"%s", "sign": "%s", "phone": "",' \
           '"device_id": "", "hardware_id": "", "platform": 0, "track_id": "undefined",' \
           '"weixin_avatar": "%s","weixin_username": "%s", "unionid": "%s"}' \
           % (hongbao.sn, user.sign, user.weixin_avatar, user.nick_name, user.unionid)


def hongbao_finder(msg):
    global PRT_PROCESS
    if "饿了么" in str(msg) and "红包" in str(msg):
        try:
            lucky_num = int(re.findall('(?<=第).+?(?=个)', str(msg))[0])
            sn = re.findall('(?<=;sn=).+?(?=&amp;)', str(msg))[0]
            hongbao = HongBao(lucky_num, sn)
            if sn not in hongbao_array:
                hongbao_array.add(hongbao.sn)
                requests = threadpool.makeRequests(hongbao_query, [([hongbao], None)])
                [pool.putRequest(req) for req in requests]
                prt_send("收到饿了么红包 幸运位%d 红包ID %s" % (hongbao.lucky_num, hongbao.sn))
            else:
                prt_send("已经在监控该红包 幸运位%d 红包ID %s" % (hongbao.lucky_num, hongbao.sn))
        except:
            prt_send("不是正确的饿了么拼手气红包!")
            traceback.print_exc(file=sys.stdout)

    if "ele进度" in str(msg):
        PRT_PROCESS = not PRT_PROCESS

def prt_send(msg, info=None):
    if msg != None:
        print(msg)
        itchat.send(str(msg), toUserName="filehelper")
    if info != None:
        print(info)
        itchat.send(str(info), toUserName="filehelper")


@itchat.msg_register([TEXT, MAP, CARD, NOTE, SHARING])
def text_reply(msg):
    hongbao_finder(msg)


@itchat.msg_register([TEXT, MAP, CARD, NOTE, SHARING], isGroupChat=True)
def text_reply(msg):
    hongbao_finder(msg)


if __name__ == '__main__':
    cur_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(cur_path, 'config.ini')
    conf = configparser.RawConfigParser()
    conf.read(config_path, encoding="utf8")

    # 微信是否打印进度
    PRT_PROCESS = True
    # 查询间隔时间
    SECONDS = conf.getint('base', 'seconds')
    # 默认线程池大小50
    pool = threadpool.ThreadPool(50)
    # 初始化查询红包信息的用户数据
    query_user = User('query')
    # 初始化领取大红包的用户数据
    get_user = User('get')

    hongbao_array = set([])
    itchat.auto_login(hotReload=True, enableCmdQR=False)
    itchat.run(True)
