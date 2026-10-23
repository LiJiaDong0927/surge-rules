#!/usr/bin/env python3
"""Switch the installed One Exit route to the owner's remote rule list."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

import integrate as core

URL = "https://raw.githubusercontent.com/LiJiaDong0927/surge-rules/main/one-exit-surge/one-exit-targets.list"
ENTRY = "RULE-SET," + URL + ",no-resolve,update-interval=3600"
SECTION = re.compile(r"(?ms)(^\[Ruleset OneExitTargets\]\n)(.*?)(?=^\[|\Z)")


def transform(source: str) -> str:
    matches = list(SECTION.finditer(source))
    if len(matches) != 1 or "[Ruleset OneExitKeepDirect]" not in source:
        raise ValueError("需要已集成且只有一份 OneExitTargets / 保留 OneExitKeepDirect 的配置。")
    if source.count("[Ruleset OneExitKeepDirect]") != 1:
        raise ValueError("直连保护集存在重复，停止。")
    route = (
        "AND,((RULE-SET,OneExitTargets,no-resolve),(NOT,((RULE-SET,OneExitKeepDirect,no-resolve)))),"
        + core.TARGET_POLICY
    )
    if source.count(route) != 1 or route + "\n" not in core.section_lines(source, "Rule"):
        raise ValueError("现有 One Exit 逻辑规则与预期不符，请先人工审查。")
    if URL in source:
        raise ValueError("已经使用此远程名单，无需重复切换。")
    remote_route = route.replace("RULE-SET,OneExitTargets,no-resolve", ENTRY, 1)
    candidate = source.replace(route, remote_route, 1)
    for section in ("General", "Ruleset OneExitTargets", "Ruleset OneExitKeepDirect"):
        if core.section_lines(candidate, section) != core.section_lines(source, section):
            raise AssertionError(section + " 不应被修改")
    if candidate.replace(remote_route, route, 1) != source:
        raise AssertionError("目标引用以外不应有任何改动")
    return candidate


def ensure_active(profile: Path) -> None:
    status = core.run_cli("status")
    active = re.search(r"^Profile Path:\s*(.+)$", status, re.M)
    if not active or Path(active.group(1).strip()).resolve() != profile:
        raise ValueError("指定配置不是当前运行配置，停止。")


def prepare(profile: Path) -> None:
    profile = profile.expanduser().resolve()
    ensure_active(profile)
    original = profile.read_bytes()
    candidate = transform(original.decode("utf-8")).encode("utf-8")
    choices = core.policy_choices(core.run_cli("policy-group", "list"))
    core.PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    core.PRIVATE.chmod(0o700)
    state_path = core.PRIVATE / "state.json"
    if state_path.exists() and json.loads(state_path.read_text()).get("applied"):
        raise ValueError("已有使用中的远程切换备份，不覆盖。")
    managed = profile.parent / ".managed"
    link = core.PRIVATE / ".managed"
    if managed.is_dir():
        if link.is_symlink():
            if link.resolve() != managed.resolve():
                raise ValueError("缓存目录不符。")
        elif link.exists():
            raise ValueError("缓存路径已存在且不是链接。")
        else:
            link.symlink_to(managed, target_is_directory=True)
    core.private_write(core.PRIVATE / "original.conf", original)
    core.private_write(core.PRIVATE / "candidate.conf", candidate)
    validation = core.run_cli("--check", str(core.PRIVATE / "candidate.conf")).strip()
    state = {"profile": str(profile), "original_sha256": core.digest(original),
             "candidate_sha256": core.digest(candidate), "policy_choices": choices,
             "applied": False, "validation": validation, "remote_url": URL,
             "update_interval": 3600}
    core.private_write(state_path, (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"prepared": True, "validation": validation,
                      "update_interval": 3600, "only_target_reference_changed": True}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "apply", "rollback"])
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    core.PRIVATE = core.PRIVATE / "remote"
    try:
        if args.action == "prepare":
            if not args.profile:
                parser.error("prepare 需要 --profile")
            prepare(args.profile)
        else:
            state = json.loads((core.PRIVATE / "state.json").read_text())
            profile = Path(state["profile"])
            ensure_active(profile)
            if args.action == "apply":
                core.apply()
            else:
                if state.get("applied") and core.digest(profile.read_bytes()) != state["candidate_sha256"]:
                    raise ValueError("配置已有后续修改，拒绝覆盖。请仅将逻辑规则中的远程 RULE-SET 引用恢复为 RULE-SET,OneExitTargets,no-resolve，保留 KeepDirect 和其它修改。")
                core.rollback()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, core.safe_message(str(error)) + "\n")


if __name__ == "__main__":
    main()
