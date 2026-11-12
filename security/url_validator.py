#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


class UrlValidator:

    ALLOWED_SCHEMES = {
        "http",
        "https",
    }

    def validate(
        self,
        url: str,
    ) -> None:

        parsed = urlparse(url)

        #
        # Scheme
        #

        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
            raise UnsafeUrlError(
                f"URL scheme is not allowed: "
                f"{parsed.scheme}"
            )

        #
        # Hostname must exist.
        #

        hostname = parsed.hostname

        if not hostname:
            raise UnsafeUrlError(
                "URL does not contain a hostname."
            )

        #
        # Explicitly reject localhost names.
        #

        hostname_lower = hostname.lower()

        if (
            hostname_lower == "localhost"
            or hostname_lower.endswith(".localhost")
        ):
            raise UnsafeUrlError(
                "Localhost URLs are not allowed."
            )

        #
        # Resolve the hostname.
        #

        try:

            address_info = socket.getaddrinfo(
                hostname,
                parsed.port or (
                    443
                    if parsed.scheme == "https"
                    else 80
                ),
                type=socket.SOCK_STREAM,
            )

        except socket.gaierror as ex:

            raise UnsafeUrlError(
                f"Unable to resolve hostname: "
                f"{hostname}"
            ) from ex

        #
        # Every returned address must be safe.
        #

        for entry in address_info:

            address = entry[4][0]

            ip = ipaddress.ip_address(address)

            if not ip.is_global:

                raise UnsafeUrlError(
                    f"URL resolves to a "
                    f"non-public address: {ip}"
                )