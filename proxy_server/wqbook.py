"""
基本的 class
"""

import json
import threading
from pathlib import Path
from io import BytesIO

from PIL import Image

import utils
from settings import settings
from mylogger import logger


class OnePage:
    """表示书籍一页的内容"""

    def __init__(self) -> None:
        self.added_pages: set[int] = set()
        "记录添加的小图片的顺序数字，当它的长度为 6 时，表示已经添加了 6 张小图片啦"
        self.split_pages: dict[int, bytes] = {}
        "一页由 6 个被分割后的图片组成，它们也是有顺序的"

    def add_split_page(self, index: int, image: bytes) -> None:
        """添加一个被分割后的图片"""
        if index < 0 and index > 6:
            logger.error(f"添加分割后小图片出错，其位置为: {index}（不在 [0, 5] 之间）")
            return

        self.split_pages[index] = image
        self.added_pages.add(index)

    def is_enough(self) -> bool:
        """判断是否已经有 6 张小图片啦"""
        return len(self.split_pages) == 6

    def save_full_page(self, filename: Path) -> None:
        """拼接 6 个小图片，并且保存为一张完整的图片"""
        # 根据顺序，将所有图片拼接在一起
        images = []  # 保存生成的 image 对象

        for i in range(6):
            # 根据 bytes 生成 image 对象
            img = Image.open(BytesIO(self.split_pages[i]))
            images.append(img)

        # 计算横向合并时、最终图片的宽高
        widths, heights = zip(*(image.size for image in images))
        total_width = sum(widths)
        max_height = max(heights)

        # 生成大图片，将其它小图片的内容绘制上去
        new_image = Image.new("RGB", (total_width, max_height))
        x_offset = 0
        for image in images:
            new_image.paste(image, (x_offset, 0))
            x_offset += image.size[0]

        # 压缩一下图片大小
        new_image.save(
            filename,
            format=settings["picture_format"],
            quality=settings["picture_quality"],
        )

    pass


class WQBook:
    """表示一本书籍"""

    def __init__(self, bid: int) -> None:
        self.bid = bid
        "书籍的 id"
        self.name = ""
        "书籍的名称，仅用于给最后生成的 PDF 命名"
        self.author = ""
        "书籍的作者，仅用于给最后生成的 PDF 命名"
        self.total_page = 0
        "书籍的总页数，仅用于判断是否下载完成"
        self.bookmark = ""
        "书籍的书签"

        self.pages: dict[int, OnePage] = {}
        "记录书籍的每一页"
        self.downloaded_page: set[int] = set()
        "记录已经下载过的页"

        self.images_path = self._init_images_path()
        "保存该书籍所有图片的目录"

    def _init_images_path(self) -> Path:
        path = settings["image_path"] / f"{self.bid}"
        is_exist = path.exists()
        path.mkdir(parents=True, exist_ok=True)

        if not is_exist:
            return path

        # 查看该目录下面已经下载了多少图片
        downloaded_imgs = utils.get_imgs_files(path, suffix=settings["picture_format"])
        for img in downloaded_imgs:
            page_num = int(img.stem)
            # 表示这一页已经下载过了
            self.downloaded_page.add(page_num)

        if downloaded_imgs:
            logger.info(
                f"书籍 <{self.bid}> 有 <{len(downloaded_imgs)}> 页已经下载到本地"
            )

        return path

    def add_book_info(self, author: str, book_name: str, total_page: int) -> None:
        """添加书籍的名称、总页数信息"""
        if self.name != "" and self.total_page != 0:
            return

        self.author = author
        self.name = book_name
        self.total_page = total_page

        # 此时，它记录的是本地已经下载好的图片
        # 现在需要输出还有哪些图片并没有下载，方便手动翻页去下载
        downloaded_page_count = len(self.downloaded_page)

        if downloaded_page_count == 0:
            return

        if downloaded_page_count == self.total_page:
            logger.info(
                f"书籍 <{self.bid}> 的所有图片已经缓存到了本地，请将该 id 从待下载设置项中移除"
            )
        else:
            losed_page = []
            for i in range(1, self.total_page + 1):
                if i not in self.downloaded_page:
                    losed_page.append(i)

            logger.info(f"书籍 <{self.bid}> 还需要下载以下页: {losed_page}")

    def add_bookmark(self, bookmark: dict) -> None:
        """添加书籍的书签信息"""
        if self.bookmark != "":
            return

        self.bookmark = bookmark
        # 保存到本地一份
        with open(self.images_path / "bookmark.json", "w", encoding="utf-8") as f:
            json.dump(bookmark, f)

    def _get_one_page(self, page_num: int) -> OnePage:
        """获取书本的某一页"""
        if page_num in self.pages:
            return self.pages[page_num]

        # 创建一本书的某一页
        page = OnePage()
        self.pages[page_num] = page
        return page

    def add_split_page(self, page_num: int, index: int, image: bytes) -> bool:
        """
        给图书的第 page_num 页添加一个小图片，小图片的顺序为 index。
        如果已经添加了 6 张小图片，则会自动合并、保存该图片啦啦。

        如果返回值 True，表示这本书已经下载完毕。
        """
        page = self._get_one_page(page_num)
        page.add_split_page(index, image)

        # 已经添加了 6 张小图片，则需要保存该图片啦
        if page.is_enough():
            # 图片路径如 `path/book_id/page_num.webp`
            suffix = settings["picture_format"]
            filename = self.images_path / f"{page_num}.{suffix}"
            page.save_full_page(filename)

            # 然后标记该页已经下载过了
            self.downloaded_page.add(page_num)
            logger.info(
                f"书籍 <{self.bid}> 的第 <{page_num}> 页已保存，整体进度 <{len(self.downloaded_page)}/{self.total_page}>"
            )

            # 然后判断书本是否下载完成，下载完成之后需要合并 PDF 哟
            if self.total_page != 0 and len(self.downloaded_page) == self.total_page:
                self._save_as_pdf()
                return True

        return False

    def is_page_downloaded(self, page_num: int) -> bool:
        """判断某一页是否已经下载过"""
        return page_num in self.downloaded_page

    def _save_as_pdf(self):
        """合并 PDF 文件"""
        good_name = utils.be_good_name(self.name)
        good_author = utils.be_good_name(self.author)

        output_pdf = (
            settings["save_path"] / f"{self.bid}_{good_name}({good_author}).pdf"
        )

        threading.Thread(
            target=utils.merge_image_as_pdf,
            args=(self.images_path, output_pdf, self.bookmark),
        ).start()

    pass


class SplitPageOrder:
    """
    根据 req_before_split_page 请求，确认它对应的小图片请求，
    从而生成映射关系，用于确认小图片的顺序！

    现在规范名称：
        小图片里面的 zn 称之为 encode_zn，它们是被加密过的，如 "ha1TgXQ9J1c"
        req_before_split_page 请求中的 zn 依然保持名为 zn，如 1

        此处就是就记录 { zn: encoe_zn } 的映射关系。
    """

    def __init__(self) -> None:
        self.zn_table: dict[int, dict[int, dict[int, str]]] = {}
        """
        其构成类似
        // 表示某本书
        bid: {
            // 表示书本的某一页
            page_num: {
                // 一个映射关系
                1: "ha1TgXQ9J1c"
            }
        }
        """

    def add(self, k: str, body: str) -> None:
        """传入 `req_before_split_page` 的参数 k、响应体 data，生成一个映射关系"""

        # 出现了 body 为空字符串的情况。我也不知道为什么，很难复现，所以暂时忽略
        if not body:
            return

        data = utils.jwt_decrypt(k)

        # 解密失败，直接返回
        if not data:
            logger.debug(
                f"req_before_split_page 请求参数 k 值进行 jwt 解密失败，k 值为 => {k}"
            )
            return

        logger.debug(f"req_before_split_page 请求的参数 k 进行 jwt 解密结果 => {data}")

        bid = data["b"]  # 书籍的 id
        page_num = data["p"]  # 书籍的第几页
        zn = data["zn"]  # 第几个小图片

        # 计算出对应的小图片中的 zn
        key = json.loads(data["k"])["i"][:16]

        logger.debug(f"req_before_split_page 请求的响应数据 => {body}")
        logger.debug(f"用于 AES 加密的 key => {key}")

        decrypt_data = utils.aes_decrypt(body, key)
        if not decrypt_data:
            return

        logger.debug(f"对 req_before_split_page 请求的 AES 解密结果 => {decrypt_data}")

        encode_zn = json.loads(decrypt_data)["zn"]

        # 添加到映射表
        logger.debug(
            f"添加映射关系: 书籍 <{bid}> 的第 <{page_num}> 页的第 <{zn}> 个小图片对应的 zn 值为 <{encode_zn}>"
        )
        self._add(bid, page_num, zn, encode_zn)

    def _add(self, bid: int, page_num: int, zn: int, encode_zn: str) -> None:
        """给书籍 bid 的第 page_num 页建立映射关系"""
        if bid not in self.zn_table:
            self.zn_table[bid] = {}

        if page_num not in self.zn_table[bid]:
            self.zn_table[bid][page_num] = {}

        self.zn_table[bid][page_num][zn] = encode_zn

    def get(self, k: str) -> int:
        """传入小图片请求参数中的 k，获取它的顺序。如果返回 -1 表示失败"""

        data = utils.jwt_decrypt(k)
        order = -1  # 记录最终查找到的小图片的顺序

        if not data:
            logger.debug(f"小图片请求参数 k 值进行 jwt 解密失败，k 值为 => {k}")
            return order

        logger.debug(f"解析小图片请求的参数 k => {data}")

        bid = data["b"]  # 书籍的 id
        page_num = data["p"]  # 书籍的第几页
        page_zn = json.loads(data["k"])["zn"]  # 这个就要看网站分析的文档啦

        if bid not in self.zn_table:
            logger.debug(f"书籍 <{bid}> 不在映射表中")
            return order

        book_zn_table = self.zn_table[bid]  # 记录一本书的 zn 关系表

        if page_num not in book_zn_table:
            logger.debug(f"书籍 <{bid}> 的第 <{page_num}> 页不在映射表中")
            return order

        page_zn_table = book_zn_table[page_num]  # 记录该本书、某一页的 zn 关系表

        logger.debug(
            f"书籍 <{bid}> 的第 <{page_num}> 页的 zn 关系表 => {page_zn_table}"
        )
        for zn, encode_zn in page_zn_table.items():
            if encode_zn == page_zn:
                order = zn
                break

        if order == -1:
            logger.debug(
                f"书籍 <{bid}> 的第 <{page_num}> 页的第 <{page_zn}> 小图片不在映射表中"
            )
        else:
            # 现在已经拿到了小图片顺序，需要清理一下空间呀
            page_zn_table.pop(order)
            # 如果该页的小图片已经全部确定好了顺序，那么就清理掉该页的映射关系
            if len(page_zn_table) == 0:
                book_zn_table.pop(page_num)

        return order

    pass
