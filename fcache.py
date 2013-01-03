# Copyright (c) 2012-2013 Thomas Roten

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnshished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

"""a simple, persistent, file-based cache module for Python.

Classes:
    Cache: A cache that stores its data on the file system.

"""

try:
    import cPickle as pickle
except ImportError:
    import pickle
import datetime
import hashlib
import os
import tempfile

import appdirs


class Cache(object):

    """A cache that stores its data on the file system.

    It uses pickle to store objects into cache file. It uses appdirs to ensure
    that cache files are stored in platform-appropriate, application-specific
    cache directories. Cached data can optionally expire after a certain amount
    of time.

    Basic Usage:

        >>> import fcache
        >>> cache = fcache.Cache("population", "statistics-fetcher")
        >>> cache.set("chicago", 9729825)
        >>> print cache.get("chicago")
        9729825

        This code creates the cache 'population' for the application
        'statistics-fetcher'. Then, it sets the key 'chicago' to the value
        '9729825'. Next, it prints the value of 'chicago'.

    Attributes:
        cachename: the cache's name, as passed to the Cache constructor.
        cachedir: the cache's parent directory, as determined by
            appdirs.user_cache_dir().
        filename: the cache's filename. It is formed by passing cachename to
            hashlib's sha1() constructor.

    Methods:
        set: store data in the cache.
        get: get data from the cache.
        invalidate: force data to expire.
        remove: remove data from the cache.
        flush: clear all data from the cache.
        delete: delete the cache file.

    """

    def __init__(self, cachename, appname, appauthor=None):
        """Take *cachename* and *appname*, then create a cache file.

        If a matching cache file was found, a new one is not created.

        *appauthor* is used on Windows to determine the appropriate cache
        directory. If not provided, it defaults to *appname*. See appdir's
        documentation for more information.

        Args:
            cachename: (string) a unique name for the cache.
            appname: (string) the name of the application the cache is created
                for.
            appauthor: (string or None) the name of the application's author --
                if None, defaults to *appname*.

        """
        if appauthor is None or appauthor == "":
            appauthor = appname
        self.cachename = cachename.encode('utf-8')
        self.cachedir = appdirs.user_cache_dir(appname, appauthor)
        self.filename = os.path.join(self.cachedir,
                                     hashlib.sha1(self.cachename).hexdigest())
        if not os.access(self.filename, os.F_OK):
            self._create()
            self.flush()

    def set(self, key, value, timeout=None):
        """Store data in the cache.

        The data, *value*, is stored under the name, *key*, in the cache.
        The data must be picklable. Optionally, the data can expire after
        *timeout* seconds have passed.

        Args:
            key: (string) the name given to the data.
            value: the data to be stored.
            timeout: (int, long, float, or None) how long in seconds the data
                should be considered valid -- if None, defaults to forever.

        Raises:
            pickle.PicklingError: an unpicklable object was passed.
            exceptions.IOError: the cache file does not exist or cannot be
                read.

        """
        data = self._read()
        if timeout is None:
            expires = None
        else:
            expires = (datetime.datetime.now() +
                       datetime.timedelta(seconds=timeout))
        data[key] = {"expires": expires, "data": value}
        self._write(data)

    def get(self, key, override=False, default=None):
        """Get data from the cache.

        All data stored under *key* is returned. If the data is expired,
        None is returned. Expired data is returned if *override* is True.

        Args:
            key: (string) the name of the data to fetch.
            override: (bool) return expired data; defaults to False.
            default: a default value to return if key does not exist

        Returns:
            the requested data or None if the requested data has expired.

        Raises:
            exceptions.KeyError: *key* was not found.
            exceptions.IOError: the cache file does not exist or cannot be
                read.
            pickle.UnpicklingError: there was a problem unpickling an object.

        """
        data = self._read()
        try:
            if (data[key]["expires"] is None or
                    (self._total_seconds((datetime.datetime.now() -
                     data[key]["expires"])) < 0) or override):
                return data[key]["data"]
            else:
                return None
        except KeyError:
            if default is not None:
                return default
            raise

    def invalidate(self, key):
        """Force data to expire.

        After forcing *key* to expire, calling get() on *key* will return
            None.

        Args:
            key: (string) the name of the data to invalidate.

        Raises:
            exceptions.KeyError: *key* was not found.
            exceptions.IOError: the cache file does not exist or cannot be
                read.

        """
        data = self._read()
        data[key]["expires"] = datetime.datetime.now()
        self._write(data)

    def remove(self, key):
        """Remove data from the cache.

        All data stored under *key* is deleted from the cache.

        Args:
            key: (string) the name of the data to remove.

        Raises:
            exceptions.KeyError: *key* was not found.
            exceptions.IOError: the cache file does not exist or cannot be
                read.

        """
        data = self._read()
        del data[key]
        self._write(data)

    def flush(self):
        """Clear all data in the cache.

        This removes all key/value pairs from the cache.

        Raises:
            exceptions.IOError: the cache file does not exist.

        """
        if not os.access(self.filename, os.F_OK):
            raise IOError("the following cache file does not exist: %s"
                          % self.filename)
        else:
            self._write({})

    def delete(self):
        """Delete the cache file.

        On Windows, if the file is in use by another application, an exception
        is raised. See os.remove() for more information.

        Raises:
            exceptions.OSError: the cache file does not exist.

        """
        os.remove(self.filename)

    def _create(self):
        """Create a cache file."""
        if not os.access(self.cachedir, os.F_OK):
            os.makedirs(self.cachedir)
        f, tmp = tempfile.mkstemp(dir=self.cachedir)
        os.rename(tmp, self.filename)

    def _read(self):
        """Open a file and use pickle to retrieve its data"""
        with open(self.filename, "rb") as f:
            return pickle.load(f)

    def _write(self, data):
        """Open a file and use pickle to save data to it"""
        with open(self.filename, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

    def _total_seconds(self, td):
        """Calculate the number of seconds in a timedelta object."""
        return ((td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) /
                10**6)
