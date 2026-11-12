"""bellhop-ui package.

Intentionally does not import the app, state, or pages: event handlers register
into whichever RegistrationContext (a contextvar) is active at first import, and
bellhop_ui.server defers that import to the serving thread. Page registration
happens in bellhop_ui.bellhop_ui (the Reflex app module) instead.
"""
