# tests/runner.py
import unittest

# import your test modules
import test.test_rest as rest

# initialize the test suite
loader = unittest.TestLoader()
suite = unittest.TestSuite()

# add tests to the test suite
suite.addTests(loader.loadTestsFromModule(rest))

# initialize a runner, pass it your suite and run it
runner = unittest.TextTestRunner(verbosity=3)

if __name__ == '__main__':
    result = runner.run(suite)
