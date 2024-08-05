import random

def randomDomain():
    bili_api = [
        'api.bilibili.com',
        'api.biliapi.com',
        'api.biliapi.net'
    ]
    base_url = random.choice(bili_api)
    return base_url