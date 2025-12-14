from pathlib import Path
from typing import Optional

from .config import Config
from .docs import DocsManager
from .prompts import DEFAULT_PROMPT_TEMPLATE


def build_prompt(
    config: Config, docs: DocsManager, prev_run_output: Optional[str]
) -> str:
    def _display_path(path: Path) -> str:
        try:
            return str(path.relative_to(config.root))
        except ValueError:
            return str(path)

    doc_paths = {
        "todo": _display_path(config.doc_path("todo")),
        "progress": _display_path(config.doc_path("progress")),
        "opinions": _display_path(config.doc_path("opinions")),
        "spec": _display_path(config.doc_path("spec")),
    }

    template_path: Path = config.prompt_template if config.prompt_template else None
    if template_path and template_path.exists():
        template = template_path.read_text(encoding="utf-8")
    else:
        template = DEFAULT_PROMPT_TEMPLATE

    prev_section = ""
    if prev_run_output:
        prev_section = "<PREV_RUN_OUTPUT>\n" + prev_run_output + "\n</PREV_RUN_OUTPUT>"

    replacements = {
        "{{TODO}}": docs.read_doc("todo"),
        "{{PROGRESS}}": docs.read_doc("progress"),
        "{{OPINIONS}}": docs.read_doc("opinions"),
        "{{SPEC}}": docs.read_doc("spec"),
        "{{PREV_RUN_OUTPUT}}": prev_section,
        "{{TODO_PATH}}": doc_paths["todo"],
        "{{PROGRESS_PATH}}": doc_paths["progress"],
        "{{OPINIONS_PATH}}": doc_paths["opinions"],
        "{{SPEC_PATH}}": doc_paths["spec"],
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template
