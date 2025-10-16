[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/Naereen/StrapDown.js/graphs/commit-activity)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate with Hassfest](https://github.com/dodog/librelink/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/dodog/librelink/actions/workflows/hassfest.yaml)
[![Validate with HACS](https://github.com/dodog/librelink/actions/workflows/validate.yaml/badge.svg)](https://github.com/dodog/librelink/actions/workflows/validate.yaml)

Forked from [@gillesvs](https://github.com/gillesvs/librelink) and [@kubasaw](https://github.com/kubasaw/librelink).  
All credit goes to them.

# LibrelinkUp Integration for Home Assistant 


[integration_librelink]: https://github.com/dodog/librelink.git
[buymecoffee]: https://www.buymeacoffee.com/dodog

**This integration will set up the following platforms for each patient linked to the librelinkUp account.**

Platform | Description
-- | --

`sensor` | Show info from LibrelinkUp API.
- Active Sensor (in days) : All information about your sensor. State is number of days since activation.
- Glucose Measurement (in mg/dL) : Measured value every minute.
- Glucose Trend : in plain text + icon.
- Minutes since update (in min) : self explanatory.

`binary_sensor` | to measure high and low.
- Is High | True of False.
- Is Low  | True of False.

## Illustration with a custom:mini-graph-card
<img width="612" height="414" alt="302025877-bfed1b2b-dbf7-4666-a202-885ff3db67b8" src="https://github.com/user-attachments/assets/19257952-2cce-4872-8db3-4738889430b2" />


And the yaml if you like this card:
https://github.com/dodog/librelink/blob/main/custom_components/librelink/mini-graph-glucose.yml


## Installation

1. Add this repository URL as a custom repository in HACS
2. Restart Home Assistant
3. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Librelink"

## Configuration is done in the UI

You need a librelinkUp account to use this integration
User must have accepted Abbott user agreement in the librelinkUp app for the integration to work.

- Use username (mail) and password of the librelinkUp account.
- A token will be retreived for the duration of the HA session.


## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

<a href="https://www.buymeacoffee.com/dodog" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>
