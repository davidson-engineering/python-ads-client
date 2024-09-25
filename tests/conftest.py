#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Created By  : Matthew Davidson
# Created Date: 2024-09-08
# version ='1.0'
# ---------------------------------------------------------------------------
"""Test fixtures for the ADS client class."""
# ---------------------------------------------------------------------------

import logging
from logging.config import dictConfig
import time
import pytest
import pyads

from ads_client import ADSConnection
from config_loader import load_configs
from utils import add_route

try:
    import pyads.testserver
except FileNotFoundError as e:
    logging.error(
        f"{e}. Check that TwinCAT software is installed and configured properly"
    )
    raise e

logger = logging.getLogger("testing")

# Configure logging using the specified logging configuration
dictConfig(load_configs("config/logging.yaml"))

# Test server configuration
PYADS_TESTSERVER_ADS_ADDRESS = "127.0.0.1.1.1"
PYADS_TESTSERVER_IP_ADDRESS = "127.0.0.1"
PYADS_TESTSERVER_ADS_PORT = 48898
PYADS_TESTSERVER_TIMEOUT_MS = 1000

add_route(
    ams_net_id=PYADS_TESTSERVER_ADS_ADDRESS,
    ip_address=PYADS_TESTSERVER_IP_ADDRESS,
)


def generate_dataset(dimensions: int | tuple = 1):
    """
    Generate a dataset with integers and real values.

    If dim2 is None, it generates single values.
    If dim2 is provided, it generates arrays with the second dimension size.
    """
    if isinstance(dimensions, int):
        dimensions = (dimensions, None)
    dim1 = dimensions[0]
    dim2 = dimensions[1] if len(dimensions) > 1 else None

    # Generate names
    names = {
        "integers": [f"integer{'_array' if dim2 else ''}{n}" for n in range(dim1)],
        "reals": [f"real{'_array' if dim2 else ''}{n}" for n in range(dim1)],
        "bools": [f"bool{'_array' if dim2 else ''}{n}" for n in range(dim1)],
    }

    # Generate values based on whether it's a regular or array dataset
    if dim2:
        values = {
            "integers": [[n * i for n in range(dim1)] for i in range(dim2)],
            "reals": [
                [round(n * i * 1.1, 2) for n in range(dim1)] for i in range(dim2)
            ],
            "bools": [[n % 2 == 0 for n in range(dim1)] for i in range(dim2)],
        }
    else:
        values = {
            "integers": [n for n in range(dim1)],
            "reals": [round(n * 1.1, 2) for n in range(dim1)],
            "bools": [n % 2 == 0 for n in range(dim1)],
        }

    # Combine names and values
    return {
        key: {name: value for name, value in zip(names[key], values[key])}
        for key in names
    }


def get_variable_kwargs(variable_type: str, initial_value: bytes = bytes(8)):
    """Function to get the keyword arguments for creating a PLCVariable."""
    if variable_type == "integers":
        return dict(
            value=initial_value,
            ads_type=pyads.constants.ADST_INT16,
            symbol_type="LINT",
        )
    elif variable_type == "reals":
        return dict(
            value=initial_value,
            ads_type=pyads.constants.ADST_REAL64,
            symbol_type="LREAL",
        )
    elif variable_type == "bools":
        return dict(
            value=False,
            ads_type=pyads.constants.ADST_BIT,
            symbol_type="BOOL",
        )
    else:
        raise ValueError(f"Unknown variable type: {variable_type}")


def get_total_length(variables):
    """Function to get the total length of all variables in a dataset."""
    if isinstance(variables, list):
        return sum(get_total_length(variable) for variable in variables)
    return sum(len(variables[key]) for key in variables)


TEST_DATASET = {}
TEST_DATASET["single_small"] = generate_dataset(1)
TEST_DATASET["single_large"] = generate_dataset(10)
# TEST_DATASET["array_small"] = generate_dataset((10, 2))
# TEST_DATASET["array_large"] = generate_dataset((2, 20))


# Test fixtures
@pytest.fixture(scope="function")
def testserver_target():
    """Fixture to create an instance of the ADS client class."""
    target = ADSConnection(
        ams_net_id=PYADS_TESTSERVER_ADS_ADDRESS, ams_net_port=PYADS_TESTSERVER_ADS_PORT
    )
    # target.set_timeout(PYADS_TESTSERVER_TIMEOUT_MS)
    with target:

        yield target


def add_variables(handler, variables):
    for var_type, variable_list in variables.items():
        for var_name in variable_list:
            try:
                array_size = len(variable_list[var_name])
            except TypeError:
                # Create a single variable
                handler.add_variable(
                    pyads.testserver.PLCVariable(
                        var_name, **get_variable_kwargs(var_type)
                    )
                )
                continue
            else:
                # Create an array variable
                kwargs = get_variable_kwargs(var_type)
                handler.add_variable(
                    pyads.testserver.PLCVariable(
                        var_name,
                        value=bytes(8 * array_size),
                        # value=kwargs["value"],
                        ads_type=kwargs["ads_type"] * array_size,
                        symbol_type=kwargs["symbol_type"],
                    )
                )


def init_testserver_advanced(variables):
    handler = pyads.testserver.AdvancedHandler()
    if isinstance(variables, list):
        for vars in variables:
            add_variables(handler, vars)
    else:
        add_variables(handler, variables)
    testserver = pyads.testserver.AdsTestServer(handler)
    time.sleep(1)

    return testserver


@pytest.fixture(scope="session")
def testserver_advanced():
    datasets = [
        TEST_DATASET["single_small"],
        TEST_DATASET["single_large"],
        # TEST_DATASET["array_small"],
        # TEST_DATASET["array_large"],
    ]
    with init_testserver_advanced(datasets) as testserver:
        testserver.total_variables = get_total_length(datasets)
        yield testserver
