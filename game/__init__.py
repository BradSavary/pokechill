"""
PokéChill game engine, in pure Python.

This package must never import Django: it only computes game rules from
plain values. The Django apps load the state from the database, call these
functions and save the result. Keeping the rules framework-free makes them
fast to test and easy to reason about.
"""
