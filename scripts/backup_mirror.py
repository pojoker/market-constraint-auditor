#!/usr/bin/env python3
"""增量镜像 data/ 与 reports/ 到 ~/Backups/market-auditor。

为什么用 python 而不是 rsync：launchd 环境下 Apple 系二进制（rsync、疑似还有
git）访问外置盘会被 macOS 权限体系拒绝（2026-07-05/06/07 夜间三连败实证：
"Operation not permitted"），而 miniconda python 在同一环境里读写外置盘经年
正常（capture/diagnose 每晚在跑）。故镜像逻辑收敛到 python。

策略：按 (size, mtime) 增量，只增改不删除——镜像是最后防线，不做删除同步，
误删源文件时镜像里还留着。
"""

import os
import shutil
import sys
from pathlib import Path

SRC = Path("/Volumes/移动硬盘/market-constraint-auditor")
DST = Path.home() / "Backups" / "market-auditor"
SUBDIRS = ["data", "reports"]


def mirror(sub: str) -> tuple[int, int, int]:
    src_root = SRC / sub
    dst_root = DST / sub
    copied = unchanged = failed = 0
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel = Path(dirpath).relative_to(src_root)
        try:
            (dst_root / rel).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"WARN mkdir {dst_root / rel}: {e}", file=sys.stderr)
            failed += 1
            continue
        for fn in filenames:
            if fn == ".DS_Store":
                continue
            s = Path(dirpath) / fn
            d = dst_root / rel / fn
            try:
                st = s.stat()
                if d.exists():
                    dt = d.stat()
                    if dt.st_size == st.st_size and int(dt.st_mtime) >= int(st.st_mtime):
                        unchanged += 1
                        continue
                shutil.copy2(s, d)
                copied += 1
            except OSError as e:
                print(f"WARN copy {s}: {e}", file=sys.stderr)
                failed += 1
    return copied, unchanged, failed


def main() -> int:
    if not (SRC / "data").exists():
        print("SKIP: source volume not mounted")
        return 0
    total_failed = 0
    for sub in SUBDIRS:
        if not (SRC / sub).exists():
            continue
        c, u, f = mirror(sub)
        total_failed += f
        print(f"mirror {sub}: copied={c} unchanged={u} failed={f}")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
