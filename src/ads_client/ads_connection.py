#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Created By  : Matthew Davidson
# Created Date: 2024-09-08
# version ='1.0'
# ---------------------------------------------------------------------------
"""ADSConnection class to manage the connection to an ADS target device"""
# ---------------------------------------------------------------------------


from typing import Any, Union
import pyads
import json
import logging
import re

from prometheus_client import Counter

from ads_client.constants import ERROR_STRUCTURE

logger = logging.getLogger(__name__)


class AMSNetIDFormatError(Exception):
    """Custom exception for invalid AMS Net ID format."""

    def __init__(self, message: str):
        # Initialize the base Exception with the custom message
        super().__init__(message)
        self.message = message


def verify_ams_net_id(ams_net_id: str) -> bool:
    """Verify if the ams_net_id follows the format 'x.x.x.x.x.x' where x is an integer between 0 and 255."""

    # Regular expression to match 6 groups of integers (0-255) separated by dots
    pattern = r"^(\d{1,3}\.){5}\d{1,3}$"

    # First check if the format is correct with 6 parts separated by '.'
    if not re.match(pattern, ams_net_id):
        raise AMSNetIDFormatError(
            "Invalid ams_net_id format, ensure that format is 6 parts separated by periods."
        )

    # Split the ams_net_id by dots and check each part is within the range 0-255
    parts = ams_net_id.split(".")
    if not all(0 <= int(part) <= 255 for part in parts):
        raise AMSNetIDFormatError(
            "Invalid ams_net_id format, ensure that numerical values are integers within range 0-255"
        )


def id_generator(prefix: str = "instance"):
    """Generator function to create unique IDs with a configurable prefix."""
    counter = 1
    while True:
        yield f"{prefix}-{counter}"
        counter += 1


class ADSConnection(pyads.Connection):
    """Class to manage an ADS client connection"""

    connection_id = id_generator("ads_connection")

    # Class-level metrics to be shared across instances
    open_events = Counter(
        name="ads_client_connection_open_events",
        documentation="Number of times the connection was opened",
        labelnames=["ams_net_id"],
    )
    close_events = Counter(
        name="ads_client_connection_close_events",
        documentation="Number of times the connection was closed",
        labelnames=["ams_net_id"],
    )
    write_events = Counter(
        name="ads_client_connection_write_events",
        documentation="Number of times a variable was written",
        labelnames=["ams_net_id"],
    )
    read_events = Counter(
        name="ads_client_connection_read_events",
        documentation="Number of times a variable was read",
        labelnames=["ams_net_id"],
    )

    def __init__(
        self,
        ams_net_id: str,
        ip_address: str = None,
        ams_net_port: str = pyads.PORT_TC3PLC1,
        name: str = None,
        verify_is_open: bool = False,
        retain_connection: bool = False,
    ):
        if name:
            self.name = name
        else:
            self.name = next(ADSConnection.connection_id)

        # Verify adsAddress
        verify_ams_net_id(ams_net_id)

        connection_name = f"'{self.name}' " if self.name else ""
        logging.info(
            f"Creating ADS connection {connection_name}to {ams_net_id}:{ams_net_port}"
        )

        self.open_events_counter = 0
        self.close_events_counter = 0

        # Initialize the parent class (pyads.Connection)
        super().__init__(
            ams_net_id=ams_net_id, ams_net_port=ams_net_port, ip_address=ip_address
        )

        # Ensure connection is open if requested
        if verify_is_open:
            self._ensure_open()

        self.retain_connection = retain_connection
        if retain_connection:
            logger.warning(
                f"'retain_connection' is set to True. Connection {self.name} will be remain open until explicitly closed."
            )

        self._retain_connection_warning = False

    def _ensure_open(self):
        """Ensure the connection is open using a context manager."""
        if not self.is_open:
            with self:
                assert self.is_open

    def write_by_name(
        self,
        data_name: str,
        value: Any,
        plc_datatype=None,
        handle=None,
        verify: bool = False,
        cache_symbol_info: bool = True,
    ) -> None:
        """Write a value to a PLC variable."""
        with self:  # Using context manager to ensure connection is open
            super().write_by_name(
                data_name, value, plc_datatype, handle, cache_symbol_info
            )
            if verify:
                assert super().read_by_name(data_name) == value

    def read_by_name(
        self,
        data_name: str,
        plc_datatype=None,
        handle: int | None = None,
        check_length: bool = True,
        cache_symbol_info: bool = True,
    ) -> Any:
        """Read a PLC variable by name."""
        with self:
            try:
                return super().read_by_name(
                    data_name,
                    plc_datatype=plc_datatype,
                    handle=handle,
                    check_length=check_length,
                    cache_symbol_info=cache_symbol_info,
                )
            except TypeError:
                logger.warning(
                    f"Variable {data_name} does not have a type declared in PLC. Ignoring read operation."
                )

    def write_array_by_name(
        self, data_name: str, value: Any, plc_datatype=None, verify: bool = False
    ) -> None:
        """Write an array to a PLC variable."""
        if plc_datatype is None:
            logger.warning("No PLC datatype provided, defaulting to LREAL")
            plc_datatype = pyads.PLCTYPE_LREAL
        with self:
            super().write_by_name(
                data_name, value, plc_datatype=plc_datatype * len(value)
            )
            if verify:
                assert (
                    super().read_by_name(
                        data_name,
                        plc_datatype=(
                            plc_datatype * len(value) if plc_datatype else None
                        ),
                    )
                    == value
                )

    def write_list_array_by_name(
        self, variables: dict, plc_datatype=None, verify: bool = False
    ) -> None:
        """Write multiple arrays to PLC variables."""
        if plc_datatype is None:
            logger.warning("No PLC datatype provided, defaulting to LREAL")
            plc_datatype = pyads.PLCTYPE_LREAL
        with self:
            for data_name, value in variables.items():
                self.write_array_by_name(
                    data_name, value, plc_datatype=plc_datatype, verify=verify
                )

    def write_list_by_name(self, variables: dict, verify: bool = False) -> None:
        """Write multiple values to PLC variables."""
        with self:
            super().write_list_by_name(variables)
            if verify:
                assert super().read_list_by_name(variables) == variables

    def read_by_name(self, data_name: str, plc_datatype=None) -> Any:
        """Read a PLC variable by name."""
        with self:
            try:
                return super().read_by_name(data_name, plc_datatype=plc_datatype)
            except TypeError:
                logger.warning(
                    f"Variable {data_name} does not have a type declared in PLC. Ignoring read operation."
                )

    def read_array_by_name(self, data_name: str, plc_datatype=None, array_size=1):
        """Read an array from a PLC variable."""
        with self:
            return super().read_by_name(
                data_name,
                plc_datatype=plc_datatype * array_size if plc_datatype else None,
            )

    def read_list_array_by_name(
        self, data_names: Union[str, list, tuple, set], plc_datatype=None, array_size=1
    ):
        """Read multiple PLC variables by their names."""
        with self:
            return {
                data_name: super().read_by_name(
                    data_names,
                    plc_datatype=plc_datatype * array_size if plc_datatype else None,
                    check_length=False,
                )
                for data_name in data_names
            }

    def read_list_by_name(self, data_names: Union[str, list, tuple, set]):
        """Read multiple PLC variables by their names."""
        with self:
            return super().read_list_by_name(data_names)

    def read_errors(self, data_name: str, number_of_errors=1):
        """Read error messages."""
        return json.dumps(
            self.read_structure_by_name(
                data_name, structure_def=ERROR_STRUCTURE, array_size=number_of_errors
            )
        )

    def read_device_info(self):
        """Read device information."""
        with self:
            return super().read_device_info()

    def get_all_symbols(self):
        """Read all symbols from the client."""
        with self:
            return super().get_all_symbols()

    def set_timeout(self, timeout: int) -> None:
        """Set the timeout for the connection."""
        super().set_timeout(timeout)

    def open(self):
        if self.is_open:
            return
        logger.debug(f"Opening connection to {self.connection_address}")
        super().open()
        logger.debug(f"Connection to {self.connection_address} opened")
        self.open_events.labels(self.ams_net_id).inc()
        self.open_events_counter += 1

    def close(self):
        if self.retain_connection:
            if not self._retain_connection_warning:
                logger.warning(
                    f"'ADSConnection.close()' was called, but 'ADSConnection.retain_connection' is set to True. Connection {self.name} will be remain open until explicitly closed. This warning will not be shown again."
                )
                self._retain_connection_warning = True
            return
        self._close()

    def _close(self):
        if not self.is_open:
            return
        logger.debug(f"Closing connection to {self.connection_address}")
        super().close()
        logger.info(f"Connection to {self.connection_address} closed")
        self.close_events.labels(self.ams_net_id).inc()
        self.close_events_counter += 1

    def ensure_closed(self):
        """Force close the connection."""
        self._close()

    def __del__(self):
        self._close()

    @property
    def connection_address(self):
        """Return the device address."""
        return f"{self.ip_address}:{self.ams_net_port}"

    def __repr__(self):
        return f"{self.__class__.__name__}(ams_net_id={self.ams_net_id}, ams_net_port={self.ams_net_port}, name={self.name})"
