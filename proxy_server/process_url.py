"""
根据 URL 进行不同的处理
"""

import json
import urllib.parse

import mitmproxy.http

from mylogger import logger
from settings import settings
from wqbook import WQBook, SplitPageOrder


class WQBookAddon:

    def __init__(self) -> None:
        self.wqbook_pool: dict[int, WQBook] = {}
        "记录需要下载的书籍，key 是书籍 ID"
        self.downloaded_book: set[int] = set()
        "记录已经下载过的书籍，key 是书籍 ID"
        self.split_page_order = SplitPageOrder()
        "记录小图片的下载顺序"

        self._init_wqbook_pool()
        pass

    def _init_wqbook_pool(self) -> None:
        """读取 settings 文件，确认要下载哪些 book"""
        for book_id in settings["book_id"]:
            self.wqbook_pool[book_id] = WQBook(book_id)

    # region 下面是 mitmproxy 规定的各种方法

    async def response(self, flow: mitmproxy.http.HTTPFlow) -> None:
        """对响应进行拦截，根据 URL 转发到各个方法进行处理"""
        req_url = flow.request.pretty_url
        body = flow.response.content

        # 小图片的请求
        if settings["api"]["split_page"] in req_url:
            await self.process_req_split_page(req_url, body)

        # 小图片之前的请求
        elif settings["api"]["req_before_split_page"] in req_url:
            await self.process_req_before_split_page(req_url, body)

        # 书籍信息请求
        elif settings["api"]["book_info"] in req_url:
            await self.process_book_info(req_url, body)

        # 书签请求
        elif settings["api"]["bookmark"] in req_url:
            await self.process_bookmark(req_url, body)

    # endregion

    #############################################################

    # region 下面是自定义的各种方法

    async def filter_book(self, bid: int, page_num: int | None = None) -> bool:
        """是否需要过滤该书籍、或者该书籍某一页的处理"""
        # 不需要处理该书籍
        if bid not in self.wqbook_pool:
            return True

        # 该书籍已经下载过了
        if bid in self.downloaded_book:
            return True

        # 该书籍的这一页已经下载过了
        if page_num and self.wqbook_pool[bid].is_page_downloaded(page_num):
            return True

        return False

    async def process_book_info(self, url: str, body: bytes):
        """处理书籍信息，比如书籍名称、总页数、作者名等等"""
        # url 形如 https://wqbook.wqxuetang.com/api/v7/read/initread?bid=3238891
        query = urllib.parse.parse_qs(url.split("?")[1])
        bid = int(query["bid"][0])

        if await self.filter_book(bid):
            return

        json_data = json.loads(body.decode())
        # 具体格式根据网站的响应格式进行编写
        data = json_data["data"]

        author = data["author"]
        book_name = data["name"]
        book_total_page = data["pages"]

        logger.info(
            f"书籍 <{bid}> - <{book_name}>，作者 <{author}>，总页数 <{book_total_page}>"
        )
        self.wqbook_pool[bid].add_book_info(author, book_name, book_total_page)

    async def process_req_before_split_page(self, url: str, body: bytes):
        """处理访问小图片之前的 6 个请求，为后续确认小图片的顺序做准备"""
        # url 形如 https://wqbook.wqxuetang.com/deep/page/once/get?bid=3238891&pnum=3&k=jwt加密的字符串
        query = urllib.parse.parse_qs(url.split("?")[1])
        bid = int(query["bid"][0])  # 书籍 ID
        page_num = int(query["pnum"][0])  # 访问的页码

        if await self.filter_book(bid, page_num):
            return

        # 解析 k 值，确认它是访问哪本书的、某一页的第几个小图片，并且保存映射关系！
        # 因为 k 值解析后的内容就包括了书籍的 id、访问的第几页等等，
        # 故不需要解析整个 url 来获取书籍 id 哟
        k = query["k"][0]
        data = json.loads(body.decode())
        self.split_page_order.add(k, data["data"])

    async def process_req_split_page(self, url: str, body: bytes):
        """处理 6 个小图片的请求"""
        # url 形如 https://wqbook.wqxuetang.com/deep/page/lmg/3238891/3?k=jwt加密的字符串
        parsed_url = urllib.parse.urlparse(url)

        # parsed_url.path 形如 '/deep/page/lmg/3238891/3'，主要提取出 bid 和 page_num
        path = parsed_url.path.split("/")
        bid = int(path[-2])  # 书籍 ID
        page_num = int(path[-1])  # 访问的页码

        if await self.filter_book(bid, page_num):
            return

        query = urllib.parse.parse_qs(parsed_url.query)
        # 解析 k 值，确认它是访问哪本书的、某一页，然后通过查表获取该小图片的顺序！
        k = query["k"][0]

        # 获取该小图片的顺序
        order = self.split_page_order.get(k)
        # 没有获取到小图片的信息，则忽略该请求了
        if order == -1:
            return

        logger.debug(f"处理小图片 - 书籍 <{bid}>，页码 <{page_num}>，顺序 <{order}>")

        # 给书籍的这一页添加小图片，如果添加了 6 个小图片后会自动合成、保存这一页
        # 并且如果已经达到了最大页数，说明 PDF 已经下载完成
        is_complete = self.wqbook_pool[bid].add_split_page(page_num, order, body)
        if is_complete:
            logger.info(f"好耶！书籍 <{bid}> 已经下载完成，正在生成 PDF . . .")
            self.downloaded_book.add(bid)
            self.wqbook_pool.pop(bid)

    async def process_bookmark(self, url: str, body: bytes):
        """处理书签"""
        # url 形如 https://wqbook.wqxuetang.com/deep/book/v1/catatree?bid=3238891
        query = urllib.parse.parse_qs(url.split("?")[1])
        bid = int(query["bid"][0])

        if await self.filter_book(bid):
            return

        json_data = json.loads(body.decode())
        bookmark = json_data["data"]

        self.wqbook_pool[bid].add_bookmark(bookmark)

    # endregion

    pass


addons = [WQBookAddon()]
