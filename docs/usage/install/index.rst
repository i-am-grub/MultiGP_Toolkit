Plugin Installation
===========================================

.. toctree::
   :maxdepth: 1
   :caption: Contents:

There are currently two methods for installing and updating the MultiGP Toolkit on the RotorHazard server. Either using a CLI method or by manually downloading the files from GitHub and copying them over to the raspberry pi.

CLI Installation
-------------------------------------------

These instructions assume that your RotorHazard instance is installed in the ``~/`` directory as outlined by the `RotorHazard Installation instructions <https://github.com/RotorHazard/RotorHazard/blob/main/doc/Software%20Setup.md#7-install-the-rotorhazard-server>`_.

1. Navigate to the ``~/`` directory::

    cd ~

2. Remove any previous versions of the plugin::

    sudo rm -r RotorHazard/src/server/plugins/MultiGP_Toolkit

3. Download the latest release's ``zip file`` from `GitHub <https://github.com/i-am-grub/MultiGP_Toolkit/releases>`_. Replace VERSION within link with |project_version|::

    wget https://github.com/i-am-grub/MultiGP_Toolkit/releases/download/VERSION/MultiGP_Toolkit.zip

4. Unzip the download::

    unzip MultiGP_Toolkit.zip
    
5. Copy the files over to the ``~/RotorHazard/src/server/plugins`` folder::
    
    cp -r MultiGP_Toolkit RotorHazard/src/server/plugins/

6. Delete the downloaded files::

    rm -r MultiGP_Toolkit

    rm MultiGP_Toolkit.zip

7. Restart the server::

    sudo reboot

If installation is successful, ``MultiGP Toolkit`` should be listed under the ``Plugins`` panel under the ``Settings`` tab after rebooting

Manual Installation
-------------------------------------------

Navigate to the `MultiGP Toolkit's Releases <https://github.com/i-am-grub/MultiGP_Toolkit/releases>`_ page