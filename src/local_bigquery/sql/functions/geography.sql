INSTALL spatial;
LOAD spatial;

CREATE MACRO _wkt(g) AS
    regexp_replace(system.main.ST_AsText(g), '([A-Z]) \(', '\1(', 'g');

CREATE MACRO _point(g, i) AS system.main.ST_PointN(g, CAST(i AS INTEGER));

CREATE MACRO _segments(g) AS list_sum(list_transform(
    range(1, system.main.ST_NPoints(g)),
    i -> system.main.ST_Distance_Sphere(bq.main._point(g, i), bq.main._point(g, i + 1))
));

CREATE MACRO _ring_area(ring) AS abs(list_sum(list_transform(
    range(1, system.main.ST_NPoints(ring)),
    i -> radians(
        system.main.ST_X(bq.main._point(ring, i + 1)) - system.main.ST_X(bq.main._point(ring, i))
    ) * (
        2 + sin(radians(system.main.ST_Y(bq.main._point(ring, i))))
        + sin(radians(system.main.ST_Y(bq.main._point(ring, i + 1))))
    )
))) * 6371008.8 * 6371008.8 / 2;

CREATE MACRO st_geogpoint(longitude, latitude) AS CASE
    WHEN latitude < -90 OR latitude > 90
        THEN error('ST_GeogPoint failed: Latitude must be between -90 and 90 degrees.')
    ELSE system.main.ST_Point(longitude, latitude)
END;

CREATE MACRO st_geogfromtext(wkt) AS CASE
    WHEN wkt IS NOT NULL AND TRY(system.main.ST_GeomFromText(wkt)) IS NULL
        THEN error('ST_GeogFromText failed: Invalid WKT: ' || wkt)
    ELSE system.main.ST_GeomFromText(wkt)
END;

CREATE MACRO st_geogfromgeojson(geojson) AS system.main.ST_GeomFromGeoJSON(geojson);

CREATE MACRO st_geogfromwkb(wkb) AS system.main.ST_GeomFromWKB(wkb);

CREATE MACRO st_astext(g) AS bq.main._wkt(g);

CREATE MACRO st_asbinary(g) AS system.main.ST_AsWKB(g);

CREATE MACRO st_asgeojson(g) AS regexp_replace(
    CAST(system.main.ST_AsGeoJSON(g) AS VARCHAR), '(\d)\.0([,\]])', '\1\2', 'g'
);

CREATE MACRO st_geometrytype(g) AS CASE system.main.ST_GeometryType(g)
    WHEN 'POINT' THEN 'ST_Point'
    WHEN 'LINESTRING' THEN 'ST_LineString'
    WHEN 'POLYGON' THEN 'ST_Polygon'
    WHEN 'MULTIPOINT' THEN 'ST_MultiPoint'
    WHEN 'MULTILINESTRING' THEN 'ST_MultiLineString'
    WHEN 'MULTIPOLYGON' THEN 'ST_MultiPolygon'
    WHEN 'GEOMETRYCOLLECTION' THEN 'ST_GeometryCollection'
END;

CREATE MACRO st_numpoints(g) AS system.main.ST_NPoints(g);

CREATE MACRO st_distance(a, b) AS system.main.ST_Distance_Sphere(
    system.main.ST_StartPoint(system.main.ST_ShortestLine(a, b)),
    system.main.ST_EndPoint(system.main.ST_ShortestLine(a, b))
);

CREATE MACRO st_dwithin(a, b, distance) AS bq.main.st_distance(a, b) <= distance;

CREATE MACRO st_length(g) AS CASE system.main.ST_GeometryType(g)
    WHEN 'LINESTRING' THEN bq.main._segments(g)
    ELSE 0.0
END;

CREATE MACRO st_perimeter(g) AS CASE system.main.ST_GeometryType(g)
    WHEN 'POLYGON' THEN bq.main._segments(system.main.ST_ExteriorRing(g))
    ELSE 0.0
END;

CREATE MACRO st_area(g) AS CASE system.main.ST_GeometryType(g)
    WHEN 'POLYGON' THEN bq.main._ring_area(system.main.ST_ExteriorRing(g))
    ELSE 0.0
END;
