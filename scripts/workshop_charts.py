from __future__ import annotations

from workshop_schema import ChartSpec


def line_chart(title: str, data: list[dict], x: str, y: str, series: str | None = None) -> ChartSpec:
    return ChartSpec(type="line", title=title, x=x, y=y, series=series, data=data)


def horizontal_bar_chart(title: str, data: list[dict], x: str, y: str) -> ChartSpec:
    return ChartSpec(type="horizontal_bar", title=title, x=x, y=y, data=data)


def bar_chart(title: str, data: list[dict], x: str, y: str) -> ChartSpec:
    return ChartSpec(type="bar", title=title, x=x, y=y, data=data)


def table_chart(title: str, data: list[dict]) -> ChartSpec:
    return ChartSpec(type="table", title=title, data=data)
