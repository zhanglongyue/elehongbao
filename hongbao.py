import configparser
import datetime
import json
import logging
import os
import re
import threading
import time
from logging.handlers import RotatingFileHandler
from urllib.parse import unquote
import itchat
import requests
import threadpool as threadpool
from itchat.content import *

Rthandler = RotatingFileHandler('hongbao.log', maxBytes=50 * 1024 * 1024, backupCount=1)
Rthandler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%m/%d/%Y %H:%M:%S %p')
Rthandler.setFormatter(formatter)
logging.getLogger('').addHandler(Rthandler)


class User:
    def __init__(self, type: str) -> None:
        super().__init__()
        self.cookies = {}
        self.nick_name = conf.get(type, 'nickname') + str(int(time.time()))
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
        print(json)
        try:
            self.count = len(json['promotion_records'])
        except Exception as e:
            logging.error('promotion_records count' + str(e))

    def __format__(self) -> str:
        try:
            msg = []
            [msg.append({i['sns_username']: i['amount']}) for i in self.json['promotion_records']]
        except Exception as e:
            logging.error('promotion_records msg create' + str(e))
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), threading.currentThread().name, \
               "监控数%d 红包%s 进度%d/%d 信息%s" % (len(hongbao_array), self.sn, self.count, self.lucky_num, str(msg))


def hongbao_query(hongbao: HongBao):
    global prt_process
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
                if prt_process:
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
    except Exception as e:
        logging.error(str(e))


# 领取红包，该方法将使用需要获得大红包的用户cookie
def hongbao_get(hongbao: HongBao):
    session = requests.session()
    content = session.post('https://h5.ele.me/restapi/marketing/promotion/weixin/%s' % (get_user.openid),
                           cookies=get_user.cookies, data=request_data(get_user, hongbao)).content
    content = str(content, "utf-8")
    hongbao.update(json.loads(content))
    session.close()


def request_data(user, hongbao):
    return '{"method": "phone", "group_sn":"%s", "sign": "%s", "phone": "",' \
           '"device_id": "", "hardware_id": "", "platform": 0, "track_id": "undefined",' \
           '"weixin_avatar": "%s","weixin_username": "%s", "unionid": "%s","latitude":"","longitude":""}' \
           % (hongbao.sn, user.sign, user.weixin_avatar, user.nick_name, user.unionid)


def hongbao_finder(msg):
    global prt_process
    if "饿了么拼手气" in str(msg) and msg.Type == 'Sharing':
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
        except Exception as e:
            prt_send("不是正确的饿了么拼手气红包!")
            logging.error(str(e))

    if "ele进度" in str(msg):
        prt_process = not prt_process


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
    try:
        cur_path = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(cur_path, 'config.ini')
        conf = configparser.RawConfigParser()
        conf.read(config_path, encoding="utf8")

        # 微信是否打印进度
        prt_process = True
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
    except Exception as e:
        logging.error(str(e))
