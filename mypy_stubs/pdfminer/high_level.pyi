import io
import pathlib
from typing import (Container, Optional, Union)
FileOrName = Union[pathlib.PurePath, str, io.IOBase]
class LAParams(): ...
def extract_text(
    pdf_file: FileOrName,
    password: str = "",
    page_numbers: Optional[Container[int]] = None,
    maxpages: int = 0,
    caching: bool = True,
    codec: str = "utf-8",
    laparams: Optional[LAParams] = None,
) -> str: ...
