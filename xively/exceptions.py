"""
Exception classes.
"""

import functools
import sys

import requests


class ResourceNotFound(Exception):
    """The requested resource was not found."""


class ExceptionsWrapper(object):

    def __call__(self, func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapped

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            if issubclass(exc_type, requests.HTTPError):
                if exc_val.response.status_code == 404:
                    json = exc_val.response.json()
                    new_exc = ResourceNotFound(json['errors'])
                    # This is a nasty hack to make it work in py2 and py3
                    if sys.version_info[0] == 3:
                        new_exc.__cause__ = exc_val
                        new_exc.with_traceback(exc_tb)
                        raise new_exc
                    else:
                        exec("raise new_exc, None, exc_tb")


wrap_exceptions = ExceptionsWrapper()
