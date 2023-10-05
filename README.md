# MultiGP Toolkit for RotorHazard

> WARNING: This plugin is compatiable with [RotorHazard v4.0.0-beta.5](https://github.com/RotorHazard/RotorHazard/releases/tag/v4.0.0-beta.5) and newer

This is a plugin developed for the RotorHazard timing system. It allows for the ability to pull and push data through the MultiGP API to assist with event management.

## Requirements

- RotorHazard v4.0+ is required to run the plugin
- You will need your MultiGP Chapter's API key and your user login credentials.
- An internet connection when pushing or pulling data from MultiGP

> NOTE: An internet connection is not required for running the event, unless the automatic tools are being used


## Installation

1. To install, clone or copy this repository's folder into RotorHazard's plugin directory `/src/server/plugins`, and (re)start the server.
    - If installation is successful, the RotorHazard log will contain the message `Loaded plugin module MultiGP_Toolkit` at startup.
2. The plugin should be visable under the Settings tab after rebooting. 

---

## User Guide

The plugin's functionality is split between the Settings and Format tabs in the RotorHazard UI.

### Settings - MultiGP Credentials

![Credentials](docs/settings.png)

This screen is used to authenticate the RotorHarzard system to MultiGP. **Each time the system is restarted, the user must sign in again to activate the plugin's toolkit**

#### Chapter API Key (Text)

The API key for your chapter. Chapter admins should have access to this key by going to their chapter's home page and going to `Manage >> Timing system key >> Copy to Clipboard`

#### Verify Credentials (Button)

Used to check the entered credentials. If the credentials are valid, the user will be signed in and the toolkit will be activated.
- To sign the user out of the system, reboot the system
- Once signed in, the button will still be visable, but will become unusable.

### Format - MultiGP Tools

![MultiGP Tools](docs/format.png)

> Note: The terminology for a ***MultiGP Race*** is equivalent to a ***RotorHazard Class***

#### MultiGP Race (Selector)

Used to select which race the system will interact with on ***MultiGP***'s side
- Races will typically stop appearing when the day of their scheduled event is about 2 months in the past. This characteristic is determined by MultiGP and not the plugin.

#### RotorHazard Class (Selector)

Used to select which class the system will interact with on ***RotorHazard***'s side

#### Automatically push race results (Checkbox)

Once the race is saved (or a race is marshaled), automatically push the results to MultiGP
- Requires the name of the race's class to be exactly the same as the name of the race on MultiGP's side
- If you set up points in RotorHazard's race format, they will also be transfered to MultiGP
- This setting is **NOT** influenced by the `MultiGP Race` or `RotorHazard Class` selectors
- **IMPORTANT**: Any race class with the `Rounds` field set to a value **less than 2** will have it's results pushed with the MultiGP round number set to the race's heat number, and the MultiGP heat set to 1. This special formating is required for ZippyQ results.

#### Automatically pull ZippyQ rounds (Checkbox)

Once the race is saved, automatically pull the next ZippyQ round from MultiGP and import it into the same ***RotorHazard Class*** of the completed race
- When using this feature make sure the following class settings are properly set:
    - `Rounds`: Should be set to 0 or 1 (See notes under `Automatically push heat results` or `Push Class Results`)
    - `Advance Heat`: Should be set to`Never`
        - If set to `Always` or `After All Rounds`, the RotorHazard will try to advance the heat before the next ZippyQ round is imported.
- This setting is **NOT** influenced by the `MultiGP Race` or `RotorHazard Class` selectors
- If a pilot is not in the RotorHazard system and is needed in the race setup, they will automatially be imported
    - This import includes the pilot's MultiGP pilot id. The MultiGP pilot id is mandatory for pushing results
    - When pilots are added to their heats, they are assigned to their race slot by using the ***MultiGP Race***'s slot number, NOT their frequency.
        - You can change the ***MultiGP Race***'s slot configuration by navigating to `Manage >> Manage Race >> Frequency Profile` on the MultiGP event's page. This should be configured before importing a ***MultiGP Race***.

#### ZippyQ round number (Integer)

Set the round number ZippyQ will use when using `Import ZippyQ Round`
- When using this feature make sure the following class settings are properly set:
    - `Rounds`: Should be set to 0 or 1 (See notes under `Automatically push heat results` or `Push Class Results`)
    - `Advance Heat`: Should be set to`Never`
        - If set to `Always` or `After All Rounds`, the RotorHazard will try to advance the heat before the next ZippyQ round is imported.

#### Refresh MultiGP Races (Button)

Refresh the options in the `MultiGP Race` selector

#### Import Pilots (Button)

Import pilots from selected `MultiGP Race`
- This import includes the pilot's `MultiGP Pilot ID`. The `MultiGP Pilot ID` is mandatory for pushing results

#### Import Race (Button)

Import the selected `MultiGP Race`
- If the race is detected to be a non-ZippyQ race, the round number, heats and pilot slot order will also be set up
- When pilots are added to their heats, they are assigned to their race slot by MultiGP's slot number, NOT their frequency.
    - You can change the ***MultiGP Race***'s slot configuration by navigating to `Manage >> Manage Race >> Frequency Profile` on the MultiGP event's page. This should be configured before importing a ***MultiGP Race***.
- If a pilot is not in the RotorHazard system and is needed in the race setup, they will automatially be imported
    - This import includes the pilot's `MultiGP Pilot ID`. The `MultiGP Pilot ID` is mandatory for pushing results


#### Import ZippyQ Round (Button)

Imports the entered `ZippyQ round number` from the selected `MultiGP Race` into the selected `RotorHazard Class`
- If a pilot is not in the RotorHazard system and is needed in the race setup, they will automatially be imported
    - This import includes the pilot's `MultiGP Pilot ID`. The `MultiGP Pilot ID` is mandatory for pushing results

#### Push Class Results (Button)

Pushes the results in the selected `RotorHazard Class` to the selected `MultiGP Race`
- If you set up points in RotorHazard's race format, they will also be transfered to MultiGP
- **IMPORTANT**: Any race class with the `Rounds` field set to a value **less than 2** will have it's results pushed with the MultiGP round number set to the race's heat number, and the MultiGP heat set to 1. This special formating is required for ZippyQ results.

#### Push Class Rankings (Button)

Pushes the rankings in the selected `RotorHazard Class` to the selected `MultiGP Race`.
- You can push the class results to MultiGP and then use the ***RotorHazard Class*** rankings to override the final race rankings on ***MultiGP***'s side
- This action is equivalent to the ***Add Overall Results*** feature in the ***MultiGP Race***'s settings

#### Finalize Event (Button)

Finalizes the selected `MultiGP Race`
- It is considered best practice to verify your results on MultiGP before using this button.
