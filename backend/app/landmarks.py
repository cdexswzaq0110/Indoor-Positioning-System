"""地圖載入與 Landmark → Node → coordinate 的對應。"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from . import config


class LandmarkMap:
    """把地板數字換算成場域座標。

    數字在不同樓層可能重複，所以查詢鍵是 (floor, digit)；呼叫端沒有樓層線索時，
    回退成「全場域唯一的那個數字」，找不到唯一解就明說歧義而不是亂猜。
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._raw: dict[str, Any] = {}
        self._by_id: dict[str, dict[str, Any]] = {}
        self._by_floor_digit: dict[tuple[int, int], dict[str, Any]] = {}
        self._by_digit: dict[int, list[dict[str, Any]]] = {}
        self.reload()

    def reload(self) -> None:
        with self._lock:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            by_id: dict[str, dict[str, Any]] = {}
            by_floor_digit: dict[tuple[int, int], dict[str, Any]] = {}
            by_digit: dict[int, list[dict[str, Any]]] = {}

            for node in raw.get("nodes", []):
                by_id[node["id"]] = node
                digit = node.get("landmark_digit")
                if digit is None:
                    continue
                key = (int(node["floor"]), int(digit))
                if key in by_floor_digit:
                    raise ValueError(
                        f"地圖有衝突：樓層 {key[0]} 的數字 {key[1]} 對到多個 node "
                        f"({by_floor_digit[key]['id']} 與 {node['id']})"
                    )
                by_floor_digit[key] = node
                by_digit.setdefault(int(digit), []).append(node)

            self._raw, self._by_id = raw, by_id
            self._by_floor_digit, self._by_digit = by_floor_digit, by_digit

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    @property
    def node_count(self) -> int:
        return len(self._by_id)

    def node_by_id(self, node_id: str) -> dict[str, Any] | None:
        return self._by_id.get(node_id)

    def resolve(self, digit: int, floor_hint: int | None = None) -> tuple[dict[str, Any] | None, str | None]:
        """回傳 (node, 失敗原因)。成功時原因為 None。"""
        if floor_hint is not None:
            node = self._by_floor_digit.get((int(floor_hint), int(digit)))
            if node is None:
                return None, f"樓層 {floor_hint} 沒有數字 {digit} 的地標"
            return node, None

        candidates = self._by_digit.get(int(digit), [])
        if not candidates:
            return None, f"地圖上沒有數字 {digit} 的地標"
        if len(candidates) > 1:
            floors = sorted({c["floor"] for c in candidates})
            return None, f"數字 {digit} 在多個樓層都有（{floors}），需要 floor_hint"
        return candidates[0], None
