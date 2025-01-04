# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import json

topdir = os.path.split(os.path.split(__file__)[0])[0]
sys.path.insert(0, topdir)

with open(os.path.join(topdir, "multigp_toolkit/manifest.json"), "r") as manifest:
    VERSION_INFO = json.load(manifest)["version"]

with open(os.path.join(topdir, "versions.json"), "r") as approved_vers:
    APPROVED_VERSIONS = json.load(approved_vers)

rh_versions = APPROVED_VERSIONS["RotorHazard"]["versions"]
tk_versions = APPROVED_VERSIONS["MultiGP Toolkit"]["versions"]

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "MultiGP Toolkit"
copyright = "2024-2025, Bryce Gruber"
author = "Bryce Gruber"
version = VERSION_INFO.split("-")[0]
release = f"{VERSION_INFO}"

rst_prolog = f"""
.. |project_version| replace:: {release}
.. |approved_rh_versions| replace:: {", ".join(rh_versions)}
.. |approved_tk_versions| replace:: {", ".join(tk_versions)}
"""

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx_substitution_extensions",
    "sphinx_copybutton",
    "autoapi.extension",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_static_path = ["_static"]

html_theme_options = {
    "repository_url": "https://github.com/i-am-grub/MultiGP_Toolkit",
    "use_repository_button": True,
}

html_title = "MultiGP Toolkit"

# -- Options for AutoAPI -------------------------------------------------
# https://sphinx-autoapi.readthedocs.io/en/latest/tutorials.html

autoapi_template_dir = "_templates/autoapi"

autoapi_dirs = ["../multigp_toolkit"]

autoapi_options = [
    "members",
    "undoc-members",
    "private-members",
    "show-inheritance",
    "show-module-summary",
]

autodoc_typehints = "description"
