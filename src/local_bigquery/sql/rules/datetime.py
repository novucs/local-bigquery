import re

from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import macro

Type = exp.DataType.Type
WEEKDAYS = "SUNDAY MONDAY TUESDAY WEDNESDAY THURSDAY FRIDAY SATURDAY".split()
TIMESTAMP_UNITS = {"MICROSECOND", "MILLISECOND", "SECOND", "MINUTE", "HOUR", "DAY"}
INTERVAL_FIELDS = ["year", "month", "day", "hour", "minute", "second"]
OFFSET = re.compile(r"^([+-])(\d{1,2})(?::?(\d{2}))?$")
FORMAT_MODEL = re.compile(
    r'"[^"]*"|YYYY|RRRR|YY|RR|MONTH|MON|MM|DDD|DD|DAY|DY|D|HH24|HH12|HH|MI|SSSSS|SS'
    r"|FF[1-9]|AM|PM|TZH|TZM|[-.,/;: ]",
    re.IGNORECASE,
)
FORMAT_MODEL_ELEMENTS = {
    "YYYY": "%Y",
    "RRRR": "%Y",
    "YY": "%y",
    "RR": "%y",
    "MONTH": "%B",
    "MON": "%b",
    "MM": "%m",
    "DDD": "%j",
    "DD": "%d",
    "DAY": "%A",
    "DY": "%a",
    "HH24": "%H",
    "HH12": "%I",
    "HH": "%I",
    "MI": "%M",
    "SS": "%S",
    "AM": "%p",
    "PM": "%p",
}
NAMED_ELEMENTS = {"MONTH", "MON", "DAY", "DY", "AM", "PM"}
FORMAT_ELEMENTS = re.compile(r"(%E(?:\d|\*)S|%E4Y|%Ez|%Q|%s|%z|%Z|%R|%Y)")


def call(name: str, *args) -> exp.Anonymous:
    return exp.Anonymous(this=name, expressions=[exp.convert(arg) for arg in args])


def _around(node: exp.Expression, build) -> None:
    placeholder = exp.null()
    node.replace(build(placeholder))
    placeholder.replace(node)


def _offset_minutes(zone: exp.Expression | None) -> int | None:
    match = isinstance(zone, exp.Literal) and OFFSET.match(zone.this)
    if not match:
        return None
    minutes = int(match[2]) * 60 + int(match[3] or 0)
    return -minutes if match[1] == "-" else minutes


def to_local(timestamp: exp.Expression, zone: exp.Expression | None) -> exp.Expression:
    minutes = _offset_minutes(zone)
    if minutes is not None:
        return exp.Add(
            this=call("timezone", "UTC", timestamp),
            expression=call("to_minutes", minutes),
        )
    return call("timezone", zone or "UTC", timestamp)


def from_local(local: exp.Expression, zone: exp.Expression | None) -> exp.Expression:
    minutes = _offset_minutes(zone)
    if minutes is not None:
        local = exp.Sub(this=local, expression=call("to_minutes", minutes))
        zone = None
    return call("timezone", zone or "UTC", local)


def _extract(node: exp.Extract) -> exp.Expression | None:
    part, value = node.this, node.expression
    if isinstance(part, exp.WeekStart):
        return macro("_week", value, exp.convert(WEEKDAYS.index(part.name.upper())))
    match part.name.upper():
        case "DAYOFWEEK":
            return exp.Add(this=call("dayofweek", value), expression=exp.convert(1))
        case "WEEK":
            return macro("_week", value, exp.convert(0))
        case "ISOWEEK":
            return call("week", value)
        case "ISOYEAR":
            return call("isoyear", value)
        case "DATE" | "TIME" | "DATETIME" as kind:
            return exp.cast(value, "TIMESTAMP" if kind == "DATETIME" else kind)
    return None


def _date_trunc(node: exp.DateTrunc) -> exp.Expression:
    unit, value = node.args["unit"], node.this
    if isinstance(unit, exp.WeekStart):
        return macro(
            "_week_start", value, exp.convert(WEEKDAYS.index(unit.name.upper()))
        )
    name = unit.name.upper()
    if name == "WEEK":
        return macro("_week_start", value, exp.convert(0))
    part = "week" if name == "ISOWEEK" else name.lower()
    return exp.cast(call("date_trunc", part, value), "DATE")


def _format(node: exp.TimeToStr) -> exp.Expression | None:
    template = node.args.get("format")
    if not isinstance(template, exp.Literal):
        return None
    value, zone = node.this, node.args.get("zone")
    instant = None
    if isinstance(value, exp.TsOrDsToTimestamp):
        instant = exp.cast(value.this, "TIMESTAMPTZ")
        local = to_local(instant, zone)
    elif isinstance(value, exp.TsOrDsToTime):
        local = exp.Add(
            this=exp.cast(exp.convert("1970-01-01"), "DATE"),
            expression=exp.cast(value.this, "TIME"),
        )
    elif isinstance(value, exp.TsOrDsToDate):
        local = exp.cast(value.this, "DATE")
    else:
        local = exp.cast(
            value.this if isinstance(value, exp.TsOrDsToDatetime) else value,
            "TIMESTAMP",
        )
    pieces = []
    for piece in FORMAT_ELEMENTS.split(template.this):
        if not piece:
            continue
        pieces.append(_element(piece, local, instant, zone))
    return exp.cast(_concat(pieces), "VARCHAR")


def _offset_seconds(local: exp.Expression, instant: exp.Expression | None):
    if instant is None:
        return exp.convert(0)
    seconds = exp.Sub(
        this=call("epoch", local.copy()), expression=call("epoch", instant.copy())
    )
    return exp.cast(seconds, "BIGINT")


def _element(piece: str, local, instant: exp.Expression | None, zone):
    offset = _offset_seconds(local, instant)
    match piece:
        case "%Q":
            return exp.cast(call("quarter", local.copy()), "VARCHAR")
        case "%Y":
            return exp.cast(call("year", local.copy()), "VARCHAR")
        case "%E4Y":
            return call("lpad", exp.cast(call("year", local.copy()), "VARCHAR"), 4, "0")
        case "%Ez":
            return macro("_offset", offset, exp.convert(":"), exp.true())
        case "%z":
            return macro("_offset", offset, exp.convert(""), exp.true())
        case "%Z" if instant is not None:
            return call("_zone_name", call("epoch", instant.copy()), zone or "UTC")
        case "%s":
            source = instant if instant is not None else local
            return exp.cast(exp.cast(call("epoch", source.copy()), "BIGINT"), "VARCHAR")
        case "%R":
            return exp.TimeToStr(this=local.copy(), format=exp.convert("%H:%M"))
    if match := re.fullmatch(r"%E(\d|\*)S", piece):
        return macro(
            "_seconds",
            local.copy(),
            exp.convert(6 if match[1] == "*" else int(match[1])),
        )
    return exp.TimeToStr(this=local.copy(), format=exp.convert(piece))


def _concat(pieces: list[exp.Expression]) -> exp.Expression:
    result = pieces[0]
    for piece in pieces[1:]:
        result = exp.DPipe(this=result, expression=piece)
    return result


def _parse_timestamp(node: exp.StrToTime) -> exp.Expression:
    zone = node.args.get("zone")
    node.set("zone", None)
    template = node.args.get("format")
    if isinstance(template, exp.Literal) and "%Ez" in template.this:
        template.replace(exp.convert(template.this.replace("%Ez", "%z")))
    template = node.args.get("format")
    if isinstance(template, exp.Literal) and "%Z" in template.this:
        node.set("this", call("_zone_checked", template.copy(), node.this))
    if isinstance(template, exp.Literal) and (
        "%z" in template.this or "%Z" in template.this
    ):
        return None
    _around(node, lambda placeholder: from_local(placeholder, zone))
    return None


def _interval(node: exp.Interval) -> exp.Expression | None:
    unit = node.args.get("unit")
    if not isinstance(unit, exp.IntervalSpan) or not isinstance(node.this, exp.Literal):
        return None
    fields = INTERVAL_FIELDS[INTERVAL_FIELDS.index(unit.this.name.lower()) :]
    values = []
    for token in node.this.this.split():
        sign = -1 if token.startswith("-") else 1
        separator = (
            "-"
            if not values
            and fields[0] in ("year", "month")
            and "-" in token.lstrip("-")
            else ":"
        )
        values += [sign * float(part) for part in token.lstrip("-+").split(separator)]
    text = " ".join(f"{value:g} {field}" for value, field in zip(values, fields))
    return exp.Interval(this=exp.convert(text))


def _is_interval(node: exp.Expression) -> bool:
    if isinstance(node, (exp.Interval, exp.MakeInterval)):
        return True
    if isinstance(node, exp.Anonymous):
        return node.name.lower() in (
            "to_days",
            "bq.main.justify_hours",
            "bq.main.justify_days",
            "bq.main.justify_interval",
        )
    return False


def _is_date(node: exp.Expression) -> bool:
    return isinstance(node, exp.Cast) and node.to.is_type(exp.DataType.Type.DATE)


def datetime(tree: exp.Expression, context) -> exp.Expression:
    for node in list(tree.find_all(exp.Interval)):
        if replacement := _interval(node):
            node.replace(replacement)
    for node in list(tree.find_all(exp.Sub)):
        if _is_date(node.this) and _is_date(node.expression):
            wrapper = call("to_days", exp.null())
            node.replace(wrapper)
            wrapper.set("expressions", [exp.cast(node, "INTEGER")])
    for node in list(tree.find_all(exp.Cast)):
        if node.to.is_type(*exp.DataType.TEXT_TYPES) and _is_interval(node.this):
            node.replace(macro("_interval_string", node.this))
    for node in reversed(list(tree.find_all(exp.Expression))):
        replacement = _rewrite(node)
        if replacement is not None and replacement is not node:
            node.replace(replacement)
    return tree


def _local(node: exp.Expression, kind: str) -> exp.Expression:
    instant = exp.cast(node.this, "TIMESTAMPTZ")
    return exp.cast(to_local(instant, node.args["zone"]), kind)


def _offset_zone(node: exp.Expression) -> bool:
    return _offset_minutes(node.args.get("zone")) is not None


def _rewrite(node: exp.Expression) -> exp.Expression | None:
    match node:
        case exp.AtTimeZone() if _offset_zone(node):
            return to_local(exp.cast(node.this, "TIMESTAMPTZ"), node.args["zone"])
        case exp.Date() if _offset_zone(node):
            return _local(node, "DATE")
        case exp.Time() if _offset_zone(node):
            return _local(node, "TIME")
        case exp.TsOrDsToTime() if not isinstance(node.parent, exp.TimeToStr):
            return exp.cast(exp.cast(node.this, "TIMESTAMP"), "TIME")
        case exp.TimestampTrunc() if _offset_zone(node):
            zone = node.args["zone"]
            local = to_local(exp.cast(node.this, "TIMESTAMPTZ"), zone)
            return from_local(
                call("date_trunc", node.text("unit").lower(), local), zone
            )
        case exp.Extract():
            return _extract(node)
        case exp.DateAdd() | exp.DateSub() | exp.DateFromUnixDate():
            _around(node, lambda placeholder: exp.cast(placeholder, "DATE", copy=False))
        case exp.TimestampAdd() | exp.TimestampSub() if (
            node.text("unit").upper() not in TIMESTAMP_UNITS
        ):
            raise BigQueryError(
                "invalidQuery",
                f"Unsupported date part {node.text('unit').upper()} for TIMESTAMP_ADD",
            )
        case exp.TimestampDiff():
            return call(
                "date_sub", node.text("unit").lower(), node.expression, node.this
            )
        case exp.DateTrunc():
            return _date_trunc(node)
        case exp.TimeTrunc():
            epoch = exp.cast(exp.convert("1970-01-01"), "DATE")
            local = exp.Add(this=epoch, expression=node.this)
            return exp.cast(
                call("date_trunc", node.text("unit").lower(), local), "TIME"
            )
        case exp.TimeToStr():
            return _format(node)
        case exp.StrToTime() if not isinstance(node, exp.ParseDatetime):
            return _parse_timestamp(node)
        case exp.UnixSeconds():
            micros = exp.Div(
                this=call("epoch_us", node.this), expression=exp.convert(1000000)
            )
            return exp.cast(call("floor", micros), "BIGINT")
        case exp.UnixToTime() if node.args.get("scale") is not None:
            _around(
                node,
                lambda placeholder: exp.cast(placeholder, "TIMESTAMPTZ", copy=False),
            )
        case exp.GenerateTimestampArray():
            return call(
                "generate_series",
                exp.cast(node.args["start"], "TIMESTAMPTZ"),
                exp.cast(node.args["end"], "TIMESTAMPTZ"),
                node.args["step"],
            )
        case exp.String() if node.args.get("zone") is not None:
            instant = exp.cast(node.this, "TIMESTAMPTZ")
            return macro(
                "_timestamp_string",
                instant,
                to_local(instant.copy(), node.args["zone"]),
            )
        case exp.Datetime() if (
            isinstance(node.expression, exp.Literal) and node.expression.is_string
        ):
            return to_local(exp.cast(node.this, "TIMESTAMPTZ"), node.expression)
    return None


def _model_element(token: str, local: exp.Expression, offset: exp.Expression):
    element = token.upper()
    if token.startswith('"'):
        return exp.convert(token[1:-1])
    if element in FORMAT_MODEL_ELEMENTS:
        text = call("strftime", local.copy(), FORMAT_MODEL_ELEMENTS[element])
        if element in NAMED_ELEMENTS and token.isupper():
            return call("upper", text)
        if element in NAMED_ELEMENTS and token.islower():
            return call("lower", text)
        return text
    if element == "D":
        weekday = exp.Add(
            this=call("dayofweek", local.copy()), expression=exp.convert(1)
        )
        return exp.cast(weekday, "VARCHAR")
    if element == "SSSSS":
        seconds = exp.cast(call("epoch", exp.cast(local.copy(), "TIME")), "BIGINT")
        return call("lpad", exp.cast(seconds, "VARCHAR"), 5, "0")
    if element.startswith("FF"):
        return call("rpad", call("strftime", local.copy(), "%f"), int(element[2]), "0")
    if element == "TZH":
        sign = exp.If(
            this=exp.LT(this=offset.copy(), expression=exp.convert(0)),
            true=exp.convert("-"),
            false=exp.convert("+"),
        )
        return call(
            "printf",
            "%s%02d",
            sign,
            exp.IntDiv(this=call("abs", offset.copy()), expression=exp.convert(3600)),
        )
    if element == "TZM":
        minutes = exp.IntDiv(
            this=exp.Mod(this=call("abs", offset.copy()), expression=exp.convert(3600)),
            expression=exp.convert(60),
        )
        return call("printf", "%02d", minutes)
    return exp.convert(token)


def format_cast(node: exp.Expression, context) -> exp.Expression:
    if not (isinstance(node, exp.Cast) and node.args.get("format")):
        return node
    template, zone = node.args["format"], None
    if isinstance(template, exp.AtTimeZone):
        template, zone = template.this, template.args["zone"]
    kind = node.this.type.this if node.this.type else None
    instant = None
    if kind == Type.TIMESTAMPTZ:
        instant = exp.cast(node.this, "TIMESTAMPTZ")
        local = to_local(instant, zone)
    elif kind == Type.TIME:
        local = exp.Add(
            this=exp.cast(exp.convert("1970-01-01"), "DATE"),
            expression=exp.cast(node.this, "TIME"),
        )
    elif kind in (Type.DATE, Type.TIMESTAMP):
        local = exp.cast(node.this, "TIMESTAMP")
    else:
        raise BigQueryError(
            "invalidQuery",
            f"CAST with FORMAT is not supported for {kind or 'this type'}",
        )
    text, pieces, position = template.name, [], 0
    for match in FORMAT_MODEL.finditer(text):
        if match.start() != position:
            break
        pieces.append(_model_element(match[0], local, _offset_seconds(local, instant)))
        position = match.end()
    if position != len(text):
        name = exp.DataType.build(kind).sql(dialect="bigquery")
        raise BigQueryError(
            "invalidQuery", f"{name} does not support '{text[position]}'"
        )
    return exp.cast(_concat(pieces), "VARCHAR") if pieces else exp.convert("")


STATEMENT_RULES = [datetime]
NODE_RULES = [format_cast]
