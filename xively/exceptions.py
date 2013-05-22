"""
Exception classes.
"""

import functools
import sys

from requests.exceptions import *  # NOQA


class ApiError(Exception):
    pass


class ResourceNotFound(ApiError):
    """The requested resource was not found."""


class Forbidden(ApiError):
    """You do not have the necessary permissions to access this resource."""


class ExceptionsWrapper(object):

    HTTP_ERRORS = {
        403: Forbidden,
        404: ResourceNotFound,
    }

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
            if issubclass(exc_type, HTTPError):
                new_class = self.HTTP_ERRORS.get(exc_val.response.status_code)
                if new_class is None:
                    # This causes the existing exception to be reraised.
                    return

                json = exc_val.response.json()
                new_exc = new_class(json['errors'])

                # This will only be shown in py3 but we can store it for py2
                # users if they know what they're looking for.
                new_exc.__cause__ = exc_val

                # This is a nasty hack to make it work in py2 and py3
                if sys.version_info[0] == 3:  # pragma: no cover
                    new_exc.with_traceback(exc_tb)
                    raise new_exc
                else:
                    exec("raise new_exc, None, exc_tb")


wrap_exceptions = ExceptionsWrapper()
