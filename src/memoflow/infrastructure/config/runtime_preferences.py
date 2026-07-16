"""运行时用户偏好（持久化到 data/runtime_preferences.json，无需重启）。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_VALID_BACKENDS = frozenset({"mlx_moss", "moss_hf", "vibevoice"})


@dataclass
class RuntimePreferences:
    data_dir: Path
    asr_backend: str | None = None

    @property
    def path(self) -> Path:
        return self.data_dir / "runtime_preferences.json"

    @classmethod
    def load(cls, data_dir: Path) -> RuntimePreferences:
        file_path = data_dir / "runtime_preferences.json"
        if not file_path.is_file():
            return cls(data_dir=data_dir)
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(data_dir=data_dir)
        backend = raw.get("asr_backend")
        if isinstance(backend, str):
            backend = backend.strip().lower()
            if backend in _VALID_BACKENDS:
                return cls(data_dir=data_dir, asr_backend=backend)
        return cls(data_dir=data_dir)

    def save_asr_backend(self, backend: str) -> None:
        backend = backend.strip().lower()
        if backend not in _VALID_BACKENDS:
            raise ValueError(f"未知 ASR 后端: {backend}")
        self.asr_backend = backend
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {"asr_backend": backend}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def clear_asr_backend(self) -> None:
        self.asr_backend = None
        if self.path.is_file():
            self.path.unlink()
