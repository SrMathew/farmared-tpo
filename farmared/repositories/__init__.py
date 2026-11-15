"""Interfaces the write services (q13 to q15) use to reach the data.

A service depends on these interfaces, never on a database driver, so its rules can be
tested with in-memory implementations and without any engine running.
"""
