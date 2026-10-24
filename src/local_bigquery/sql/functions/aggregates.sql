CREATE MACRO approx_quantiles(x, n) AS quantile_disc(x, list_transform(range(n + 1), lambda i: i / n));

CREATE MACRO approx_top_count(x, n) AS list_transform(
    list_slice(list_sort(list_transform(map_entries(histogram(x)), lambda e: {'c': -CAST(e.value AS BIGINT), 'v': e.key})), 1, n),
    lambda e: {'value': e.v, 'count': -e.c}
);

CREATE MACRO _top_sum(l, n) AS list_transform(
    list_slice(list_sort(list_transform(
        list_distinct(list_transform(l, lambda e: e.v)),
        lambda v: {'s': -list_sum(list_transform(list_filter(l, lambda e: e.v = v), lambda e: e.w)), 'v': v}
    )), 1, n),
    lambda e: {'value': e.v, 'sum': -e.s}
);

CREATE MACRO approx_top_sum(x, w, n) AS bq.main._top_sum(list({'v': x, 'w': w}), n);

CREATE MACRO _hll_init(x) AS list_distinct(list(x));

CREATE MACRO _hll_merge_partial(s) AS list_distinct(flatten(list(s)));

CREATE MACRO _hll_merge(s) AS coalesce(len(list_distinct(flatten(list(s)))), 0);

CREATE MACRO _hll_extract(s) AS coalesce(len(s), 0);
