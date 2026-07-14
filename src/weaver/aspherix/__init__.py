"""weaver.aspherix — deck-as-template Aspherix wrapper for Weaver.

The study owns a real ``.asx`` deck with ``{{name}}`` holes; this package is
render → stage assets → launch → observe, wired as model steps of a
``simulate`` model. It owns zero Aspherix vocabulary. Public surface:

    from weaver.aspherix import bind
    run_case, observe, observe_bytes = bind(__file__)
"""

from weaver.aspherix.errors import AsxError
from weaver.aspherix.steps import bind

__all__ = ["AsxError", "bind"]
