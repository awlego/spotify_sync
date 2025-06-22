#!/usr/bin/env python3
"""
Intentional failing tests to verify error counting
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestIntentionalFailures(unittest.TestCase):
    """Tests that should fail to verify error counting"""
    
    def test_this_should_fail(self):
        """This test should fail"""
        self.assertTrue(False, "This is an intentional failure")
    
    def test_this_should_error(self):
        """This test should error"""
        raise Exception("This is an intentional error")


if __name__ == '__main__':
    unittest.main()