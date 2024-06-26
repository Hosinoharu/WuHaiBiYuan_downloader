import commentjson as json
from pathlib import Path
from datetime import datetime

__all__ = ["settings"]

# 配置文件必须在本 .py 的同一层目录中！
settings_file = Path(__file__).parent / "settings.jsonc"
settings = json.loads(settings_file.read_text(encoding="utf-8"))


def create_path(path: str):
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


# 项目所在的目录，使用相对路径啦
project_dir = Path(__file__).parent.parent

# 所有下载的图书都保存在这个目录下，书籍名为 `书籍id_书名(作者).pdf`
settings["save_path"] = project_dir / "download_book"
# 保存书籍每一页时的临时路径。以 `/书籍id/` 目录保存特定书籍的图片
settings["image_path"] = project_dir / "book_images"

create_path(settings["save_path"])
create_path(settings["image_path"])


if settings["log_file"]:
    log_path = project_dir / "log"
    create_path(log_path)

    # 创建日志文件
    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y-%m-%d-%M-%S")
    settings["log_file"] = log_path / f"{formatted_time}.log"
else:
    settings["log_file"] = None
