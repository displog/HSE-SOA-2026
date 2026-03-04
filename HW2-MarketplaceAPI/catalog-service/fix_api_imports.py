#!/usr/bin/env python3
"""Замена openapi_server.models на src.schemas.generated."""
import re
from pathlib import Path


def fix_imports(content: str) -> str:
    """Заменяет импорты models на src.schemas.generated."""
    # openapi_server.models.xxx -> src.schemas.generated
    content = re.sub(
        r"from openapi_server\.models\.\w+ import ([^\n]+)",
        r"from src.schemas.generated import \1",
        content,
    )
    content = re.sub(
        r"from openapi_server\.models import ([^\n]+)",
        r"from src.schemas.generated import \1",
        content,
    )
    # src.models (если packageName=src)
    content = re.sub(
        r"from src\.models\.\w+ import ([^\n]+)",
        r"from src.schemas.generated import \1",
        content,
    )
    # Убираем импорт extra_models.TokenModel (может отсутствовать при models=)
    content = re.sub(
        r"from \w+\.models\.extra_models import TokenModel.*\n",
        "",
        content,
    )
    # strict=True в Query ломает парсинг строк "0","5" как int — убираем
    content = re.sub(r", strict=True\)", ")", content)
    content = re.sub(r", strict=True,", ",", content)
    content = re.sub(r"Field\(strict=True, ", "Field(", content)
    return content


def main():
    base = Path("src/openapi_server")
    if not base.exists():
        return
    for subdir in ("apis", "impl"):
        dir_path = base / subdir
        if not dir_path.exists():
            continue
        for py_file in dir_path.glob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="replace")
            new_content = fix_imports(content)
            if new_content != content:
                py_file.write_text(new_content, encoding="utf-8")
                print(f"Fixed: {py_file}")


if __name__ == "__main__":
    main()
