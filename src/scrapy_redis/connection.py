import redis
from scrapy.utils.misc import load_object

from . import defaults

# Shortcut maps 'setting name' -> 'parameter name'.
SETTINGS_PARAMS_MAP = {
    "REDIS_URL": "url",
    "REDIS_HOST": "host",
    "REDIS_PORT": "port",
    "REDIS_DB": "db",
    "REDIS_ENCODING": "encoding",
}

SETTINGS_PARAMS_MAP["REDIS_DECODE_RESPONSES"] = "decode_responses"

# Global registry of connection pools keyed by (url, pool_cls, params)
_CONNECTION_POOLS = {}


def _make_hashable(val):
    """Recursively convert nested dictionaries, lists, or unhashable objects
    into hashable types so they can be safely used in dictionary keys."""
    if isinstance(val, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in val.items()))
    if isinstance(val, (list, set, tuple)):
        return tuple(_make_hashable(v) for v in val)
    try:
        hash(val)
        return val
    except TypeError:
        return str(val)


def _get_pool_key(url, pool_cls, params):
    """Generate a stable, hashable key for caching connection pools."""
    return (
        url,
        pool_cls,
        tuple(sorted((k, _make_hashable(v)) for k, v in params.items())),
    )


def get_connection_pool_from_settings(settings):
    """Returns a redis ConnectionPool instance from given Scrapy settings object.

    This function caches connection pools in ``_CONNECTION_POOLS`` global
    so that multiple components (spider, scheduler, dupefilter, pipeline)
    share the same connection pool when using the same connection settings.

    Parameters
    ----------
    settings : Settings
        A scrapy settings object.

    Returns
    -------
    redis.ConnectionPool
        Redis connection pool instance.
    """
    params = defaults.REDIS_PARAMS.copy()
    params.update(settings.getdict("REDIS_PARAMS"))
    for source, dest in SETTINGS_PARAMS_MAP.items():
        val = settings.get(source)
        if val is not None:
            params[dest] = val

    # If the user already provided a connection pool, reuse it directly
    if "connection_pool" in params:
        return params["connection_pool"]

    url = params.pop("url", None)
    params.pop("redis_cls", None)

    max_connections = settings.get(
        "REDIS_MAX_CONNECTIONS", params.pop("max_connections", None)
    )
    if max_connections is not None:
        params["max_connections"] = int(max_connections)

    pool_cls = params.pop("connection_pool_cls", redis.ConnectionPool)
    if isinstance(pool_cls, str):
        pool_cls = load_object(pool_cls)

    if not url:
        params.setdefault("host", "localhost")
        params.setdefault("port", 6379)

    key = _get_pool_key(url, pool_cls, params)
    if key not in _CONNECTION_POOLS:
        if url:
            _CONNECTION_POOLS[key] = pool_cls.from_url(url, **params)
        else:
            _CONNECTION_POOLS[key] = pool_cls(**params)

    return _CONNECTION_POOLS[key]


def get_redis_from_settings(settings):
    """Returns a redis client instance from given Scrapy settings object.

    This function uses ``get_connection_pool_from_settings`` to obtain a
    shared connection pool and instantiates the client using that pool.

    Parameters
    ----------
    settings : Settings
        A scrapy settings object.

    Returns
    -------
    server
        Redis client instance.
    """
    params = defaults.REDIS_PARAMS.copy()
    params.update(settings.getdict("REDIS_PARAMS"))
    for source, dest in SETTINGS_PARAMS_MAP.items():
        val = settings.get(source)
        if val is not None:
            params[dest] = val

    redis_cls = params.pop("redis_cls", defaults.REDIS_CLS)
    if isinstance(redis_cls, str):
        redis_cls = load_object(redis_cls)

    # If a custom connection_pool was explicitly provided, pass it directly
    if "connection_pool" in params:
        return redis_cls(**params)

    pool = get_connection_pool_from_settings(settings)
    return redis_cls(connection_pool=pool)


# Backwards compatible alias.
from_settings = get_redis_from_settings


def get_redis(**kwargs):
    """Returns a redis client instance.

    Parameters
    ----------
    redis_cls : class, optional
        Defaults to ``redis.StrictRedis``.
    url : str, optional
        If given, ``redis_cls.from_url`` is used to instantiate the class.
    **kwargs
        Extra parameters to be passed to the ``redis_cls`` class.

    Returns
    -------
    server
        Redis client instance.
    """
    redis_cls = kwargs.pop("redis_cls", defaults.REDIS_CLS)
    url = kwargs.pop("url", None)
    if url:
        return redis_cls.from_url(url, **kwargs)
    else:
        return redis_cls(**kwargs)
