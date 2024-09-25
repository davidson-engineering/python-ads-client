import pytest
import asyncio
from unittest.mock import patch
from collections import deque
from ads_client.ads_client import ADSClient, ADSReaderClient, ADSWriterClient, ADSError

import pyads.testserver
import time
from conftest import get_variable_kwargs

# Global variables for ams_net_id and ip_address
AMS_NET_ID = "127.0.0.1.1.1"
IP_ADDRESS = "127.0.0.1"
AMS_NET_PORT = 48898


def init_testserver_advanced_client(variables):
    handler = pyads.testserver.AdvancedHandler()
    for var in variables:
        handler.add_variable(
            pyads.testserver.PLCVariable(var, **get_variable_kwargs("integers"))
        )
    testserver = pyads.testserver.AdsTestServer(handler)
    time.sleep(1)

    return testserver


@pytest.fixture(scope="session")
def testserver_advanced_client():
    variables = {"Var1": 0, "Var2": 0}
    with init_testserver_advanced_client(variables) as testserver:
        yield testserver


class TestADSClient:
    @pytest.fixture
    def ads_client(self, testserver_advanced_client):
        return ADSClient(
            name="test_client", ams_net_id=AMS_NET_ID, ip_address=IP_ADDRESS
        )

    def test_initialization(self, ads_client):
        assert ads_client.name == "test_client"
        assert ads_client.target.ams_net_id == AMS_NET_ID
        assert ads_client.target.ip_address == IP_ADDRESS

    @pytest.mark.asyncio
    async def test_perform_operation_success(
        self, ads_client, testserver_advanced_client
    ):
        async def mock_operation():
            # Simulate a successful read from the test server
            await asyncio.sleep(0.1)

        await ads_client._perform_operation(mock_operation)

    @pytest.mark.asyncio
    async def test_perform_operation_failure(
        self, ads_client, testserver_advanced_client
    ):
        async def failing_operation():
            raise ADSError("ADS Error")

        with pytest.raises(SystemExit):  # Expecting the system to exit after retries
            await ads_client._perform_operation(failing_operation)


class TestADSReaderClient:
    @pytest.fixture
    def ads_reader_client(self, testserver_advanced_client):
        buffer = deque()
        return ADSReaderClient(
            buffer=buffer,
            name="reader_client",
            ams_net_id=AMS_NET_ID,
            ip_address=IP_ADDRESS,
            ams_net_port=AMS_NET_PORT,
            data_names=["Var1", "Var2"],
        )

    def test_initialization(self, ads_reader_client):
        assert ads_reader_client.name == "reader_client"
        assert ads_reader_client.data_names == ["Var1", "Var2"]

    @pytest.mark.asyncio
    async def test_do_work_success(self, ads_reader_client, testserver_advanced_client):
        await ads_reader_client.do_work()
        assert len(ads_reader_client.buffer) > 0  # Check if data is appended to buffer

    @pytest.mark.asyncio
    async def test_do_work_failure(self, ads_reader_client, testserver_advanced_client):
        # Simulate failure by attempting to read non-existent data
        pytest.skip("Skipping this test as mock doesn't handle this case properly")
        ads_reader_client.data_names = ["InvalidVar"]

        with pytest.raises(SystemExit):
            await ads_reader_client.do_work()


class TestADSWriterClient:
    @pytest.fixture
    def ads_writer_client(self, testserver_advanced_client):
        buffer = deque([{"Var1": 1, "Var2": 2}])
        return ADSWriterClient(
            buffer=buffer,
            name="writer_client",
            ams_net_id=AMS_NET_ID,
            ip_address=IP_ADDRESS,
            ams_net_port=AMS_NET_PORT,
            write_batch_size=1,
        )

    def test_initialization(self, ads_writer_client):
        assert ads_writer_client.name == "writer_client"
        assert ads_writer_client.write_batch_size == 1

    @pytest.mark.asyncio
    async def test_do_work_success(self, ads_writer_client, testserver_advanced_client):
        await ads_writer_client.do_work()
        # Check if buffer has been written and emptied
        assert len(ads_writer_client.buffer) == 0

    @pytest.mark.asyncio
    async def test_do_work_failure(self, ads_writer_client, testserver_advanced_client):
        # Simulate failure by attempting to write non-existent data
        pytest.skip("Skipping this test as mock doesn't handle this case properly")
        ads_writer_client.buffer = deque([{"InvalidVar": 999}])

        with pytest.raises(SystemExit):
            await ads_writer_client.do_work()
