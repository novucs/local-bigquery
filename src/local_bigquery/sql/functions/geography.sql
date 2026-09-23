INSTALL spatial;
LOAD spatial;

CREATE MACRO _wkt(g) AS
    regexp_replace(system.main.ST_AsText(g), '([A-Z]) \(', '\1(', 'g');

CREATE MACRO _point(g, i) AS system.main.ST_PointN(g, CAST(i AS INTEGER));

CREATE MACRO _radius() AS 6371010.0;

CREATE MACRO _unit(g) AS [
    cos(radians(system.main.ST_Y(g))) * cos(radians(system.main.ST_X(g))),
    cos(radians(system.main.ST_Y(g))) * sin(radians(system.main.ST_X(g))),
    sin(radians(system.main.ST_Y(g)))
];

CREATE MACRO _arc(a, b) AS
    2 * asin(least(1, list_distance(bq.main._unit(a), bq.main._unit(b)) / 2));

CREATE MACRO _arcs(line) AS coalesce(list_sum(list_transform(
    range(1, system.main.ST_NPoints(line)),
    i -> bq.main._arc(bq.main._point(line, i), bq.main._point(line, i + 1))
)), 0);

CREATE MACRO _excess(a, b) AS 2 * atan2(
    tan(radians(system.main.ST_X(b) - system.main.ST_X(a)) / 2)
    * (tan(radians(system.main.ST_Y(a)) / 2) + tan(radians(system.main.ST_Y(b)) / 2)),
    1 + tan(radians(system.main.ST_Y(a)) / 2) * tan(radians(system.main.ST_Y(b)) / 2)
);

CREATE MACRO _ring_area(ring) AS abs(coalesce(list_sum(list_transform(
    range(1, system.main.ST_NPoints(ring)),
    i -> bq.main._excess(bq.main._point(ring, i), bq.main._point(ring, i + 1))
)), 0));

CREATE MACRO _holes(polygon) AS list_transform(
    range(1, system.main.ST_NumInteriorRings(polygon) + 1),
    i -> system.main.ST_InteriorRingN(polygon, CAST(i AS INTEGER))
);

CREATE MACRO _parts(g, kind) AS list_transform(
    list_filter(system.main.ST_Dump(g), part -> system.main.ST_GeometryType(part.geom) = kind),
    part -> part.geom
);

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

CREATE MACRO st_asgeojson(g) AS CASE
    WHEN system.main.ST_IsEmpty(g) THEN '{ "type": "GeometryCollection", "geometries": [ ] } '
    ELSE regexp_replace(
        CAST(system.main.ST_AsGeoJSON(g) AS VARCHAR), '(\d)\.0([,\]])', '\1\2', 'g'
    )
END;

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

CREATE MACRO st_iscollection(g) AS
    system.main.ST_GeometryType(g) IN ('MULTIPOINT', 'MULTILINESTRING', 'MULTIPOLYGON', 'GEOMETRYCOLLECTION')
    AND system.main.ST_NumGeometries(g) > 1;

CREATE MACRO st_intersectsbox(g, lng1, lat1, lng2, lat2) AS
    system.main.ST_Intersects(g, system.main.ST_MakeEnvelope(lng1, lat1, lng2, lat2));

CREATE MACRO st_makepolygonoriented(rings) AS
    system.main.ST_MakePolygon(rings[1], rings[2:]);

CREATE MACRO st_snaptogrid(g, size) AS system.main.ST_ReducePrecision(g, size);

CREATE MACRO st_distance(a, b) AS bq.main._radius() * bq.main._arc(
    system.main.ST_StartPoint(system.main.ST_ShortestLine(a, b)),
    system.main.ST_EndPoint(system.main.ST_ShortestLine(a, b))
);

CREATE MACRO st_maxdistance(a, b) AS bq.main._radius() * list_max(list_transform(
    system.main.ST_Dump(system.main.ST_Points(a)),
    p -> list_max(list_transform(
        system.main.ST_Dump(system.main.ST_Points(b)),
        q -> bq.main._arc(p.geom, q.geom)
    ))
));

CREATE MACRO st_dwithin(a, b, distance) AS bq.main.st_distance(a, b) <= distance;

CREATE MACRO st_length(g) AS bq.main._radius() * coalesce(list_sum(list_transform(
    bq.main._parts(g, 'LINESTRING'), line -> bq.main._arcs(line)
)), 0);

CREATE MACRO st_perimeter(g) AS bq.main._radius() * coalesce(list_sum(list_transform(
    bq.main._parts(g, 'POLYGON'),
    polygon -> bq.main._arcs(system.main.ST_ExteriorRing(polygon))
        + coalesce(list_sum(list_transform(bq.main._holes(polygon), h -> bq.main._arcs(h))), 0)
)), 0);

CREATE MACRO st_area(g) AS pow(bq.main._radius(), 2) * coalesce(list_sum(list_transform(
    bq.main._parts(g, 'POLYGON'),
    polygon -> bq.main._ring_area(system.main.ST_ExteriorRing(polygon))
        - coalesce(list_sum(list_transform(
            bq.main._holes(polygon), h -> bq.main._ring_area(h)
        )), 0)
)), 0);
