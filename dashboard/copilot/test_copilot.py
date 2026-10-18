import pytest

from copilot import tools


@pytest.mark.parametrize("query", ["delete from mining.tag_rules", "select 1; drop table mining.tag_rules",
                                   "update marts.x set a = 1", "  insert into t values (1)"])
def test_run_readonly_sql_rejects_writes(query):
    with tools.tracing() as trace, pytest.raises(ValueError):
        tools.run_readonly_sql(query)
    assert trace == []   # bị chặn trước khi chạm DB


def test_tool_schemas():
    from copilot.llm import TOOLS

    schemas = {t.to_dict()["name"]: t.to_dict()["input_schema"] for t in TOOLS}
    assert set(schemas) == {f.__name__ for f in tools.TOOLS}
    assert schemas["run_readonly_sql"]["required"] == ["query"]
    assert schemas["similar_games"]["properties"]["tags"]["description"]   # mô tả tham số lấy từ docstring
