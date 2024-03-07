MultiGP Toolkit plugin for RotorHazard
===========================================

.. image:: rotorhazard-logo.svg
   :width: 800
   :alt: RotorHazard Logo
   :align: center

.. image:: multigp-logo.png
   :width: 800
   :alt: MultiGP Logo
   :align: center

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   usage/install/index
   usage/fpvscores/index
   usage/setup/index
   usage/importing/index
   usage/zippyq/index
   usage/running/index
   usage/pushing/index

.. warning::

   Please be aware that this plugin is not approved for MultiGP Global Qualifers

This is a plugin developed with cooperation with MultiGP for the RotorHazard timing system. It gives RotorHazard the ability interface with MultiGP's RaceSync system for event management.

This plugin comes packaged with a mini version of `FPVScores plugin <https://github.com/FPVScores/FPVScores>`_ allowing you to push your event results without the need to install the full version.

General Requirements
---------------------------
- RotorHazard v4.1+ is required to run this plugin
   - Stricter RotorHazard version requirements are enforced for running Global Qualifers
- You will need your MultiGP Chapter's API key
- An internet connection when pushing or pulling data from MultiGP

.. note::

   An internet connection is **not** required for running the event, unless ZippyQ is being used