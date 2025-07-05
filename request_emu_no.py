import requests
import time

def get_emu_no(train_number):
    time.sleep(1)
    url = "https://api.rail.re/train/" + train_number
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Connection": "keep-alive",
        "Host": "api.rail.re",
        "Origin": "https://rail.re",
        "Referer": "https://rail.re/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"
    }
    response = requests.get(url, headers=headers)
    # 检查响应状态码
    response.raise_for_status()
    if not response.json():
        return {
            "date": "",
            "emu_no": "unknown",
            "type": "unknown",
            "train_number": train_number,
        }
    # 解析 JSON 响应
    no = response.json()[0]
    # no['date'], x = no['date'].split(' ')
    no['type'] = no['emu_no'][:-4]
    return no

if __name__ == '__main__':
    code = input("Input train numbers: ")
    train_type = get_emu_no(code)
    print(train_type)
