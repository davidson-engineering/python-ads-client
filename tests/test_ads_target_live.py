import pytest
import logging

from ads_client import ADSConnection
from utils import (
    _testfunc_read_by_name,
    _testfunc_write_by_name,
    _testfunc_get_all_symbols,
    _testfunc_get_all_symbol_values,
    _testfunc_read_device_info,
    add_route,
)

ADS_TARGET_NETID_LIVE = "5.109.60.19.1.1"
ADS_TARGET_PORT_LIVE = 851
ADS_TARGET_IP_ADDRESS_LIVE = "10.10.32.53"

logger = logging.getLogger("testing")


@pytest.fixture(scope="session")
def ads_target_live():
    """Fixture to create an instance of the ADS client class."""
    target = ADSConnection(
        ams_net_id=ADS_TARGET_NETID_LIVE,
        ip_address=ADS_TARGET_IP_ADDRESS_LIVE,
        ams_net_port=ADS_TARGET_PORT_LIVE,
    )

    with target:
        add_route(
            ams_net_id=ADS_TARGET_NETID_LIVE, ip_address=ADS_TARGET_IP_ADDRESS_LIVE
        )
        yield target


@pytest.fixture(scope="session")
def ads_target_live_retained():
    """Fixture to create an instance of the ADS client class with retained connection."""
    target = ADSConnection(
        ams_net_id=ADS_TARGET_NETID_LIVE,
        ip_address=ADS_TARGET_IP_ADDRESS_LIVE,
        ams_net_port=ADS_TARGET_PORT_LIVE,
        retain_connection=True,
    )

    with target:
        add_route(
            ams_net_id=ADS_TARGET_NETID_LIVE, ip_address=ADS_TARGET_IP_ADDRESS_LIVE
        )
        yield target
        target.ensure_closed()


# Test Read / Write Operations
# ################################################################################################


def test_read_by_name(ads_target_live):
    """Test single reading by name using the ADS client class."""
    _testfunc_read_by_name(ads_target_live, {"MAIN.nVar1": 1})


def test_write_by_name(ads_target_live):
    """Test single writing by name using the ADS client class."""
    _testfunc_write_by_name(ads_target_live, {"MAIN.nVar1": 1})


def test_get_all_symbols(ads_target_live):
    """Test getting all symbols using the ADS client class."""
    _testfunc_get_all_symbols(ads_target_live)


def test_get_all_symbol_values(ads_target_live):
    """Test getting all symbol values using the ADS client class."""
    _testfunc_get_all_symbol_values(ads_target_live)


def test_read_device_info(ads_target_live):
    """Test reading device info using the ADS client class."""
    _testfunc_read_device_info(ads_target_live)


def test_read_by_name_retained(ads_target_live, ads_target_live_retained):
    """Test single reading by name using the ADS client class with retained connection."""
    _testfunc_read_by_name(ads_target_live_retained, {"MAIN.nVar1": 1})
    _testfunc_read_by_name(ads_target_live, {"MAIN.nVar1": 1})
    assert ads_target_live_retained.is_open == True
    assert ads_target_live.is_open == False


def test_write_by_name_retained(ads_target_live_retained):
    """Test single writing by name using the ADS client class with retained connection."""
    _testfunc_write_by_name(ads_target_live_retained, {"MAIN.nVar1": 1})
    assert ads_target_live_retained.is_open == True


# Performance Testing
# ################################################################################################


# @pytest.mark.parametrize("variable_type", {"integers", "reals", "bools"})
# @pytest.mark.parametrize("dataset", {"single_small", "single_large"})
# def test_read_by_name_performance(benchmark, ads_target_live, variable_type, dataset):
#     """Benchmark single reading by name using the ADS client class."""
#     variables = TEST_DATASET[dataset][variable_type]
#     benchmark(_testfunc_read_by_name, ads_target_live, variables)
