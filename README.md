# MultiGP interface for RotorHazard

[TOC]

> WARNING: This plugin is still under inital development and will only be compatiable with the RotorHazard v4.0 (non-beta) release

This is a plugin being developed for the RotorHazard timing system. It allows for the ability to pull and push data through the MultiGP API to assist with event management.

## Requirements

- Currently, the main development branch of RotorHazard is required to run the pluging, but it will be compatible with the official release of RotorHazard v4.0 
- You will need your MultiGP Chapter's API key and your user login credentials.

## Installation

1. To install, clone or copy this repository's folder into RotorHazard's plugin directory ```/src/server/plugins```, and (re)start the server.
    - If downloading the zip file directly from GitHub, make sure to rename the plugin's folder to ```MultiGP_Toolkit``` otherwise the plugin will not import
2. The plugin should be visable under the Settings tab after rebooting. 

## User Guide

The plugin's functionality is split between the Settings and Format tabs in the RotorHazard UI.

### Settings

[Credentials](docs/settings.png)

This screen is used to authenticate the RotorHarzard system to MultiGP. Each time the system is restartedm the user must sign in again to activate the plugin's toolkit

#### Chapter API Key (Text)
The API key for your chapter. Chapter admins should have access to this key by going to their chapter's home page and going to Manage >> Timing system key >> Copy to Clipboard

#### MultiGP Username (Text)
User's MultiGP Username

#### MultiGP Password (Text)
User's MultiGP Password

#### Verify Credentials (Button)
Button to check the entered credentials. Once signed in, the button will still be visable, but will become unusable. To sign the user out of the system, reboot the system

[MultiGP Tools](docs/format.png)

#### MultiGP Race (Selector)
Used to select which race the system will interact with on MultiGP's side
- MultiGP has a uncontrollable timeframe for which races are avaliable and which one are not 

#### RotorHazard Class (Selector)
Used to select which race the system will interact with on RotorHazard's side

#### Automatically push heat results (Checkbox)
Once the race is saved (or a race is marshaled), push the results to MultiGP
- Requires the name of the race's class to be exactly the same as the name of the race on MultiGP's side
- This setting is not influenced by the Selectors

#### Automatically pull ZippyQ rounds (Checkbox)
Once the race is saved, pull the next ZippyQ round from MultiGP and import it into the same race class that was completed
- Sets the name of each heat to 'Round X'. You can delete heats as needed, but DO NOT change the names of these heats if you are planning to manually push results for a class that is utalizing ZippyQ

#### Automatically pull ZippyQ rounds (Integer)
Set the round number ZippyQ will use when manually importing a ZippyQ round

#### Refresh MultiGP Races (Button)
Refresh the options in the MultiGP Race selector

#### Import Pilots (Button)
Import Pilots from selected MultiGP Race. This import includes the pilot's MultiGP pilot id. The id is mandatory for pushing results

#### Import Race (Button)
Import race from MultiGP
- If the race is detected to be a non-ZippyQ race, the heats and pilot's slot order will also be set up
- When pilots are added to their heats, they are assigned by MultiGP's slot number, NOT their frequency
- If a pilot is not in the RotorHazard system and is needed in the race setup, they will automatially be imported

#### Import ZippyQ Round (Button)
Imports the entered ZippyQ round number from the selected MultiGP Race into the selected RotorHazard Class

#### Push Class Results (Button)
Pushes the results in the selected RotorHazard Class to the selected MultiGP Race
- If you set up points in RotorHazard's race format, they will also be transfered to MultiGP

#### Push Class Rankings (Button)
Pushes the rankings in the selected RotorHazard Class to the selected MultiGP Race.
- You can push timer results to MultiGP, but still use the Class rankings to override the final race rankings on MultiGP's side

#### Coming Soon: Push Global Qualifer Results (Button) 
Pushes the results in the selected RotorHazard Class to the selected MultiGP Race in the Global Qualifer format

#### Finalize Event
Finalizes the selected MultiGP Race
- It is best practice to verify your results on MultiGP before using this button