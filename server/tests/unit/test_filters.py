"""Unit tests for FileListFilters and the filter -> SQLAlchemy clause builder.

No DB engine or connection: clauses are asserted by compiling the built
``select()`` to a string, not by executing it. See docs/design/testing.md.
"""

import pytest
from pydantic import ValidationError

from server.db.filters import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    FileListFilters,
    build_file_query,
)


def _compiled(query):
    return str(query.compile(compile_kwargs={"literal_binds": True}))


def test_defaults_when_no_query_params_given():
    filters = FileListFilters()

    assert filters.limit == DEFAULT_LIMIT
    assert filters.offset == 0
    assert filters.name is None
    assert filters.min_duration is None


def test_no_filters_gives_unfiltered_select():
    query = build_file_query(FileListFilters())

    assert query.whereclause is None


def test_limit_over_cap_is_rejected():
    with pytest.raises(ValidationError):
        FileListFilters(limit=MAX_LIMIT + 1)


def test_categorical_field_accepts_repeated_values():
    filters = FileListFilters(channels=[1, 2])

    assert filters.channels == [1, 2]


def test_scalar_field_rejects_non_numeric_input():
    with pytest.raises(ValidationError):
        FileListFilters(min_duration="not-a-number")


def test_one_categorical_filter_produces_in_clause():
    query = build_file_query(FileListFilters(channels=[1, 2]))

    assert "files.channels IN (1, 2)" in _compiled(query)


def test_one_scalar_bound_produces_comparison_clause():
    query = build_file_query(FileListFilters(min_duration=5.0))

    assert "files.duration_seconds >=" in _compiled(query)


def test_combined_filters_are_anded_together():
    query = build_file_query(FileListFilters(channels=[1], min_duration=5.0))

    compiled = _compiled(query)
    assert " AND " in compiled
    assert "files.channels IN (1)" in compiled
    assert "files.duration_seconds >=" in compiled
