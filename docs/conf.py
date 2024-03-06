"""Sphinx configuration."""

project = "Embody File"
author = "Aidee Health"
copyright = "2022, Aidee Health"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
