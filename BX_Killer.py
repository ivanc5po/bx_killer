import time
import json
import hmac
import base64
import urllib.request
import websocket
import requests
import threading
import asyncio
import aiohttp
from aiohttp.client import ClientSession

setting = """
-------------------------------------------------------------------------------------------------------
APIKEY     : z3AQAxHyywMUSBzo3Ie7g3DLFny9lhMQRYFplwEp0Yoy5fqyRy1koxEAUuodBZxvCTOw7zOzKb9ycTVzJA2Q
SECRETKEY  : nnQLklDgeBvF5YLs3lYXqRD7UqYIdE0GoZqp70grMbNeRE5O20nhj3FCCQLfDe7OrQTdymcAbhMZMLPTEyEA

coin       : xrp
rate       : 0.2

mode       : s
-------------------------------------------------------------------------------------------------------
"""

APIURL = "https://api-swap-rest.bingbon.pro"
APIKEY = setting.split(": ")[1].split("\n")[0]
SECRETKEY = setting.split(": ")[2].split("\n")[0]

coin = setting.split(": ")[3].split("\n")[0].upper()
bx_symbol = coin+"-USDT"
bn_symbol = coin+"USDT"

rate = float(setting.split(": ")[4].split("\n")[0])
price_mode = setting.split(": ")[5].split("\n")[0].lower()

                
def Setting():
    global genSignature
    global post
    global get_balance
    global get_price
    global place_order
    global set_leverage
    global get_leverage

    def genSignature(path, method, paramsMap):
        sortedKeys = sorted(paramsMap)
        paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
        paramsStr = method + path + paramsStr
        return hmac.new(SECRETKEY.encode("utf-8"), paramsStr.encode("utf-8"), digestmod="sha256").digest()

    def post(url, body):
        req = urllib.request.Request(url, data=body.encode("utf-8"), headers={'User-Agent': 'Mozilla/5.0'})
        return json.loads(urllib.request.urlopen(req).read().decode("UTF-8").replace("'", '"'))

    def get_balance():
        paramsMap = {
            "apiKey": APIKEY,
            "timestamp": int(time.time()*1000),
            "currency": "USDT",
        }
        sortedKeys = sorted(paramsMap)
        paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
        paramsStr += "&sign=" + urllib.parse.quote(base64.b64encode(genSignature("/api/v1/user/getBalance", "POST", paramsMap)))
        url = "%s/api/v1/user/getBalance" % APIURL
        return post(url, paramsStr)

    def get_price(symbol):
        return requests.get("https://api-swap-rest.bingbon.pro/api/v1/market/getLatestPrice?symbol="+symbol).json()

    def place_order(symbol, side, price, volume, tradeType, action):
        paramsMap = {
            "symbol": symbol,
            "apiKey": APIKEY,
            "side": side,
            "entrustPrice": price,
            "entrustVolume": volume,
            "tradeType": tradeType,
            "action": action,
            "timestamp": int(time.time()*1000),
        }
        sortedKeys = sorted(paramsMap)
        paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
        paramsStr += "&sign=" + urllib.parse.quote(base64.b64encode(genSignature("/api/v1/user/trade", "POST", paramsMap)))
        url = "%s/api/v1/user/trade" % APIURL
        return post(url, paramsStr)
    
    def set_leverage(symbol, leverage):
        paramsMap = {
            "symbol": symbol,
            "apiKey": APIKEY,
            "side": "Long",
            "leverage": leverage,
            "timestamp": int(time.time()*1000),
        }
        sortedKeys = sorted(paramsMap)
        paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
        paramsStr += "&sign=" + urllib.parse.quote(base64.b64encode(genSignature("/api/v1/user/setLeverage", "POST", paramsMap)))
        url = "%s/api/v1/user/setLeverage" % APIURL
        post(url, paramsStr)

        paramsMap = {
            "symbol": symbol,
            "apiKey": APIKEY,
            "side": "Short",
            "leverage": leverage,
            "timestamp": int(time.time()*1000),
        }
        sortedKeys = sorted(paramsMap)
        paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
        paramsStr += "&sign=" + urllib.parse.quote(base64.b64encode(genSignature("/api/v1/user/setLeverage", "POST", paramsMap)))
        url = "%s/api/v1/user/setLeverage" % APIURL
        return post(url, paramsStr)

    def get_leverage(symbol):
        paramsMap = {
            "symbol": symbol,
            "apiKey": APIKEY,
            "timestamp": int(time.time()*1000),
        }
        sortedKeys = sorted(paramsMap)
        paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
        paramsStr += "&sign=" + urllib.parse.quote(base64.b64encode(genSignature("/api/v1/user/getLeverage", "POST", paramsMap)))
        url = "%s/api/v1/user/getLeverage" % APIURL
        return post(url, paramsStr)

bn_price = 0
fs = ""

if price_mode == "f":
    fs = "f"

oc_modes = ["Open", "Close"]
oc_num = 0
oc_mode = "Open"

def on_message(ws, message):
    global mode
    global x
    global amt

    data = json.loads(message)
    if data['e'] == 'trade':
        bn_price = float(data['p'])
        url_list = ["https://api-swap-rest.bingbon.pro/api/v1/market/getLatestPrice?symbol="+coin+"-USDT"]
        asyncio.run(download_all(url_list))
        print(bn_price, bx_price)
        if bn_price < bx_price and mode == "long":
            if place_order(symbol=bx_symbol, price=bx_price, action=oc_mode, volume=amt, side="Ask", tradeType="Market")["code"] == 0:
                oc_num = 1-oc_num
                oc_mode = oc_modes[oc_num]
                mode = "no"
                print(oc_mode+" long :", bx_price)
                balance = get_balance()["data"]["account"]["balance"]
                print("--------------------------------------")
                print("balance     :", balance)
                x *= 1.01
                amt = balance*get_leverage(symbol=bx_symbol)["data"]["longLeverage"]*x/bx_price
                
        if bx_price < bn_price and mode == "short":
            if place_order(symbol=bx_symbol, price=bx_price, action=oc_mode, volume=amt, side="Bid", tradeType="Market")["code"] == 0:
                oc_num = 1-oc_num
                oc_mode = oc_modes[oc_num]
                mode = "no"
                print(oc_mode+" short :", bx_price)
                balance = get_balance()["data"]["account"]["balance"]
                print("--------------------------------------")
                print("balance     :", balance)
                x *= 1.01
                amt = balance*get_leverage(symbol=bx_symbol)["data"]["longLeverage"]*x/bx_price

        if bn_price > bx_price*(1+rate/100) and mode == "no":
            if place_order(symbol=bx_symbol, price=bx_price, action=oc_mode, volume=amt, side="Bid", tradeType="Market")["code"] == 0:
                # oc_num = 1-oc_num
                # oc_mode = oc_modes[oc_num]
                mode = "long"
                print("======================================")
                print(oc_mode+" long :", bx_price)
            else:
                balance = get_balance()["data"]["account"]["balance"]
                leverage = get_leverage(symbol=bx_symbol)["data"]["longLeverage"]
                amt = balance*leverage*x/bx_price
                print("amt error")
                x *= 0.9
                
        if bx_price > bn_price*(1+rate/100) and mode == "no":
            if place_order(symbol=bx_symbol, price=bx_price, action=oc_mode, volume=amt, side="Ask", tradeType="Market")["code"] == 0:
                # oc_num = 1-oc_num
                # oc_mode = oc_modes[oc_num]
                mode = "short"
                print("======================================")
                print(oc_mode+" short :", bx_price)
            else:
                balance = get_balance()["data"]["account"]["balance"]
                leverage = get_leverage(symbol=bx_symbol)["data"]["longLeverage"]
                amt = balance*leverage*x/bx_price
                print("amt error")
                x *= 0.9

Setting()

balance = get_balance()["data"]["account"]["balance"]
def print_info():
    print("--------------------------------------")
    print("coin       :", coin)
    print("rate       :", rate)
    print("price mode :", price_mode)
    print("balance    :", balance)
    print("--------------------------------------")

async def download_link(url:str,session:ClientSession):
    global bx_price
    async with session.get(url) as response:
        result = await response.text()
        bx_price = float(json.loads(result)["data"]["tradePrice"])
        time.sleep(0.1)

async def download_all(urls:list):
    my_conn = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=my_conn) as session:
        tasks = []
        for url in urls:
            task = asyncio.ensure_future(download_link(url=url,session=session))
            tasks.append(task)
        await asyncio.gather(*tasks,return_exceptions=True)

x = 0.9
mode = "no"

url_list = ["https://api-swap-rest.bingbon.pro/api/v1/market/getLatestPrice?symbol="+coin+"-USDT"]
asyncio.run(download_all(url_list))

leverage = get_leverage(symbol=bx_symbol)["data"]["longLeverage"]
amt = balance*leverage*x/bx_price
print_info()
print("start !!!")

if bn_symbol == "LUNAUSDT":
    bn_symbol = "LUNA2USDT"
ws = websocket.WebSocketApp("wss://"+fs+"stream.binance.com/ws/"+bn_symbol.lower()+"@trade", on_message=on_message)
ws.run_forever()