import requests
import json
from models_and_keys import keys, urls
def generate_text(prompt, assistant_enable, md_enable=False, enter_enable=False,
                  content="", model="deepseek-v3-250324", max_tokens=1000,
                  temperature=0.7, word_limit=-1, history=[]):
    url = urls[model]
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + keys[model]
    }
    if not md_enable and assistant_enable:
        prompt = "去除markdown格式 " + prompt
    if not enter_enable and assistant_enable:
        prompt = "去除换行符用纯文本回复 " + prompt
    if word_limit != -1 and assistant_enable:
        prompt = "控制回复字数在" + str(word_limit) + "字以内 " + prompt
    # 构建消息历史
    messages = [{"role": "system", "content": content}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    data = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    # 发送请求
    response = requests.post(url, headers=headers, data=json.dumps(data))
    # 处理响应
    if response.status_code == 200:
        result = response.json()
        response_message = result["choices"][0]["message"]
        # 将本次对话加入历史
        history.append({"role": "user", "content": prompt})
        history.append(response_message)
        return {"status": "success", "text": response_message["content"], "history": history}
    else:
        return {"status": "error", "text": "null", "history": history}

chinese_char = '，。、？！；：“”‘’（）【】《》'
chinese_char_not_head = '，。？！】”’）》'

def text_enter(text, line_char_limit=50):
    result = []
    current_line_length = 0
    text = text.replace('\n', '')
    for i, char in enumerate(text):
        # 判断字符类型（中文/全角符号占2个字符）
        if (('\u4e00' <= char <= '\u9fff') or ('\uff01' <= char <= '\uff5e') or
            (char in '，。、？！；：“”‘’（）【】《》')):
            char_length = 2
        else:
            char_length = 1
        if current_line_length + char_length > line_char_limit:
            if char in chinese_char_not_head:
                result.append(char)
                result.append('\n')
                current_line_length = 0
            else:
                result.append('\n')
                result.append(char)
                current_line_length = char_length
        else:
            result.append(char)
            current_line_length += char_length
    # 把result转换为字符串
    text = ''.join(result)
    return text
