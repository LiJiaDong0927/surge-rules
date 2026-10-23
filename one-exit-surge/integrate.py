#!/usr/bin/env python3
"""Prepare/apply a reversible One Exit patch without changing existing rules."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / ".private"
CLI = Path("/Applications/Surge.app/Contents/Applications/surge-cli")
TARGET_POLICY = "♻️ 手动切换"
START_ROUTE = "# BEGIN ONE EXIT ROUTE"
END_ROUTE = "# END ONE EXIT ROUTE"
START_DATA = "# BEGIN ONE EXIT DATA"
RESOLVING = {"RULE-SET", "DOMAIN-SET", "IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_message(value: str) -> str:
    return re.sub(r"https?://[^\s,]+", "<resource-url>", value)


def run_cli(*args: str) -> str:
    result = subprocess.run([str(CLI), *args], text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(safe_message(result.stderr + result.stdout).strip())
    return result.stdout


def private_write(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    path.chmod(0o600)


def atomic_write(path: Path, data: bytes) -> None:
    mode = path.stat().st_mode & 0o777
    fd, name = tempfile.mkstemp(prefix=".one-exit-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def policy_choices(output: str) -> dict[str, str]:
    choices = {}
    current = None
    for line in output.splitlines():
        if line and not line.startswith(" ") and " (" in line:
            current = line.rsplit(" (", 1)[0]
        elif current and line.startswith("  Selected:"):
            choices[current] = line.partition(":")[2].strip()
    return choices


def direct_policies(choices: dict[str, str]) -> set[str]:
    direct = {"DIRECT"}
    while True:
        expanded = direct | {name for name, selected in choices.items() if selected in direct}
        if expanded == direct:
            return direct
        direct = expanded


def section_lines(text: str, name: str) -> list[str]:
    active = False
    result = []
    for line in text.splitlines(keepends=True):
        match = re.fullmatch(r"\[([^\]]+)\]\s*", line.strip())
        if match:
            active = match.group(1) == name
        elif active:
            result.append(line)
    return result


def csv_line(fields: list[str]) -> str:
    stream = io.StringIO()
    csv.writer(stream, lineterminator="").writerow(fields)
    return stream.getvalue()


def strip_managed(text: str) -> str:
    text = re.sub(r"(?ms)^# BEGIN ONE EXIT ROUTE\n.*?^# END ONE EXIT ROUTE\n", "", text)
    return text.split("\n" + START_DATA + "\n", 1)[0]


def transform(source: str, direct: set[str], targets: str) -> tuple[str, list[str]]:
    if START_ROUTE in source or START_DATA in source:
        raise ValueError("One Exit 已集成；请先回滚或手动审查，不重复插入。")
    if re.search(r"(?m)^\[Ruleset OneExit(?:Targets|KeepDirect)\]", source):
        raise ValueError("已有同名规则集，请先处理命名冲突。")
    guards = []
    for raw in section_lines(source, "Rule"):
        line = raw.strip()
        if not line or line.startswith(("#", ";", "//")):
            continue
        fields = [part.strip() for part in next(csv.reader([line]))]
        kind = fields[0]
        if kind in {"AND", "OR", "NOT", "SCRIPT"}:
            raise ValueError("发现需要人工审查的规则类型：" + kind)
        if kind == "FINAL" and len(fields) > 1 and fields[1] in direct:
            raise ValueError("FINAL 当前直连，无法自动枚举其保护范围。")
        if len(fields) < 3 or fields[2] not in direct:
            continue
        flags = [flag for flag in fields[3:] if flag in {"no-resolve", "extended-matching"}]
        if kind in RESOLVING and "no-resolve" not in flags:
            flags.append("no-resolve")
        condition = csv_line(fields[:2] + flags)
        if condition not in guards:
            guards.append(condition)
    if not guards:
        raise ValueError("没有识别到现有直连规则，停止自动集成。")
    anchor = re.search(r"(?m)^RULE-SET,LAN,DIRECT,no-resolve[^\S\n]*\n", source)
    if not anchor:
        raise ValueError("没有找到已修复的 LAN 规则，停止自动集成。")
    route = (
        START_ROUTE + "\n"
        '# 当前直连例外回到原分流；其余 One Exit 目标跟随手动选择。\n'
        'AND,((RULE-SET,OneExitTargets,no-resolve),(NOT,((RULE-SET,OneExitKeepDirect,no-resolve)))),'
        + TARGET_POLICY + '\n' + END_ROUTE + "\n"
    )
    candidate = source[:anchor.end()] + route + source[anchor.end():]
    candidate += (
        "\n" + START_DATA + "\n"
        "# 本地快照；不更改 General/DNS 或原有规则顺序。\n"
        "[Ruleset OneExitTargets]\n" + targets.rstrip() + "\n\n"
        "[Ruleset OneExitKeepDirect]\n" + "\n".join(guards) + "\n"
        "# END ONE EXIT DATA\n"
    )
    if strip_managed(candidate) != source:
        raise AssertionError("原配置保留检查失败")
    if section_lines(candidate, "General") != section_lines(source, "General"):
        raise AssertionError("General 不应被修改")
    return candidate, guards


def prepare(profile: Path) -> None:
    profile = profile.expanduser().resolve()
    original = profile.read_bytes()
    choices = policy_choices(run_cli("policy-group", "list"))
    direct = direct_policies(choices)
    if TARGET_POLICY not in choices or TARGET_POLICY in direct:
        raise ValueError("手动切换组不存在或正在直连，请先选择实际代理节点。")
    targets = (ROOT / "one-exit-targets.list").read_text()
    candidate, guards = transform(original.decode("utf-8"), direct, targets)
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    PRIVATE.chmod(0o700)
    # Surge resolves cached remote #!include files relative to the profile folder.
    # Reuse its existing cache for offline validation; never copy it into public files.
    managed = profile.parent / ".managed"
    cache_link = PRIVATE / ".managed"
    if managed.is_dir():
        if cache_link.is_symlink():
            if cache_link.resolve() != managed.resolve():
                raise ValueError("候选配置缓存指向另一个目录，停止。")
        elif cache_link.exists():
            raise ValueError("候选缓存路径已存在且不是链接，停止。")
        else:
            cache_link.symlink_to(managed, target_is_directory=True)
    state_path = PRIVATE / "state.json"
    if state_path.exists():
        old_state = json.loads(state_path.read_text())
        if old_state.get("applied"):
            raise ValueError("已有应用中的备份，不覆盖；请先回滚或人工审查。")
    private_write(PRIVATE / "original.conf", original)
    private_write(PRIVATE / "candidate.conf", candidate.encode())
    check = run_cli("--check", str(PRIVATE / "candidate.conf"))
    state = {
        "profile": str(profile), "original_sha256": digest(original),
        "candidate_sha256": digest(candidate.encode()), "applied": False,
        "policy_choices": choices, "protected_policies": sorted(direct),
        "protected_conditions": len(guards), "validation": check.strip(),
    }
    private_write(state_path, (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"prepared": True, "protected_conditions": len(guards),
                      "protected_policies": sorted(direct), "validation": check.strip()}, ensure_ascii=False))


def apply() -> None:
    state_path = PRIVATE / "state.json"
    state = json.loads(state_path.read_text())
    path = Path(state["profile"])
    original = (PRIVATE / "original.conf").read_bytes()
    candidate = (PRIVATE / "candidate.conf").read_bytes()
    if digest(path.read_bytes()) != state["original_sha256"]:
        raise ValueError("生效配置在准备后发生变化，停止覆盖。请重新准备并检查。")
    if digest(original) != state["original_sha256"] or digest(candidate) != state["candidate_sha256"]:
        raise ValueError("候选或备份校验失败，停止应用。")
    if policy_choices(run_cli("policy-group", "list")) != state["policy_choices"]:
        raise ValueError("策略组选择在准备后变化，请重新准备。")
    run_cli("--check", str(PRIVATE / "candidate.conf"))
    if digest(path.read_bytes()) != state["original_sha256"]:
        raise ValueError("校验期间配置被修改，停止覆盖。")
    atomic_write(path, candidate)
    try:
        output = run_cli("reload")
    except Exception:
        if digest(path.read_bytes()) != state["candidate_sha256"]:
            raise RuntimeError("重载失败且配置又被修改，请人工检查；原备份已保留。")
        atomic_write(path, original)
        run_cli("reload")
        raise
    state["applied"] = True
    private_write(state_path, (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
    print("已应用并重新载入。" + safe_message(output).strip())


def rollback() -> None:
    state_path = PRIVATE / "state.json"
    state = json.loads(state_path.read_text())
    path = Path(state["profile"])
    if not state.get("applied"):
        raise ValueError("尚未应用，无需回滚。")
    if digest(path.read_bytes()) != state["candidate_sha256"]:
        raise ValueError("配置已有后续修改，拒绝覆盖。请手动移除 ONE EXIT 标记块。")
    original = (PRIVATE / "original.conf").read_bytes()
    candidate = (PRIVATE / "candidate.conf").read_bytes()
    if digest(original) != state["original_sha256"]:
        raise ValueError("备份校验失败。")
    if digest(candidate) != state["candidate_sha256"]:
        raise ValueError("候选文件校验失败。")
    if digest(path.read_bytes()) != state["candidate_sha256"]:
        raise ValueError("回滚检查期间配置被修改，停止覆盖。")
    atomic_write(path, original)
    try:
        run_cli("reload")
    except Exception as error:
        if digest(path.read_bytes()) != state["original_sha256"]:
            raise RuntimeError("回滚重载失败且配置又被修改，请人工检查；备份已保留。") from error
        atomic_write(path, candidate)
        try:
            run_cli("reload")
        except Exception:
            pass
        raise RuntimeError("回滚重载失败，已恢复回滚前文件，可重试。" + str(error)) from error
    state["applied"] = False
    private_write(state_path, (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
    print("已恢复原配置并重新载入。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "apply", "rollback"])
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            if not args.profile:
                parser.error("prepare 需要 --profile")
            prepare(args.profile)
        elif args.action == "apply":
            apply()
        else:
            rollback()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, safe_message(str(error)) + "\n")


if __name__ == "__main__":
    main()
