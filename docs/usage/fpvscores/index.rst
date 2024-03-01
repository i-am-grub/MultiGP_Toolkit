Setting Up FPVScores
===========================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

The RotorHazard Development Team has teamed up with with `FPVScores <https://fpvscores.com/>`_ to provide a platform to host your race results!

.. image:: mgp_link.png
    :width: 1000
    :alt: FPVScores Event Link

.. _fpvscores table:

.. list-table:: MultiGP Toolkit's Ability to Upload to FPVScores
    :widths: 25 25 50
    :header-rows: 1

    * - 
      - FPVScores Event UUID
      - Linking MultiGP Chapter API key to FPVScores Organisation
    * - **Standard MultiGP Race**
      - *Required* when FPVScores Organisation **is not** linked **or** *Optional* when FPVScores Organisation **is** linked
      - *Required* when FPVScores Event UUID **is not** provided at upload
    * - **MultiGP Global Qualifier**
      - *Not Required*
      - *Not Required* - when uploading without a linked FPVScores Organisation, the results will be uploaded without being linked to an FPVScores Organisation. These results **will not** be capable of being managed by an Organisation once uploaded.::

Linking a FPVScores Organisation
-------------------------------------------

1. Navigate to `FPVScores <https://fpvscores.com/>`_.

2. When signed in as a Organisation Organisator, open the event manager

    .. image:: event_manager.png
        :width: 400
        :alt: Event Manager

3. Open your Organisation's settings

    .. image:: organisation_settings.png
        :width: 400
        :alt: Event Manager

4. Enter your MultiGP Chapter's timer API key

    .. image:: chapter_apikey.png
        :width: 400
        :alt: MultiGP Chapter API key

5. Click the ``Update Settings`` button

You can now upload results to your FPVScores Organisation without providing an Event UUID to the MultiGP Toolkit when uploading your race results!

Finding and Event UUID for a race
-------------------------------------------

1. Navigate to `FPVScores <https://fpvscores.com/>`_.

2. When signed in as a Organisation Organisator, open the event manager

    .. image:: event_manager.png
        :width: 400
        :alt: Event Manager

3. Open the events page

    .. image:: events.png
        :width: 400
        :alt: Organisation Events

4. Click the ``COPY`` button for the event with the UUID you desire

    .. image:: uuid_copy.png
        :width: 400
        :alt: UUID Copy

Your UUID should now be stored within your Clipboard