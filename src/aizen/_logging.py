from __future__ import annotations

import logging


class PromptTruncateFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        prompt = getattr(record, "prompt", None)
        if prompt and isinstance(prompt, str) and len(prompt) > 200:
            truncated = prompt[:200] + "..."
            if record.args and len(record.args) > 0:
                args = list(record.args)
                for i, arg in enumerate(args):
                    if isinstance(arg, str) and arg == prompt:
                        args[i] = truncated
                record.args = tuple(args)
            record.prompt = truncated
        return True


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(PromptTruncateFilter())
