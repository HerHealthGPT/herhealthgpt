"""Source clients, one module per source. Written in phase 4.

Every client returns normalised records and writes raw content to
raw/{source}/{YYYY-MM-DD}/ without ever overwriting a previous fetch. No module
in this package may make a network call without the operator confirming first,
and no test in this repo may hit the network.
"""
