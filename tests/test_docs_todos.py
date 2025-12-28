from codex_autorunner.docs import parse_todos


def test_parse_todos_collects_outstanding_and_done() -> None:
    content = """# TODO

- [ ] First task
- [x] Finished task
- [X] Also finished
- [ ]    Spaced task
"""
    outstanding, done = parse_todos(content)

    assert outstanding == ["First task", "Spaced task"]
    assert done == ["Finished task", "Also finished"]
