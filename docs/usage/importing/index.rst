.. _importing from mgp:

Importing an Event into RotorHazard
==========================================

.. important::

        All instructions under this section will be performed under the ``Format`` page

        .. image:: format.png
                :width: 500
                :alt: RotorHazard Format page
                :align: center

        If the panels under this subsection are not visable, verify your **timer** has an internet
        connection and reboot the system. After rebooting, there may be a delay before an internet connection
        is established.

Waiting for Plugin Activation
-------------------------------------------

After placing your MultiGP chapter's timer API key into the RotorHazard system,
the plugin will activate if the timer has an internet connection after rebooting.
The server will wait for a duration of time before checking the internet to give the
timer the some extra time to establish the connection.

Archiving any Previous Events
-------------------------------------------

Before importing a new event, it is best practice to archive your previous event. To archive
your previous event start by locating the ``Event`` panel.

1. Open up the ``Event`` panel and then click ``Archive/New Event``

    .. image:: archive.png
            :width: 600
            :alt: Archive Panel
            :align: center

2. Select ``Races, Heats, Classes, and Pilots`` from the drop-down selector

    .. image:: archive_selection.png
            :width: 400
            :alt: Archive Selection
            :align: center

3. Press ``Archive Event`` to backup your race data

    .. image:: archive_button.png
            :width: 400
            :alt: Archive Selection
            :align: center

Your previous event can now be seen under the ``Archived Events`` menu

.. image:: archived_events.png
            :width: 600
            :alt: Archive Selection
            :align: center

Import a MultiGP Event
-------------------------------------------

1. Locate the ``MultiGP Race Import`` panel. The panel will include the name of the MultiGP chapter 
associated with the entered MultiGP API key.

    .. image:: race_panel.png
            :width: 600
            :alt: Race Panel
            :align: center

2. Select the race that you would like to import from MultiGP from the drop-down selector
and then click ``Import Race``

    .. image:: race_import.png
            :width: 600
            :alt: Race Import
            :align: center

.. tip::

        Turn on ``Download Logo`` to download the chapter's logo to the timer. It will automatically
        be added to your timer's home page.

        .. image:: home_page.png
                :width: 500
                :alt: Race Import
                :align: center

After importing, you should see a few changes made to the RotorHazard user interface. The following table outlines
the type of changes that should be shown depending on the type of race that was imported.

.. list-table:: What's visable after importing a race?
    :widths: 30 10 10
    :header-rows: 1
    :stub-columns: 1

    * - 
      - Controlled Race
      - ZippyQ Race
    * - Event Name Change
      - Yes
      - Yes
    * - Event Description Change
      - Yes
      - Yes
    * - Imported Pilots under the ``Pilots`` panel
      - Yes
      - No
    * - An imported class under the ``Classes and Heats`` panel
      - Yes
      - Yes
    * - Heats set up under the newly imported class
      - Yes
      - No
    * - A ``MultiGP Pilot Import`` panel
      - Yes
      - Yes
    * - A ``ZippyQ Controls`` panel
      - No
      - Yes
    * - A ``MultiGP Results Controls`` panel
      - Yes
      - Yes
    * - A ``ZippyQ Pack Return`` panel (under the ``Marshal`` page)
      - No
      - Yes


      




