# -*- coding: utf-8 -*-
"""FGQEP01 Browse Enhancer plugin entry."""


def classFactory(iface):  # pylint: disable=invalid-name
    from .plugin import FGQEP01BrowseEnhancerPlugin
    return FGQEP01BrowseEnhancerPlugin(iface)
