# -*- mode: python; indent-tabs-mode: nil -*-

# Part of mlat-client - an ADS-B multilateration client.
# Copyright 2015, Oliver Jowett <oliver@mutability.co.uk>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Common networking bits, based on asyncore
"""

import sys
import socket
import asyncore
from mlat.client.util import (log, log_exc, monotonic_time,
                               STATE_DISCONNECTED, STATE_CONNECTED, STATE_READY)

import random
random.seed()

__all__ = ('LoggingMixin', 'ReconnectingConnection')


class LoggingMixin:
    """A mixin that redirects asyncore's logging to the client's
    global logging."""

    def log(self, message):
        log('{0}', message)

    def log_info(self, message, type='info'):
        log('{0}: {1}', message, type)


class ReconnectingConnection(LoggingMixin, asyncore.dispatcher):
    """
    An asyncore connection that maintains a TCP connection to a particular
    host/port, reconnecting on connection loss.
    """

    reconnect_interval = 10.0
    _ipv6_supported = None  # Cache for IPv6 support detection

    @classmethod
    def _check_ipv6_support(cls):
        """Check if IPv6 is supported and routable on this system."""
        if cls._ipv6_supported is None:
            try:
                # Try to create and bind an IPv6 socket to verify IPv6 is actually available
                test_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                try:
                    # Try to bind to IPv6 loopback - this will fail if IPv6 isn't configured
                    test_socket.bind(('::1', 0))
                    cls._ipv6_supported = True
                    log('IPv6 support detected')
                finally:
                    test_socket.close()
            except (OSError, socket.error) as e:
                cls._ipv6_supported = False
                log('IPv6 not available, will use IPv4 only')
        return cls._ipv6_supported

    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.host = host
        self.port = port
        # check port as well, if port doesn't match, could be direct MLAT
        self.addrlist = []
        self.state = STATE_DISCONNECTED
        self.reconnect_at = None
        self.last_try = 0
        # Check IPv6 support on first initialization
        self._check_ipv6_support()

    def heartbeat(self, now):
        if self.reconnect_at is None or self.reconnect_at > now:
            return
        if self.state == STATE_READY:
            return
        self.reconnect_at = None
        self.reconnect()

    def close(self, manual_close=False):
        try:
            asyncore.dispatcher.close(self)
        except AttributeError:
            # blarg, try to eat asyncore bugs
            pass

        if self.state != STATE_DISCONNECTED:
            if not manual_close:
                log('Lost connection to {host}:{port}', host=self.host, port=self.port)
                log('This may indicate the remote service is unavailable or network connectivity issues')

            self.state = STATE_DISCONNECTED
            self.reset_connection()
            self.lost_connection()

        if not manual_close:
            self.schedule_reconnect()

    def disconnect(self, reason):
        if self.state != STATE_DISCONNECTED:
            log('Disconnecting from {host}:{port}: {reason}', host=self.host, port=self.port, reason=reason)
            self.close(True)

    def writable(self):
        return self.connecting

    def schedule_reconnect(self):
        if self.reconnect_at is None:
            mono = monotonic_time()

            if len(self.addrlist) > 0:
                # we still have more addresses to try
                # nb: asyncore breaks in odd ways if you try
                # to reconnect immediately at this point
                # (pending events for the old socket go to
                # the new socket) so do it in 0.5s time
                # so the caller can clean up the old
                # socket and discard the events.
                interval = 0.5
            else:

                interval = self.last_try + self.reconnect_interval - mono + 2 * random.random()

                if interval < 4:
                    interval = 2 + 2 * random.random()

            log('Reconnecting in {seconds:.1f} seconds'.format(seconds=interval))
            self.reconnect_at = mono + interval

    def refresh_address_list(self):
        self.address

    def reconnect(self):
        if self.state != STATE_DISCONNECTED:
            self.disconnect('About to reconnect')

        self.last_try = monotonic_time()

        while True:
            try:
                self.reset_connection()

                if len(self.addrlist) == 0:
                    # ran out of addresses to try, resolve it again
                    self.addrlist = socket.getaddrinfo(host=self.host,
                                                       port=self.port,
                                                       family=socket.AF_UNSPEC,
                                                       type=socket.SOCK_STREAM,
                                                       proto=0,
                                                       flags=0)

                    # Filter out IPv6 addresses if IPv6 is not supported
                    if not self._ipv6_supported:
                        self.addrlist = [addr for addr in self.addrlist if addr[0] == socket.AF_INET]
                    else:
                        # Prioritize IPv4 over IPv6 for better compatibility
                        self.addrlist.sort(key=lambda x: (x[0] != socket.AF_INET, x))

                # try the next available address
                a_family, a_type, a_proto, a_canonname, a_sockaddr = self.addrlist[0]
                del self.addrlist[0]

                self.create_socket(a_family, a_type)
                self.connect(a_sockaddr)
                # Connection attempt started successfully
                break

            except socket.error as e:
                # EADDRNOTAVAIL (99) = address family not available (e.g. no IPv6)
                # ENETUNREACH (101) = network unreachable (e.g. IPv6 not routed)
                # ECONNREFUSED (111) = connection refused (service not running)
                # Try the next address if available
                if e.errno in (99, 101) and len(self.addrlist) > 0:
                    log('Connection failed ({error}), trying next address', error=e.strerror)
                    continue

                # For other errors or if no more addresses, give up and schedule reconnect
                log('Connection to {host}:{port} failed: {ex!s}', host=self.host, port=self.port, ex=e)
                if e.errno == 111:  # ECONNREFUSED
                    log('Connection refused - check that the service at {host}:{port} is running',
                        host=self.host, port=self.port)
                elif e.errno == 113:  # EHOSTUNREACH
                    log('Host unreachable - check network connectivity and host address')
                elif e.errno == 110:  # ETIMEDOUT
                    log('Connection timeout - check firewall settings and network connectivity')
                self.close()
                break

    def handle_connect(self):
        self.state = STATE_CONNECTED
        self.addrlist = []  # connect was OK, re-resolve next time
        self.start_connection()

    def handle_read(self):
        pass

    def handle_write(self):
        pass

    def handle_close(self):
        self.close()

    def handle_error(self):
        t, v, tb = sys.exc_info()
        if isinstance(v, IOError):
            log('Connection to {host}:{port} lost: {ex!s}',
                host=self.host,
                port=self.port,
                ex=v)
        else:
            log_exc('Unexpected exception on connection to {host}:{port}',
                    host=self.host,
                    port=self.port)

        self.handle_close()

    def reset_connection(self):
        pass

    def start_connection(self):
        pass

    def lost_connection(self):
        pass
