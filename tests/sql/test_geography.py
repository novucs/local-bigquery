import pytest

from tests.cases import q

SQUARE = "ST_GEOGFROMTEXT('POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))')"

CASES = [
    q("SELECT ST_GEOGPOINT(1, 2)", "POINT(1 2)", types="GEOGRAPHY"),
    q("SELECT ST_ASTEXT(ST_GEOGPOINT(-122.35, 47.62))", "POINT(-122.35 47.62)"),
    q(
        "SELECT ST_ASTEXT(ST_GEOGFROMTEXT('LINESTRING(0 0, 1 1)'))",
        "LINESTRING(0 0, 1 1)",
    ),
    q(
        """SELECT ST_ASTEXT(ST_GEOGFROMGEOJSON('{"type": "Point", "coordinates": [1, 2]}'))""",
        "POINT(1 2)",
    ),
    q(
        "SELECT ST_ASTEXT(ST_GEOGFROMWKB(ST_ASBINARY(ST_GEOGPOINT(1, 2))))",
        "POINT(1 2)",
    ),
    q(
        "SELECT JSON_VALUE(ST_ASGEOJSON(ST_GEOGPOINT(1, 2)), '$.type'), "
        "JSON_VALUE(ST_ASGEOJSON(ST_GEOGPOINT(1, 2)), '$.coordinates[1]')",
        rows=[("Point", "2")],
    ),
    q(
        "SELECT ST_X(ST_GEOGPOINT(1.5, 2.5)), ST_Y(ST_GEOGPOINT(1.5, 2.5))",
        rows=[(1.5, 2.5)],
    ),
    q(
        "SELECT ST_ASTEXT(ST_MAKELINE(ST_GEOGPOINT(0, 0), ST_GEOGPOINT(0, 1)))",
        "LINESTRING(0 0, 0 1)",
    ),
    q("SELECT ST_GEOMETRYTYPE(ST_GEOGPOINT(0, 0))", "ST_Point"),
    q(
        f"SELECT ST_DIMENSION(ST_GEOGPOINT(0, 0)), "
        f"ST_DIMENSION(ST_GEOGFROMTEXT('LINESTRING(0 0, 1 1)')), ST_DIMENSION({SQUARE})",
        rows=[(0, 1, 2)],
    ),
    q("SELECT ST_NUMPOINTS(ST_GEOGFROMTEXT('LINESTRING(0 0, 1 1, 2 2)'))", 3),
    q(
        "SELECT ST_ASTEXT(ST_STARTPOINT(ST_GEOGFROMTEXT('LINESTRING(0 0, 1 1, 2 2)'))), "
        "ST_ASTEXT(ST_ENDPOINT(ST_GEOGFROMTEXT('LINESTRING(0 0, 1 1, 2 2)')))",
        rows=[("POINT(0 0)", "POINT(2 2)")],
    ),
    q("SELECT ST_ISCLOSED(ST_GEOGFROMTEXT('LINESTRING(0 0, 1 1)'))", False),
    q("SELECT ST_ISEMPTY(ST_GEOGFROMTEXT('POINT EMPTY'))", True),
    q(
        "SELECT ROUND(ST_DISTANCE(ST_GEOGPOINT(0, 0), ST_GEOGPOINT(0, 1)) / 1000, 1)",
        111.2,
        types="FLOAT64",
    ),
    q(
        "SELECT ROUND(ST_LENGTH(ST_GEOGFROMTEXT('LINESTRING(0 0, 0 1)')) / 1000, 1)",
        111.2,
    ),
    q(f"SELECT ROUND(ST_AREA({SQUARE}) / 1e6)", 12364.0),
    q(f"SELECT ROUND(ST_PERIMETER({SQUARE}) / 1000)", 445.0),
    q(
        f"SELECT ST_CONTAINS({SQUARE}, ST_GEOGPOINT(0.5, 0.5)), "
        f"ST_CONTAINS({SQUARE}, ST_GEOGPOINT(2, 2))",
        rows=[(True, False)],
    ),
    q(
        "SELECT ST_INTERSECTS(ST_GEOGFROMTEXT('LINESTRING(0 0, 1 1)'), "
        "ST_GEOGFROMTEXT('LINESTRING(0 1, 1 0)'))",
        True,
    ),
    q(
        "SELECT ST_DISJOINT(ST_GEOGPOINT(0, 0), ST_GEOGPOINT(10, 10))",
        True,
    ),
    q(
        "SELECT ST_DWITHIN(ST_GEOGPOINT(0, 0), ST_GEOGPOINT(0, 1), 200000), "
        "ST_DWITHIN(ST_GEOGPOINT(0, 0), ST_GEOGPOINT(0, 1), 100000)",
        rows=[(True, False)],
    ),
    q(
        "SELECT ST_EQUALS(ST_GEOGFROMTEXT('LINESTRING(0 0, 1 1)'), "
        "ST_GEOGFROMTEXT('LINESTRING(1 1, 0 0)'))",
        True,
    ),
    q(
        "SELECT ROUND(ST_X(ST_CENTROID(ST_GEOGFROMTEXT('MULTIPOINT(0 0, 2 0)'))), 6)",
        1.0,
    ),
    q(
        "SELECT ST_NUMPOINTS(ST_UNION_AGG(p)) "
        "FROM UNNEST([ST_GEOGPOINT(0, 0), ST_GEOGPOINT(1, 1), ST_GEOGPOINT(2, 2)]) AS p",
        3,
    ),
    q(
        "CREATE TEMP TABLE g AS SELECT ST_GEOGPOINT(1, 2) AS p; SELECT ST_ASTEXT(p) FROM g",
        "POINT(1 2)",
    ),
    q("SELECT ST_GEOGPOINT(0, 91)", error="invalidQuery"),
    q("SELECT ST_GEOGFROMTEXT('POINT(1')", error="invalidQuery"),
]


@pytest.mark.xfail(reason="GEOGRAPHY not supported")
@pytest.mark.parametrize("case", CASES)
def test_geography(check, case):
    check(case)
