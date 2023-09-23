#!/usr/bin/env python3

# © Copyright 2021-2023, Scott Gasch

"""zookeeper unittest."""

import datetime
import logging
import time
import unittest

from pyutils import unittest_utils, zookeeper

logger = logging.getLogger(__name__)


class TestZookeeper(unittest.TestCase):
    @zookeeper.obtain_lease(
        also_pass_lease=True, duration=datetime.timedelta(minutes=1)
    )
    def test_release_lease(self, lease: zookeeper.RenewableReleasableLease):
        self.assertTrue(lease)
        self.assertTrue(lease.release())
        self.assertFalse(lease)
        self.assertFalse(lease.release())
        self.assertFalse(lease)

    @zookeeper.obtain_lease(
        also_pass_lease=True, duration=datetime.timedelta(minutes=1)
    )
    def test_renew_lease(self, lease: zookeeper.RenewableReleasableLease):
        self.assertTrue(lease)
        self.assertTrue(lease.try_renew(datetime.timedelta(minutes=2)))
        self.assertTrue(lease)
        self.assertTrue(lease.release())

    @zookeeper.obtain_lease(
        also_pass_lease=True,
        duration=datetime.timedelta(minutes=1),
    )
    def test_cant_renew_lease_after_released(
        self, lease: zookeeper.RenewableReleasableLease
    ):
        self.assertTrue(lease)
        self.assertTrue(lease.release())
        self.assertFalse(lease)
        self.assertFalse(lease.try_renew(datetime.timedelta(minutes=2)))

    @zookeeper.obtain_lease(
        also_pass_lease=True, duration=datetime.timedelta(seconds=5)
    )
    def test_lease_expiration(self, lease: zookeeper.RenewableReleasableLease):
        self.assertTrue(lease)
        time.sleep(7)
        self.assertFalse(lease)

    def test_leases_are_exclusive(self):
        @zookeeper.obtain_lease(
            contender_id='second',
            duration=datetime.timedelta(seconds=10),
        )
        def i_will_fail_to_get_the_lease():
            logger.debug("I seem to have gotten the lease, wtf?!?!")
            self.fail("I should not have gotten the lease?!")

        @zookeeper.obtain_lease(
            contender_id='first',
            duration=datetime.timedelta(seconds=10),
        )
        def i_will_hold_the_lease():
            logger.debug("I have the lease.")
            time.sleep(1)
            self.assertFalse(i_will_fail_to_get_the_lease())

        i_will_hold_the_lease()


if __name__ == '__main__':
    unittest.main()
