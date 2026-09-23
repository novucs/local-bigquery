CREATE MACRO _net_authority(url) AS regexp_extract(
    regexp_replace(trim(url), '^([a-zA-Z][a-zA-Z0-9+.-]*:)?//', ''), '^[^/?#]*'
);

CREATE MACRO _net_server(authority) AS regexp_replace(authority, '^.*@', '');

CREATE MACRO _net_host(url) AS nullif(CASE
    WHEN starts_with(bq.main._net_server(bq.main._net_authority(url)), '[')
        THEN regexp_extract(bq.main._net_server(bq.main._net_authority(url)), '^\[[^\]]*\]')
    ELSE regexp_replace(bq.main._net_server(bq.main._net_authority(url)), ':.*$', '')
END, '');

CREATE MACRO _net_suffix(host) AS CASE
    WHEN lower(regexp_extract(host, '[^.]+\.[^.]+$')) IN (
        'co.uk', 'org.uk', 'ac.uk', 'gov.uk', 'me.uk', 'net.uk', 'ltd.uk', 'plc.uk',
        'com.au', 'net.au', 'org.au', 'edu.au', 'gov.au', 'co.nz', 'org.nz', 'govt.nz',
        'co.jp', 'ne.jp', 'or.jp', 'ac.jp', 'go.jp', 'co.kr', 'or.kr', 'com.cn', 'net.cn',
        'org.cn', 'gov.cn', 'com.hk', 'com.tw', 'com.sg', 'com.my', 'co.in', 'net.in',
        'org.in', 'gov.in', 'co.id', 'co.th', 'com.br', 'net.br', 'org.br', 'gov.br',
        'com.ar', 'com.mx', 'com.co', 'com.tr', 'co.za', 'org.za', 'co.il', 'com.ua',
        'com.pl', 'co.at', 'or.at'
    ) THEN regexp_extract(host, '[^.]+\.[^.]+$')
    WHEN regexp_full_match(lower(regexp_extract(host, '[^.]+$')), '[a-z]{2}') OR
        lower(regexp_extract(host, '[^.]+$')) IN (
            'com', 'org', 'net', 'edu', 'gov', 'mil', 'int', 'info', 'biz', 'name',
            'pro', 'aero', 'coop', 'museum', 'mobi', 'asia', 'tel', 'travel', 'jobs',
            'xyz', 'app', 'dev', 'page', 'cloud', 'online', 'site', 'store', 'tech',
            'blog', 'shop', 'io', 'ai', 'google', 'goog'
        ) THEN regexp_extract(host, '[^.]+$')
END;

CREATE MACRO _net_public_suffix(url) AS bq.main._net_suffix(bq.main._net_host(url));

CREATE MACRO _net_reg_domain(url) AS nullif(regexp_extract(
    bq.main._net_host(url),
    '[^.]+\.' || regexp_escape(bq.main._net_public_suffix(url)) || '$'
), '');

CREATE MACRO _net_ip_from_string(s) AS _ip_from_string(s);

CREATE MACRO _net_safe_ip_from_string(s) AS TRY(_ip_from_string(s));

CREATE MACRO _net_ip_to_string(b) AS _ip_to_string(b);

CREATE MACRO _net_ip_net_mask(n, prefix) AS _ip_net_mask(n, prefix);

CREATE MACRO _net_ip_trunc(b, prefix) AS _ip_trunc(b, prefix);

CREATE MACRO _net_ipv4_from_int64(i) AS CASE
    WHEN i < -2147483648 OR i > 4294967295
        THEN _raise('NET.IPV4_FROM_INT64() encountered a non-IPv4 integer: ' || i)
    ELSE unhex(printf('%08x', i & 4294967295))
END;

CREATE MACRO _net_ipv4_to_int64(b) AS CASE
    WHEN octet_length(b) <> 4
        THEN _raise('NET.IPV4_TO_INT64() encountered a non-IPv4 address. Expected 4 bytes but got ' || octet_length(b))
    ELSE CAST('0x' || hex(b) AS BIGINT)
END;
