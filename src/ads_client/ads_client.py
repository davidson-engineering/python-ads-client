#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Created By  : Matthew Davidson
# Created Date: 2023-01-23
# version ='1.0'
# ---------------------------------------------------------------------------
"""a_short_module_description"""
# ---------------------------------------------------------------------------

import asyncio
import sys
from typing import Union
from collections import deque
from pathlib import Path
import logging
from datetime import datetime, timezone

from ads_client import ADSConnection
from buffered import Buffer
from pyads import ADSError

logger = logging.getLogger(__name__)


def id_generator(prefix: str = "instance"):
    """Generator function to create unique IDs with a configurable prefix."""
    counter = 1
    while True:
        yield f"{prefix}-{counter}"
        counter += 1


class ADSClient:
    """ADSClient class to manage the connection to an ADS target device and read data from it."""

    client_id = id_generator(prefix="client")

    def __init__(
        self,
        name: str = None,
        ams_net_id=None,
        ip_address=None,
        ams_net_port=None,
        update_interval: int = 1,
        retry_attempts: int = 10,
        retain_connection: bool = False,
    ):
        self.name = name or next(self.client_id)
        self.target = ADSConnection(
            ams_net_id=ams_net_id,
            ip_address=ip_address,
            ams_net_port=ams_net_port,
            retain_connection=retain_connection,
        )
        self.update_interval = update_interval
        self.retry_attempts = retry_attempts

    async def do_work_periodically(self, *args, update_interval=None, **kwargs):
        update_interval = update_interval or self.update_interval
        while True:
            await self.do_work(*args, **kwargs)
            await asyncio.sleep(update_interval)

    async def do_work(self, *args, **kwargs):
        """This should be overridden by subclasses"""
        raise NotImplementedError("Subclasses should implement this method.")

    async def _perform_operation(self, operation):
        operation_successful = False
        retry_attempts = self.retry_attempts

        while not operation_successful and retry_attempts > 0:
            try:
                await operation()
                operation_successful = True
            except ADSError as e:
                retry_attempts -= 1
                logger.error(
                    f"Operation failed. Retrying... ({retry_attempts} remaining) {e}"
                )

        if not operation_successful:
            logger.error(
                f"Operation failed after {self.retry_attempts} attempts. Exiting."
            )
            sys.exit(1)


class ADSReaderClient(ADSClient):
    """ADSClient class to manage the connection to an ADS target device and read data from it."""

    client_id = id_generator(prefix="reader_client")

    def __init__(
        self,
        buffer: Union[list, deque],
        name: str = None,
        ams_net_id=None,
        ip_address=None,
        ams_net_port=None,
        data_names=None,
        update_interval: int = 1,
        retry_attempts: int = 10,
        retain_connection: bool = False,
        process_data_enabled: bool = False,
    ):
        super().__init__(
            name=name,
            ams_net_id=ams_net_id,
            ip_address=ip_address,
            ams_net_port=ams_net_port,
            update_interval=update_interval,
            retry_attempts=retry_attempts,
            retain_connection=retain_connection,
        )
        self.process_data_enabled = process_data_enabled
        self.buffer = buffer
        self.data_names = data_names

    def process_data(self, data):
        """
        Process data read from the target device.
        Define how to process the data in this method.
        """
        # Example: Convert data to InfluxDB line protocol format
        # processed_data = {
        #     "time": datetime.now(timezone.utc).timestamp(),
        #     "measurement": self.name,
        #     "tags": {"device": self.name},
        #     "fields": data,
        # }
        # return processed_data
        return None

    async def do_work(self, *args, **kwargs):
        async def read_operation():
            read_data = self.target.read_list_by_name(data_names=self.data_names)

            if read_data:
                if self.process_data_enabled:
                    read_data = self.process_data(read_data)
                if read_data is None and self.process_data_enabled:
                    logger.error(
                        f"Processing data failed. 'process_data_enabled' is {self.process_data_enabled} but 'process_data' function returning {read_data}. Check that 'process_data' is implemented correctly for subclass{self.__class__.__name__}."
                    )
                    return
                logger.info(f"Adding {len(read_data)} packets to queue")
                self.buffer.append(read_data)

        # Use the base class method to handle retries and errors
        await self._perform_operation(read_operation)


class ADSWriterClient(ADSClient):
    """ADSClient class to manage the connection to an ADS target device and write data to it."""

    client_id = id_generator(prefix="writer_client")

    def __init__(
        self,
        buffer: Union[list, deque, Buffer],
        name: str = None,
        ams_net_id=None,
        ip_address=None,
        ams_net_port=None,
        update_interval: int = 1,
        retry_attempts: int = 10,
        retain_connection: bool = False,
        write_batch_size: int = 0,
        verify_write_operations: bool = False,
    ):
        super().__init__(
            name=name,
            ams_net_id=ams_net_id,
            ip_address=ip_address,
            ams_net_port=ams_net_port,
            update_interval=update_interval,
            retry_attempts=retry_attempts,
            retain_connection=retain_connection,
        )
        self.buffer = buffer
        self.write_batch_size = write_batch_size
        self.verify_write_operations = verify_write_operations

    async def do_work(self, *args, **kwargs):
        async def write_operation():
            if self.buffer:
                if isinstance(self.buffer, Buffer):
                    if self.write_batch_size:
                        write_data = self.buffer.dump(self.write_batch_size)
                        self.target.write_list_by_name(
                            variables=write_data, verify=self.verify_write_operations
                        )
                    else:
                        write_data = self.buffer.get()
                else:
                    write_data = self.buffer.popleft()
                for data_name, value in write_data.items():
                    self.target.write_by_name(data_name=data_name, value=value)

        # Use the base class method to handle retries and errors
        await self._perform_operation(write_operation)
