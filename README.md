# MultiGP Toolkit plugin for RotorHazard

![MultiGP](docs/multigp-logo.png)

## Plugin Documentation

[![Documentation Status](https://readthedocs.org/projects/multigp-toolkit/badge/?version=latest)](https://multigp-toolkit.readthedocs.io/en/latest/?badge=latest)

The documentation for this plugin can be found [here](https://multigp-toolkit.readthedocs.io)

## Plugin Overview

This is a plugin developed with cooperation from MultiGP for the [RotorHazard](https://github.com/RotorHazard/RotorHazard) timing system. It gives RotorHazard the ability interface with MultiGP's RaceSync system for event management.

This plugin now comes packaged with a mini version of [FPVScores](https://github.com/FPVScores/FPVScores) allowing you to push your event results without the need to install the full version.

## General Requirements

- RotorHazard v4.1+ is required to run this plugin
   - Stricter RotorHazard version requirements are enforced for running Global Qualifers. Please see the current release's documentation for details.
- You will need your MultiGP Chapter's API key
- An internet connection when pushing data to or pulling data from MultiGP

> [!NOTE]
> An internet connection is not required for running the event, unless ZippyQ is being used

## Installing the Plugin

Please reference the [installation documentation](https://multigp-toolkit.readthedocs.io/stable/usage/install/index.html) when installing this plugin. 

Downloading the repository's source code from GitHub is not a valid installation method as a closed source module is bundled in at the time
of the release.

> [!NOTE]
> Due to our agreement with MultiGP, the offical releases of the MultiGP Toolkit comes bundled with a closed source module.
> When running a Global Qualifier, this module will verify the system and give the MultiGP Toolkit the ability to sign off on the pushed race data. 
> When running a standard event, this module will be dormant and allow code modifications to both the RotorHazard server and the MultiGP Toolkit. 
> All other actions besides verifiying the system and signing off on race data for Global Qualifiers are open source.

## Plugin Support

Please reach out in the [RotorHarzard discord server](https://discord.gg/ANKd2pzBKH) for support.

Issues and feature requests can be submitted [here](https://github.com/i-am-grub/MultiGP_Toolkit/issues).