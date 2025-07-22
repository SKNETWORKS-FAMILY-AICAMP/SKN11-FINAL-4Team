"""
Async file utilities for non-blocking file I/O operations
"""
import json
import aiofiles
from typing import Any, Dict


async def async_read_json(file_path: str) -> Dict[str, Any]:
    """Asynchronously read and parse a JSON file"""
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = await f.read()
        return json.loads(content)


async def async_write_json(file_path: str, data: Dict[str, Any]) -> None:
    """Asynchronously write data to a JSON file"""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(json_str)


async def async_read_text(file_path: str) -> str:
    """Asynchronously read a text file"""
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        return await f.read()


async def async_write_text(file_path: str, content: str) -> None:
    """Asynchronously write text to a file"""
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(content)