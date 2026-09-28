#!/usr/bin/env python3

import re
from pathlib import Path

import yaml


CONFIG_PATH = Path("/slamhive/tep_config.yaml")
TEMPLATE_PATH = Path("/slamhive/template.yaml.j2")
OUTPUT_PATH = Path("/slamhive/mappingtask.yaml")


def load_context():
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def render(template, context):
    pattern = re.compile(r"{{\s*([A-Za-z0-9_]+)\s*}}")
    missing = set()

    def replace(match):
        key = match.group(1)
        if key not in context:
            missing.add(key)
            return match.group(0)
        value = context[key]
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    rendered = pattern.sub(replace, template)
    if missing:
        raise KeyError("Missing template values: {}".format(", ".join(sorted(missing))))
    return rendered


def main():
    context = load_context()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    OUTPUT_PATH.write_text(render(template, context), encoding="utf-8")
    print("[render_template.py] wrote {}".format(OUTPUT_PATH))


if __name__ == "__main__":
    main()
