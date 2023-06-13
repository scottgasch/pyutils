#!/usr/bin/env python3

# © Copyright 2022, Scott Gasch

"""Wrapper around US Census address geocoder API described here:

* https://www2.census.gov/geo/pdfs/maps-data/data/Census_Geocoder_User_Guide.pdf
* https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.pdf

Also try::

    $ curl --form addressFile=@localfile.csv \\
           --form benchmark=2020 \\
           https://geocoding.geo.census.gov/geocoder/locations/addressbatch \\
           --output geocoderesult.csv
"""

import functools
import json
import logging
from typing import Any, Dict, List, Optional

import requests
from requests.utils import requote_uri

from pyutils import list_utils

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=256)
def geocode_address(address: str) -> Optional[Dict[str, Any]]:
    """Send a single address to the US Census geocoding API in order to
    lookup relevant data about it (including, if possible, its
    lat/long).  The response is a parsed JSON chunk of data with N
    addressMatches in the result section and the details of each match
    within it.

    Args:
        address: the full address to lookup in the form: "STREET
        ADDRESS, CITY, STATE, ZIPCODE".  These components may be
        omitted and the service will make educated guesses but
        the commas delimiting each component must be included.

    Returns:
        A parsed json dict with a bunch of information about the
            address contained within it.  Each 'addressMatch'
            in the JSON describes the details of a possible match.
            Returns None if there was an error or the address is
            not known.

    >>> json = geocode_address('4600 Silver Hill Rd,, 20233')
    >>> json['result']['addressMatches'][0]['matchedAddress']
    '4600 SILVER HILL RD, WASHINGTON, DC, 20233'

    >>> json['result']['addressMatches'][0]['coordinates']
    {'x': -76.9274328556918, 'y': 38.845989080537514}
    """
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    url += f"?address={address}"
    url += "&returntype=geographies&layers=all&benchmark=4&vintage=4&format=json"
    url = requote_uri(url)
    logger.debug("GET: %s", url)
    try:
        r = requests.get(url, timeout=10.0)
    except Exception as e:
        logger.exception(e)
        return None

    if not r.ok:
        logger.debug(r.text)
        logger.error("Unexpected response code %d, wanted 200.  Fail.", r.status_code)
        return None
    logger.debug("Response: %s", json.dumps(r.json(), indent=4, sort_keys=True))
    return r.json()


def batch_geocode_addresses(addresses: List[str]) -> Optional[List[str]]:
    """Send a list of addresses for batch geocoding to a web service
    operated by the US Census Bureau.

    Args:
        addresses: a list of addresses to geocode.  Each line of the
            input list should be a single address in the form: "STREET
            ADDRESS, CITY, STATE, ZIPCODE".  Individual address components
            may be omitted and the service will make educated guesses but
            the commas delimiters between address components may not be
            omitted.

    Returns:
        An array of the same size as the input array with one
        answer record per line.  Returns None on error.

    Note: this code will deal with requests >10k addresses by chunking
    them internally because the census website disallows requests >
    10k lines.

    >>> batch_geocode_addresses(
    ...     [
    ...         '4600 Silver Hill Rd, Washington, DC, 20233',
    ...         '935 Pennsylvania Avenue, NW, Washington, DC, 20535-0001',
    ...         '1600 Pennsylvania Avenue NW, Washington, DC, 20500',
    ...         '700 Pennsylvania Avenue NW, Washington, DC, 20408',
    ...     ]
    ... )
    ['"1"," 4600 Silver Hill Rd,  Washington,  DC,  20233","Match","Exact","4600 SILVER HILL RD, WASHINGTON, DC, 20233","-76.92743285599994,38.84598908100003","76355984","L","24","033","802405","2004"', '"2"," 935 Pennsylvania Avenue,  NW,  Washington,  DC","No_Match"', '"3"," 1600 Pennsylvania Avenue NW,  Washington,  DC,  20500","Match","Exact","1600 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20500","-77.03654072899997,38.89874352700008","76225813","L","11","001","980000","1034"', '"4"," 700 Pennsylvania Avenue NW,  Washington,  DC,  20408","Match","Exact","700 PENNSYLVANIA AVE NW, WASHINGTON, DC, 20408","-77.02304089899997,38.89361872300003","76226346","L","11","001","980000","1025"']
    """

    n = 1
    url = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
    payload = {"benchmark": "4", "vintage": "4"}
    out = []
    for chunk in list_utils.shard(addresses, 9999):
        raw_file = ""
        for address in chunk:
            raw_file += f"{n}, {address}\n"
            n += 1
        files = {"addressFile": ("input.csv", raw_file)}
        logger.debug("POST: %s", url)
        try:
            r = requests.post(url, files=files, data=payload, timeout=10.0)
        except Exception as e:
            logger.exception(e)
            return None

        if not r.ok:
            logger.debug(r.text)
            logger.error(
                "Unexpected response code %d, wanted 200.  Fail.", r.status_code
            )
            return None
        logger.debug("Response: %s", r.text)
        for line in r.text.split("\n"):
            line = line.strip()
            if line:
                out.append(line)
    return out


if __name__ == "__main__":
    import doctest

    doctest.testmod()
