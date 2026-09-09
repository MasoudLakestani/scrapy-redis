from unittest import mock

from scrapy.settings import Settings

from scrapy_redis import connection, defaults
from scrapy_redis.connection import (
    from_settings,
    get_connection_pool_from_settings,
    get_redis,
    get_redis_from_settings,
)


class TestGetRedis:

    def test_default_instance(self):
        server = get_redis()
        assert isinstance(server, defaults.REDIS_CLS)

    def test_custom_class(self):
        client_cls = mock.Mock()
        server = get_redis(param="foo", redis_cls=client_cls)
        assert server is client_cls.return_value
        client_cls.assert_called_with(param="foo")

    def test_from_url(self):
        client_cls = mock.Mock()
        url = "redis://localhost"
        server = get_redis(redis_cls=client_cls, url=url, param="foo")
        assert server is client_cls.from_url.return_value
        client_cls.from_url.assert_called_with(url, param="foo")


class TestFromSettings:

    def setup(self):
        self.redis_cls = mock.Mock()
        self.expected_params = {
            "timeout": 0,
            "flag": False,
        }
        self.settings = Settings(
            {
                "REDIS_PARAMS": dict(self.expected_params, redis_cls=self.redis_cls),
            }
        )

    setup_method = setup

    def test_redis_cls_default(self):
        server = from_settings(Settings())
        assert isinstance(server, defaults.REDIS_CLS)

    def test_redis_cls_custom_path(self):
        self.settings["REDIS_PARAMS"]["redis_cls"] = "unittest.mock.Mock"
        server = from_settings(self.settings)
        assert isinstance(server, mock.Mock)

    def test_default_params(self):
        server = from_settings(self.settings)
        assert server is self.redis_cls.return_value
        call_kwargs = self.redis_cls.call_args[1]
        assert "connection_pool" in call_kwargs
        connect_kwargs = call_kwargs["connection_pool"].connection_kwargs
        for k, v in dict(defaults.REDIS_PARAMS, **self.expected_params).items():
            assert connect_kwargs[k] == v

    def test_override_default_params(self):
        for key, _ in defaults.REDIS_PARAMS.items():
            self.expected_params[key] = self.settings["REDIS_PARAMS"][key] = object()

        server = from_settings(self.settings)
        assert server is self.redis_cls.return_value
        call_kwargs = self.redis_cls.call_args[1]
        assert "connection_pool" in call_kwargs
        connect_kwargs = call_kwargs["connection_pool"].connection_kwargs
        for k, v in self.expected_params.items():
            assert connect_kwargs[k] is v


class TestConnectionPool:

    def setup_method(self):
        connection._CONNECTION_POOLS.clear()

    def teardown_method(self):
        connection._CONNECTION_POOLS.clear()

    def test_pool_cached(self):
        settings = Settings({"REDIS_HOST": "localhost", "REDIS_PORT": 6379})
        pool1 = get_connection_pool_from_settings(settings)
        pool2 = get_connection_pool_from_settings(settings)
        assert pool1 is pool2

    def test_pool_different_settings(self):
        s1 = Settings({"REDIS_HOST": "host1", "REDIS_PORT": 6379})
        s2 = Settings({"REDIS_HOST": "host2", "REDIS_PORT": 6379})
        assert get_connection_pool_from_settings(s1) is not get_connection_pool_from_settings(s2)

    def test_pool_max_connections(self):
        settings = Settings({"REDIS_MAX_CONNECTIONS": 25})
        pool = get_connection_pool_from_settings(settings)
        assert pool.max_connections == 25

    def test_existing_pool_in_params(self):
        custom_pool = mock.Mock()
        settings = Settings({"REDIS_PARAMS": {"connection_pool": custom_pool}})
        pool = get_connection_pool_from_settings(settings)
        assert pool is custom_pool
        server = from_settings(settings)
        assert server.connection_pool is custom_pool


def test_get_server_from_settings_alias():
    assert from_settings is get_redis_from_settings
