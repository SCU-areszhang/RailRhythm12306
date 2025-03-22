import requests
import json
import re

def get_train_no(key):
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Connection": "keep-alive",
        "Cookie": "_big_fontsize=0; guidesStatus=off; highContrastMode=defaltMode; cursorStatus=off; BIGipServerpool_restapi=2313224714.44582.0000",
        "Host": "search.12306.cn",
        "Referer": "https://kyfw.12306.cn/",
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0"
    }
    url = "https://search.12306.cn/search/v1/h5/search"
    params = {"callback": "jQuery19104341730539493107_1742625763636", "keyword": key}
    resp = requests.get(url, params=params, headers=headers)
    if resp.status_code != 200:
        return "error"
    pattern = re.compile(r'\((.*)\)')
    match = pattern.search(resp.text)
    if match:
        json_str = match.group(1)
        try:
            data = []
            data_dict = json.loads(json_str)["data"]
            # print(data_dict)
            if data_dict:
                # print(data_dict)
                for train in data_dict:
                    data.append(train["params"])
                # print(data)
                return data
            else:
                return "empty"
        except json.JSONDecodeError as e:
            return "error"
    else:
        return "empty"
# test
res = get_train_no("G1")
print(res)