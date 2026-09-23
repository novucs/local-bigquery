CREATE MACRO error(message) AS _raise(message);

CREATE MACRO iferror(a, b) AS CASE WHEN TRY([a]) IS NULL THEN b ELSE TRY([a])[1] END;

CREATE MACRO iserror(a) AS TRY([a]) IS NULL;

CREATE MACRO nulliferror(a) AS TRY(a);

CREATE MACRO nullifzero(x) AS nullif(x, 0);

CREATE MACRO zeroifnull(x) AS coalesce(x, 0);
