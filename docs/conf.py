# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import json

topdir = os.path.split(os.path.split(__file__)[0])[0]
sys.path.insert(0, topdir)

with open(os.path.join(topdir, "manifest.json"), 'r') as manifest:
    VERSION_INFO = json.load(manifest)["version"]

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'MultiGP Toolkit'
copyright = '2024, Bryce Gruber'
author = 'Bryce Gruber'
version = VERSION_INFO.split("-")[0]
release = VERSION_INFO

rst_prolog = f"""
.. |project_version| replace:: {release}
"""

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_material'
html_static_path = ['_static']

html_theme_options = {
    'nav_title': 'MultiGP Toolkit',

    'color_primary': 'orange',
    'color_accent': 'grey',

    'repo_url': 'https://github.com/i-am-grub/MultiGP_Toolkit',
    'repo_name': 'MultiGP Toolkit',
    'repo_type': 'github',

    'globaltoc_depth': 2,
    'globaltoc_collapse': True,
}

html_sidebars = {
    "**": ["logo-text.html", "globaltoc.html", "searchbox.html"]
}

extensions = ['sphinx.ext.autosectionlabel']