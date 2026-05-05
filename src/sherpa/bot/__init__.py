"""GitHub posting integration. Spec pre-flight-bot.

Hard contract: this module MUST NOT call the GitHub Reviews API. Tests in
tests/test_no_approve.py grep this package's source for the forbidden surface
and run a transport-double assertion at runtime.
"""
