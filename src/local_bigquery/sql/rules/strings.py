import re

from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import macro
from local_bigquery.sql.rules.typing import BYTES, FLOATS, TEXT, kind

ESCAPE = re.compile(
    r"\\(?:u([0-9a-fA-F]{4})|U([0-9a-fA-F]{8})|x([0-9a-fA-F]{2})|([0-7]{3}))"
)
SPECIFIER = re.compile(r"%(?:%|[-+ #0']*\d*(?:\.\d+)?[a-zA-Z])")


def string_escapes(node: exp.Expression, context) -> exp.Expression:
    if not (isinstance(node, exp.Literal) and node.is_string and "\\" in node.this):
        return node
    decoded = ESCAPE.sub(
        lambda m: chr(int(m[1] or m[2] or m[3], 16) if not m[4] else int(m[4], 8)),
        node.this,
    )
    return exp.Literal.string(decoded)


def format_(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.Format):
        return node
    template, args = node.this, list(node.expressions)
    if isinstance(template, exp.Literal) and template.is_string:
        index = 0

        def specifier(match: re.Match) -> str:
            nonlocal index
            spec = match.group(0)
            if spec == "%%":
                return spec
            if spec[-1] in "tT" and index < len(args):
                args[index] = exp.Cast(
                    this=args[index], to=exp.DataType.build("VARCHAR")
                )
                spec = spec[:-1] + "s"
            index += 1
            return spec

        template = exp.Literal.string(SPECIFIER.sub(specifier, template.this))
    return exp.Anonymous(this="printf", expressions=[template, *args])


def regexp_extract(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.RegexpExtract) or node.args.get("position"):
        return node
    matches = exp.Anonymous(
        this="regexp_matches", expressions=[node.this.copy(), node.expression.copy()]
    )
    return exp.If(this=matches, true=node)


def collate(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.Collate) or not isinstance(
        node.expression, exp.Literal
    ):
        return node
    name = node.expression.this.lower()
    if name == "und:ci":
        return exp.Collate(this=node.this, expression=exp.var("NOCASE"))
    if name:
        raise BigQueryError(
            "invalidQuery",
            f"Collation '{node.expression.this}' in collate function is not supported.",
        )
    return node.this


def like_escape(node: exp.Expression, context) -> exp.Expression:
    if (
        isinstance(node, exp.Like)
        and not isinstance(node.expression, (exp.Any, exp.All))
        and not isinstance(node.parent, exp.Escape)
    ):
        return exp.Escape(this=node, expression=exp.Literal.string("\\"))
    return node


def float_to_string(node: exp.Expression, context) -> exp.Expression:
    if not (isinstance(node, exp.Cast) and node.to.this in TEXT):
        return node
    if kind(node.this) not in FLOATS:
        return node
    return exp.Anonymous(
        this="regexp_replace",
        expressions=[node, exp.Literal.string(r"\.0$"), exp.Literal.string("")],
    )


def normalize(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.Normalize):
        return node
    form = node.args.get("form")
    return exp.Anonymous(
        this="_normalize",
        expressions=[
            node.this,
            exp.Literal.string(form.name if form else "NFC"),
            exp.Boolean(this=bool(node.args.get("is_casefold"))),
        ],
    )


def _binary(node: exp.Expression) -> bool:
    if isinstance(node, exp.Anonymous) and node.name.lower() == "from_hex":
        return True
    return isinstance(node, exp.ByteString) or kind(node) in BYTES


def upper(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Upper) and not _binary(node.this):
        sharp = [node.this, exp.Literal.string("ß"), exp.Literal.string("SS")]
        node.set("this", exp.Anonymous(this="replace", expressions=sharp))
    return node


def concat(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Concat) and kind(node) in TEXT:
        return exp.cast(node, exp.DataType.build("VARCHAR"), copy=False)
    return node


def net(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.NetFunc):
        return node
    function = node.this
    if isinstance(function, exp.Anonymous):
        return macro(f"_net_{function.name.lower()}", *function.expressions)
    return macro(f"_net_{function.sql_name().lower()}", function.this)


NODE_RULES = [
    net,
    string_escapes,
    format_,
    regexp_extract,
    collate,
    like_escape,
    float_to_string,
    normalize,
    upper,
    concat,
]
