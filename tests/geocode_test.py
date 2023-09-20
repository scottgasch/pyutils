#!/usr/bin/env python3

# © Copyright 2022-2023, Scott Gasch

"""Tests for geocode.py"""

import logging
import unittest
from unittest.mock import Mock, patch

from pyutils import bootstrap, geocode, unittest_utils

logger = logging.getLogger(__name__)


class TestGeocoder(unittest.TestCase):
    def test_geocode_makes_expected_network_read(self) -> None:
        with patch('requests.get') as mock_request:
            mock_request.return_value = Mock(
                status_code=200, content='', json=lambda: ""
            )
            geocode.geocode_address('1234 Main Street\nBellevue, WA 98005')
            mock_request.assert_called_with(
                "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=1234%20Main%20Street%0ABellevue,%20WA%2098005&returntype=geographies&layers=all&benchmark=4&vintage=4&format=json",
                timeout=10.0,
            )


if __name__ == '__main__':
    bootstrap.initialize(unittest.main)()
