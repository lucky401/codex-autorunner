from pathlib import Path

from codex_autorunner.logging_utils import setup_rotating_logger
from codex_autorunner.config import LogConfig


def test_rotating_loggers_are_isolated(tmp_path: Path):
    log_a = tmp_path / "a.log"
    log_b = tmp_path / "b.log"
    cfg_a = LogConfig(path=log_a, max_bytes=80, backup_count=1)
    cfg_b = LogConfig(path=log_b, max_bytes=40, backup_count=2)

    logger_a = setup_rotating_logger("repo:a", cfg_a)
    logger_b = setup_rotating_logger("repo:b", cfg_b)

    logger_a.info("first")
    logger_b.info("second")

    assert log_a.exists()
    assert log_b.exists()
    assert logger_a.handlers
    assert logger_b.handlers
    assert logger_a.handlers[0] is not logger_b.handlers[0]

    # Rotation should be contained per logger
    for _ in range(10):
        logger_b.info("x" * 20)
    logger_b.handlers[0].flush()
    assert (tmp_path / "b.log.1").exists()

    # Reusing the same name reuses the same handler
    same_logger = setup_rotating_logger("repo:a", cfg_a)
    assert same_logger is logger_a
    assert len(same_logger.handlers) == 1
