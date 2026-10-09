# -*- coding: utf-8 -*-
# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者 · MIT
import os
import re
import subprocess
import sys
from pathlib import Path


def test_no_control_characters_in_markdown():
    """断言 markdown 文档中不含 \x00-\x08\x0b\x0c\x0e-\x1f 控制字符"""
    root = Path(__file__).resolve().parent.parent
    md_files = [root / "README.md", root / "AGENTS.md"]
    docs_dir = root / "docs"
    for p in docs_dir.rglob("*.md"):
        if "screenshots" in p.parts:
            continue
        md_files.append(p)

    ctrl_char_pattern = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
    failures = []

    for path in md_files:
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            failures.append(f"{path}: 无法以 UTF-8 读取: {e}")
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            matches = list(ctrl_char_pattern.finditer(line))
            if matches:
                codes = [f"U+{ord(m.group()):04X} at col {m.start()+1}" for m in matches]
                failures.append(f"{path.relative_to(root)}:{line_no} 含控制字符: {', '.join(codes)}")

    assert not failures, "发现文档控制字符损坏:\n" + "\n".join(failures)


def test_readme_test_count_matches_collected_tests():
    """断言 README.md 徽章行与测试说明行的用例数与 pytest --collect-only 收集数一致"""
    root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    res = subprocess.run(cmd, cwd=root, capture_output=True)
    stdout_text = res.stdout.decode("utf-8", errors="ignore")
    m = re.search(r"(\d+)\s+tests?\s+collected", stdout_text)
    assert m, f"未从 pytest --collect-only 输出解析出用例总数:\n{stdout_text}"
    collected_count = int(m.group(1))

    readme_path = root / "README.md"
    readme_lines = readme_path.read_text(encoding="utf-8").splitlines()

    badge_line = next((l for l in readme_lines if "badge/tests-" in l), None)
    assert badge_line is not None, "README.md 缺少 tests 徽章行"
    assert str(collected_count) in badge_line, f"README 徽章测试数与收集数不一致: 期望含 {collected_count}, 实际行: {badge_line}"

    pytest_line = next((l for l in readme_lines if "pytest -q" in l and "项" in l), None)
    assert pytest_line is not None, "README.md 缺少 pytest -q 测试说明行"
    assert str(collected_count) in pytest_line, f"README 说明测试数与收集数不一致: 期望含 {collected_count}, 实际行: {pytest_line}"
