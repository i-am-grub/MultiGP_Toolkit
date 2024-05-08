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



This is a plugin developed with cooperation from MultiGP for the `RotorHazard <https://github.com/RotorHazard/RotorHazard>`_ timing system. It gives RotorHazard the ability interface with MultiGP's RaceSync system for event management.

This plugin comes packaged with a lite version of `FPVScores plugin <https://github.com/FPVScores/FPVScores>`_ allowing you to push your event results without the need to install the full version.

Requirements
---------------------------

General Requirements
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- You will need your MultiGP Chapter's API key
- An internet connection when pushing data to or pulling data from MultiGP
- RotorHarzard v4.1-beta.2+

.. note::

   An internet connection is **not** required for running the event, unless ZippyQ is being used

Requirements for Global Qualifiers
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _gq versions:

Global Qualifier have stricter requirements for what versions of RotorHarzard and the MultiGP Toolkit can be used.
The follow table contains the currently approved versions and is expected to change throughout the developed of RotorHazard.

.. list-table::
    :widths: 30 30
    :header-rows: 1
    :align: center

    * - Software Component
      - Approved Versions
    * - RotorHazard
      - |approved_rh_versions|
    * - MultiGP Toolkit
      - |approved_tk_versions|

.. warning:: 
   
   You must use the RotorHarzard user interface when using RotorHarzard and the MultiGP Toolkit for running your Global Qualifier events.
   
   Use of timing solutions that connect to the RotorHarzard timer (such as LiveTime and Trackside) are not approved to be used alongside
   the MultiGP Toolkit for Global Qualifiers.

.. seealso::

   :ref:`Additional rules when running Global Qualifier events <gq rules>`.

Support
---------------------------

Please reach out in the `RotorHarzard discord server <https://discord.gg/ANKd2pzBKH>`_ for support.

Issues and feature requests can be submitted `here <https://github.com/i-am-grub/MultiGP_Toolkit/issues>`_.

Noteworthy RotorHarzard Best Practices 
---------------------------

You may notice the performance of certain aspects of the timer's user interface degrade as more race data is collected throughout the event. A few things can be done to combat this issue.

- Limit user access to the timer. Avoid letting pilots login to the raspberry pi to check results.
   - If you have access to an internet connection, consider uploading your race data to MultiGP, FPVScores, or `RHCloudlink <https://rhcloudlink.com/home>`_ for pilots to view
- Use a higher model raspberry pi in the timer. The raspberry pi 3B is currently recommended up to 100 pilot-races (number of pilots per race * number of races).
   - Above the 100 pilot-races threshold, a raspberry pi 4B or 5 is advised (the more RAM, the better)


Sections
---------------------------

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