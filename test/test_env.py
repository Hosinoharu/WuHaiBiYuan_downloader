"""
测试环境配置是否正确。
"""

print("\n . . . 测试整个代理环境 . . .\n")


def request(flow):
    method = flow.request.method
    url = flow.request.url
    print(f"{method} | {url[:50]} . . .")
