Developer Information
======================

This section is specifically for people who are wanting to help develop
or are looking to get a better understanding of how the plugin works.

The layout of the plugin and its internal modules is as follows: [#f1]_.

.. toctree::
   :titlesonly:

   {% for page in pages|selectattr("is_top_level_object") %}
   {{ page.include_path }}
   {% endfor %}

Contributing
-------------

The following python tools are used during this plugin's development:

- `Black <https://black.readthedocs.io/en/stable/>`_
- `mypy <https://mypy-lang.org/>`_
- `Pylint <https://docs.pylint.org/>`_
- `Sphinx <https://www.sphinx-doc.org/en/master/>`_

When contributing code, it is not necessary to install and run all these tools,
but is requested that you follow some of the development patterns already 
established in the code to roughly follow the guidelines these tools would
otherwise provide.

.. [#f1] Created with `sphinx-autoapi <https://github.com/readthedocs/sphinx-autoapi>`_
