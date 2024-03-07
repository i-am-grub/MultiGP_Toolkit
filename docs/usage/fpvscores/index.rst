Setting Up FPVScores
===========================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

The RotorHazard Development Team has teamed up with with `FPVScores <https://fpvscores.com/>`_ to provide a platform to host your race results!

.. image:: mgp_link.png
    :width: 800
    :alt: FPVScores Event Link
    :align: center

.. _fpvscores table:

.. list-table:: Uploading to FPVScores with the MultiGP Toolkit
    :widths: 30 30 30
    :header-rows: 1
    :align: center

    * - 
      - Standard MultiGP Race
      - MultiGP Global Qualifier
    * - Is uploading to FPVScores optional?
      - Yes
      - No, it is mandatory to upload to FPVScores
    * - Do I need an Event UUID from FPVScores?
      - Only when you want to upload to FPVScores and your Organisation **is not** linked
      - No
    * - Am I required to link my FPVScores Organisation to MultiGP
      - No
      - No
    * - Can FPVScores automatically create an event for me?
      - Yes, when you have linked an FPVScores Organisation to MultiGP
      - All events will be automatically created. If you have a linked FPVScores Organisation, the event will be created under your Organisation, otherwise, an ``Unlinked`` event will be created to store your results. 

Linking a FPVScores Organisation
-------------------------------------------

1. Navigate to `FPVScores <https://fpvscores.com/>`_.

2. When signed in as a Organisation Organisator, open the ``Event Manager``

    .. image:: event_manager.png
        :width: 600
        :alt: Event Manager
        :align: center

3. Open ``Organisation Settings``

    .. image:: organisation_settings.png
        :width: 600
        :alt: Event Manager
        :align: center

4. Scroll down to the ``MultiGP Chapter API`` field and enter your MultiGP Chapter's API key

    .. image:: chapter_apikey.png
        :width: 600
        :alt: MultiGP Chapter API key
        :align: center

5. Click the ``Update Settings`` button

You can now upload results to your FPVScores Organisation without providing an Event UUID to the MultiGP Toolkit when uploading your race results!

Finding an Event UUID for a race
-------------------------------------------

1. Navigate to `FPVScores <https://fpvscores.com/>`_.

2. When signed in as a Organisation Organisator, open the ``Event Manager``

    .. image:: event_manager.png
        :width: 600
        :alt: Event Manager
        :align: center

3. Open the ``Events`` page

    .. image:: events.png
        :width: 600
        :alt: Organisation Events
        :align: center

4. Click the ``COPY`` button for the event with the UUID you desire

    .. image:: uuid_copy.png
        :width: 600
        :alt: UUID Copy
        :align: center

Your UUID should now be stored within your clipboard. This value can now be pasted from the clipboard as needed.