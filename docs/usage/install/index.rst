Plugin Installation
===========================================

There are currently two methods for installing and updating the MultiGP Toolkit on the RotorHazard server. Either using a CLI method or by manually downloading the files from GitHub and copying them over to the raspberry pi.

These instructions assume that your RotorHazard instance is installed in the ``~/`` directory as outlined by the `RotorHazard Installation instructions <https://github.com/RotorHazard/RotorHazard/blob/main/doc/Software%20Setup.md#7-install-the-rotorhazard-server>`_.

CLI Installation
-------------------------------------------

1. Navigate to the ``~/`` directory::

    cd ~

2. Remove any previous versions of the plugin::

    sudo rm -r RotorHazard/src/server/plugins/MultiGP_Toolkit

3. Download the latest release's ``zip file`` from `GitHub <https://github.com/i-am-grub/MultiGP_Toolkit/releases>`_. Replace ``VERSION`` with |project_version| within the following command with for the lastest version of the plugin::

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

.. image:: install_verify.png
        :width: 500
        :alt: Installation Verification

Manual Installation
-------------------------------------------

1. Navigate to the `MultiGP Toolkit's Releases <https://github.com/i-am-grub/MultiGP_Toolkit/releases>`_ page

2. Navigate to the release for |project_version| (the latest stable release) and open the ``Assets`` tab.

    .. image:: assets.png
        :width: 400
        :alt: GitHub's Assets Tab

3. Download the ``MultiGP_Toolkit.zip`` file

    .. image:: toolkit_zip.png
        :width: 400
        :alt: MultiGP Toolkit's zip file location

4. Unzip the downloaded file. Once unzipped, you should have a folder named ``MultiGP_Toolkit``. When opened, there should be several files within it.

5. Install the ``MultiGP_Toolkit`` folder into the ``~/RotorHazard/src/server/plugins`` folder within your RotorHazard installation

6. Restart the server::

If installation is successful, ``MultiGP Toolkit`` should be listed under the ``Plugins`` panel under the ``Settings`` tab after rebooting

.. image:: install_verify.png
        :width: 500
        :alt: Installation Verification