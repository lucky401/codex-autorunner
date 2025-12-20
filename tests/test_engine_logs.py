from codex_autorunner.engine import Engine


def test_engine_reads_run_log_file(repo):
    engine = Engine(repo)
    run_id = 3
    run_log = engine._run_log_path(run_id)
    run_log.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "=== run 3 start ===",
            "[2025-01-01T00:00:00Z] run=3 stdout: hello",
            "=== run 3 end (code 0) ===",
            "",
        ]
    )
    run_log.write_text(content, encoding="utf-8")
    assert engine.read_run_block(run_id) == content
    assert engine.extract_prev_output(run_id) == "hello"
