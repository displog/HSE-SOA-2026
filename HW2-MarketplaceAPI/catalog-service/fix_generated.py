#!/usr/bin/env python3
"""Постобработка generated.py для совместимости с Pydantic v2."""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "src/schemas/generated.py"

with open(path) as f:
    c = f.read()

# Pydantic v2: regex -> pattern
c = c.replace("regex=", "pattern=")

# Pydantic v2: __root__ -> RootModel (datamodel-codegen старых версий)
c = re.sub(
    r"class (\w+)\(BaseModel\):\s*\n\s+__root__: (\w+)\s*\n",
    r"class \1(RootModel[\2]):\n    pass\n",
    c,
)

# Добавить RootModel в импорт если использовали RootModel
if "RootModel[" in c and "RootModel" not in c.split("from pydantic import")[1].split("\n")[0]:
    if "from pydantic import BaseModel," in c:
        c = c.replace("from pydantic import BaseModel,", "from pydantic import BaseModel, RootModel,", 1)
    else:
        c = c.replace("from pydantic import BaseModel\n", "from pydantic import BaseModel, RootModel\n", 1)

if "TokenModel" not in c:
    c += "\n\nTokenModel = Any\n"

with open(path, "w") as f:
    f.write(c)
