#!/usr/bin/env python3
"""Validate the policy-free source list and regenerate the optional Surge module."""
from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HEADER = (
    "#!name=One Exit for Surge - Targets\n"
    "#!desc=仅提供 OneExitTargets 名单，由主配置指定出口并保留直连例外。Mac 6.10+ / iOS 5.23+\n"
)


def render(source: str) -> tuple[str, int]:
    comments, rules = [], []
    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") and not line.startswith("#!"):
            comments.append(line)
            continue
        fields = line.split(",")
        kind = fields[0]
        valid = False
        if kind in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}:
            valid = len(fields) == 2 and bool(fields[1]) and not any(c.isspace() for c in fields[1])
            valid = valid and not any(c in fields[1] for c in "[]/;=\"'")
        elif kind in {"IP-CIDR", "IP-CIDR6", "IP-ASN"}:
            valid = len(fields) == 3 and fields[2] == "no-resolve"
            if valid:
                try:
                    if kind == "IP-ASN":
                        valid = fields[1].isascii() and fields[1].isdigit() and 0 < int(fields[1]) < 2**32
                    else:
                        network = ipaddress.ip_network(fields[1], strict=True)
                        valid = network.version == (6 if kind == "IP-CIDR6" else 4)
                except ValueError:
                    valid = False
        if not valid:
            raise ValueError(f"第 {number} 行不是受支持的无策略规则，或缺少 no-resolve")
        if line in rules:
            raise ValueError(f"第 {number} 行重复")
        rules.append(line)
    if not rules:
        raise ValueError("拒绝生成空名单")
    preamble = "\n".join(comments)
    module = HEADER + "\n" + preamble + "\n\n[Ruleset OneExitTargets]\n" + "\n".join(rules) + "\n"
    return module, len(rules)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查已生成模块与源名单是否一致")
    args = parser.parse_args()
    try:
        module, count = render((ROOT / "one-exit-targets.list").read_text(encoding="utf-8"))
        target = ROOT / "one-exit-targets.sgmodule"
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != module:
                raise ValueError("Module 与源名单不一致，请先运行 python3 build_module.py")
        else:
            target.write_text(module, encoding="utf-8")
        print(f"OK: {count} rules" + ("; module is current" if args.check else "; module generated"))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
