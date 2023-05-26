import json
import ablator.utils.file as futils
import numpy as np

import pandas as pd

def test():
    # 创建一个包含字典的列表
    data = [
    ]

    # 将列表转化为 JSON 并写入文件
    with open('./data.json', 'w') as f:
        json.dump(data, f)


    # 在稍后的时间点，读取 JSON 文件
    with open('./data.json', 'r') as f:
        data = json.load(f)

    data.append({"test": 0})
    data.append({"test": 1})
    data.append({"test": 10})
    data.append(futils.dict_to_json({"df": pd.DataFrame(np.zeros(3))}))
    with open('./data.json', 'w') as f:
        json.dump(data, f)

    with open('./data.json', 'r') as f:
        data_from_file = json.load(f)

    print(data_from_file)

with open('/tmp/0.15829659330222678/results.json', 'r') as f:
    data_from_file = json.load(f)

    print(data_from_file["results"][0])
