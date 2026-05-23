"""
Monkey-patch tqdm.tqdm so HuggingFace / ModelScope download bars
flow into a shared state dict. Used by tts_service for progress reporting.

Aggregates *all* active bars by id(self): HuggingFace downloads multiple shards
in parallel, and each shard gets its own tqdm bar. We sum (n / total) across
every active bar so the frontend sees a single monotonic global percentage
instead of one bar's value flickering up and down.
"""
from __future__ import annotations

import threading
from typing import Any

_hook_installed = False
_hook_lock = threading.Lock()

# id(bar) -> (n, total, desc).  Cleared in _patched_close.
_active_bars: dict[int, tuple[int, int, str]] = {}
_bars_lock = threading.Lock()


def _recompute(state_dict: dict[str, Any]) -> None:
    """Roll up every live tqdm bar into a single percent / detail."""
    with _bars_lock:
        if not _active_bars:
            return
        total_n = 0
        total_total = 0
        last_desc = ""
        for n, total, desc in _active_bars.values():
            if total <= 0:
                continue
            total_n += n
            total_total += total
            if desc:
                last_desc = desc
        if total_total <= 0:
            return
        pct = int(total_n / total_total * 100)
        state_dict["percent"] = max(0, min(100, pct))
        state_dict["detail"] = (
            f"{last_desc or 'download'}: {total_n}/{total_total} "
            f"({len(_active_bars)} files)"
        )


def install_progress_hook(state_dict: dict[str, Any]) -> None:
    """Install once-per-process tqdm hook that writes aggregated progress.

    state_dict will be mutated with keys: percent (int), detail (str).
    Safe to call multiple times — only the first call patches tqdm.
    """
    global _hook_installed
    with _hook_lock:
        if _hook_installed:
            return
        try:
            import tqdm as _tqdm  # type: ignore

            _orig_update = _tqdm.tqdm.update
            _orig_close = _tqdm.tqdm.close

            def _patched_update(self, n: int = 1):  # type: ignore[no-untyped-def]
                ret = _orig_update(self, n)
                try:
                    if self.total and self.total > 0:
                        with _bars_lock:
                            _active_bars[id(self)] = (
                                int(self.n),
                                int(self.total),
                                (self.desc or "").strip(),
                            )
                    _recompute(state_dict)
                except Exception:
                    pass
                return ret

            def _patched_close(self):  # type: ignore[no-untyped-def]
                ret = _orig_close(self)
                try:
                    with _bars_lock:
                        _active_bars.pop(id(self), None)
                    _recompute(state_dict)
                except Exception:
                    pass
                return ret

            _tqdm.tqdm.update = _patched_update  # type: ignore[assignment]
            _tqdm.tqdm.close = _patched_close  # type: ignore[assignment]
            _hook_installed = True
        except Exception as e:  # noqa: BLE001
            print(f"[tqdm-hook] install failed: {e}")
