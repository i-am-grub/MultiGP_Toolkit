Using MultiGP's ZippyQ System
==============================

.. note::

    The ``ZippyQ Controls`` and ``ZippyQ Pack Return`` panels are only visable when a ZippyQ
    race has been imported.

.. note::

    After a race utilizing ZippyQ has been saved (either after running the race or marshaling)
    the result will be uploaded automatically to MultiGP.

Import ZippyQ Rounds
------------------------------

.. _zippy controls:

.. important::

        All instructions under this subsection will be performed under the ``Format`` page

        .. image:: ../importing/format.png
                :width: 500
                :alt: RotorHazard Format page
                :align: center

        If the panels under this subsection are not visable, verify your **timer** has an internet
        connection and reboot the system. For more information, review the section on the 
        :ref:`plugin's activation <plugin activation>`.

After importing a race with ZippyQ enabled, a new class under ``Classes and Heats`` will
be created. This class will not have any heats under it.

.. image:: zippyq_class.png
        :width: 600
        :alt: ZippyQ Class
        :align: center

.. important::
        The ZippyQ tools will only work with the class that was setup for you at the time
        of importing the MultiGP race. Deleting this class will prevent you from being
        able to use ZippyQ.

1. To import rounds from MultiGP, locate the ``ZippyQ Controls`` panel.

    .. image:: zippyq_controls.png
            :width: 600
            :alt: ZippyQ Controls Panel
            :align: center

2. Open the ``ZippyQ Controls`` panel and click the ``Import Next ZippyQ Round`` button

    .. image:: import_round.png
            :width: 600
            :alt: Import ZippyQ round
            :align: center

The first ZippyQ round and the pilots within the round should now imported within RotorHazard

.. image:: imported_round.png
        :width: 600
        :alt: Imported ZippyQ round
        :align: center

.. hint::
        Turning on ``Use Automatic ZippyQ Import`` will automatically download the next
        ZippyQ round when the race for the previous one has finished. This prevents the need to click the 
        ``Import Next ZippyQ Round`` after every round.

.. hint::
        Turning on ``Active Race on Import`` will automatically set the next round as the
        active race after downloading either manually or automatically. This feature will trigger the ``Heat Change``
        event within RotorHazard if you have an ``Event Action`` setup under the ``Settings`` page.

ZippyQ Pack Return
------------------------------

.. important::

        All instructions under this subsection will be performed under the ``Marshal`` page

        .. image:: marshal_page.png
                :width: 500
                :alt: RotorHazard Marshal page
                :align: center

        If the panels under this subsection are not visable, verify your **timer** has an internet
        connection and reboot the system. For more information, review the section on the 
        :ref:`plugin's activation <plugin activation>`.

The toolkit supports the functionality to give a pilot their pack back after a race if needed. 

.. image:: pack_return.png
        :width: 600
        :alt: Pack Reutrn
        :align: center

1. Open the ``ZippyQ Pack Return Panel``.

2. Select the Race the pilot particpated in from the ``Race Result`` selector

3. Select the pilot in the ``Pilot`` selector

4. Click the ``Return Pack`` button

.. note::

    The race director will still need to manually remove the pack through
    the MultiGP ZippyQ admin kiosk for the race.

.. note::

    This action will not remove the results from the RotorHazard system, but it will 
    disassociate the result from the pilot.