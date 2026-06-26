from __future__ import annotations

import logging

import pytest

from aizen._logging import PromptTruncateFilter, setup_logging


def test_verbose_sets_debug():
    setup_logging(verbose=True)
    assert logging.getLogger().level == logging.DEBUG


def test_default_is_info():
    setup_logging(verbose=False)
    assert logging.getLogger().level == logging.INFO


def test_prompt_truncate_filter():
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="prompt: %s", args=("x" * 500,), exc_info=None,
    )
    record.prompt = "x" * 500
    f = PromptTruncateFilter()
    assert f.filter(record)
    assert len(record.msg) < 250


def test_short_prompt_not_truncated():
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="prompt: %s", args=("hello",), exc_info=None,
    )
    record.prompt = "hello"
    f = PromptTruncateFilter()
    assert f.filter(record)
    assert record.args == ("hello",)
    assert record.prompt == "hello"


def test_prompt_truncate_no_prompt_attr():
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="no prompt here", args=(), exc_info=None,
    )
    f = PromptTruncateFilter()
    assert f.filter(record)
    assert record.msg == "no prompt here"
