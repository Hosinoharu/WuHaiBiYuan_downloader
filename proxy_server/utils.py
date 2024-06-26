import json
import traceback
import base64
from pathlib import Path
from io import BytesIO

import jwt
import pypdf
from PIL import Image
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


from mylogger import logger
from settings import settings


def jwt_decrypt(k: str) -> dict:
    """如果解密失败，则返回空字典"""
    try:
        decrypt_data = jwt.decode(
            k,
            "secret",
            algorithms=["HS256"],
            # 必须加上这一行
            options={"verify_signature": False},
        )
    except Exception as e:
        logger.error(
            f"jwt_decrypt 错误: {e}。\n解密数据为: {k}。\n堆栈: { traceback.format_exc()}。"
        )
        decrypt_data = {}

    return decrypt_data


def aes_decrypt(ciphertext: str, key: str) -> str:
    """如果解密失败，则返回空字符串"""
    ciphertext = base64.b64decode(ciphertext)
    key = key.encode()

    cipher = AES.new(key, AES.MODE_ECB)

    try:
        text = unpad(cipher.decrypt(ciphertext), AES.block_size)
        result = text.decode()
    except Exception as e:
        logger.error(
            f"AES decrypt error: {e}。\n密文为: {ciphertext}，key 为: {key}。\n堆栈: { traceback.format_exc()}。"
        )
        result = ""

    return result


def be_good_name(name: str, be: str = "") -> str:
    """name 将用于 windows 的文件名称，需要把其中不符合规范的字符替换成指定的字符"""
    for c in '\\/:*?"<>|':
        if c in name:
            name = name.replace(c, be)

    return name


def get_imgs_files(dir: Path, suffix: str) -> list[Path]:
    """获取目录下所有图片文件，根据后缀名确定图片的格式"""
    suffix = "." + suffix

    result = []
    for item in dir.iterdir():
        if item.suffix == suffix:
            result.append(item)

    # 根据文件名排序，它们都是 0.webp 1.webp 2.webp ... 等格式
    return sorted(result, key=lambda x: int(x.stem))


def _add_bookmark(pdf_writer: pypdf.PdfWriter, bookmark: dict):
    """给 PDF 添加书签"""
    """
    bookmark 的每一项都是一个书签，格式如下：
        {
            "id": "281474976645121",
            "pid": "0",
            "label": "封面",  # 书签名
            "pnum": "1",     # 书签的页数
            "level": "1",    # 书签的层级
            "isLeaf": true,  # 是否是叶子节点，如果是，则下方的 children 为 null，否则为下一层级的书签
            "children": null   # 下一层级的书签
        },
    """

    all_page_num = pdf_writer.get_num_pages()  # 记录总页数，因为图片可能缺页呀

    def _add_outline(parent_bookmark, bookmark: dict):
        """递归添加书签。

        parent_bookmark 记录最近一次访问的、上一层级的书签，当前书签都将添加到其下面
        """
        for item in bookmark:
            title = item["label"]
            page_num = int(item["pnum"]) - 1  # 索引从 0 开始哟

            # pdf 缺页了，那就先返回吧
            if page_num > all_page_num:
                return

            # 先添加当前书签
            current_bookmark = pdf_writer.add_outline_item(
                title, page_num, parent_bookmark
            )

            # 递归处理子书签
            if item["children"]:
                _add_outline(current_bookmark, item["children"])

        pass

    _add_outline(None, bookmark)
    pass


def merge_image_as_pdf(path: Path, filename: str, bookmark: dict | None = None):
    """将目录下的图片合并成一个 PDF，并添加书签"""
    page_num = 0  # 记录当前处理的是第几页

    try:
        with pypdf.PdfWriter() as pdf_writer:
            # 先拼接成一个 PDF，然后添加书签
            for img in get_imgs_files(path, suffix=settings["picture_format"]):
                page_num += 1

                # 图片转为 pdf 保存到 stream 中
                pdf_stream = BytesIO()
                Image.open(img).save(pdf_stream, "PDF")

                # 读取 stream 中的 pdf 文件
                reader = pypdf.PdfReader(pdf_stream)
                pdf_writer.add_page(reader.pages[0])

            if bookmark:
                _add_bookmark(pdf_writer, bookmark)

            pdf_writer.write(filename)

            logger.info(f"合并图片为 PDF 成功，文件名: {filename}")

    except Exception as e:
        logger.error(f"合并图片为 PDF 失败: {e}。\n堆栈: { traceback.format_exc()}。")

    pass


if __name__ == "__main__":
    # 此处用于手动合并 PDF
    images_path = Path("这里填入下载的图片的位置")

    # 书签文件应该也在 images_path 下
    bookmark = json.loads(
        open(images_path / "bookmark.json", "r", encoding="utf-8").read()
    )
    filename = Path("这里填入合并后的 PDF 文件名")

    merge_image_as_pdf(images_path, filename, bookmark)
