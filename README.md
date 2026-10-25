[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/Naereen/StrapDown.js/graphs/commit-activity)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate with Hassfest](https://github.com/dodog/librelink/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/dodog/librelink/actions/workflows/hassfest.yaml)
[![Validate with HACS](https://github.com/dodog/librelink/actions/workflows/validate.yaml/badge.svg)](https://github.com/dodog/librelink/actions/workflows/validate.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
 

# LibrelinkUp Integration for Home Assistant 


[integration_librelink]: https://github.com/dodog/librelink.git
[buymecoffee]: https://www.buymeacoffee.com/dodog


> **Note:** This fork is a continuation of unmaintained [librelink](https://github.com/gillesvs/librelink) integration by [@gillesvs](https://github.com/gillesvs) 

Connect your Abbott **FreeStyle LibreLink** continuous glucose monitor (CGM) data into Home Assistant, straight from your **LibreLinkUp** account — no extra hardware, no scraping required.

For every patient linked to your LibreLinkUp account, this integration creates a full set of sensors with an enhanced, trend calculation that's more responsive than the sensor's native trend readout.

## Features
- 📈 **Enhanced trend calculation** — More accurate than the sensor's native trend. Uses a weighted average across multiple time windows (1-min, 5-min, 15-min) with smoothing logic to reduce noise and better reflect true physiological changes, instead of relying on the sensor's raw native trend.
- 🎯 **Time In Range (24h)** — Rolling 24-hour percentage of readings within your target range, persisted across Home Assistant restarts.
- 🩸 **Per-patient sensors** — automatically sets up entities for every patient linked to your LibreLinkUp account.
- ⏳ **Sensor expiry** — shows when the current sensor was applied and when it expires.
- ⚠️ **High/low binary sensors** — instantly know when glucose is out of range.
- 🖥️ **Configured entirely through the Home Assistant UI** — no YAML required to get started.
- 🔁 **Session-based authentication** — token retrieved automatically for the duration of the Home Assistant session.
- 🌍 **Multi language support** — English, German, French, Slovak, Polish.
   
## Entities Created

### `sensor`

| Sensor | Description |
|---|---|
| Measurement | Latest glucose reading, updated every minute, in the unit chosen during setup (mg/dL or mmol/L). |
| Time In Range (24h) | Percentage of readings within your target range over a rolling 24-hour window. Survives Home Assistant restarts by rebuilding from recorder history. |
| Trend | Direction and speed of glucose change, classified using clinical thresholds. |
| Glucose Trend Arrow | Visual arrow indicator: ↑ ↗ → ↘ ↓ |
| Rate of Change | Precise speed of change, in mg/dL/min or mmol/L/min. |
| Delta 1min / Delta 5min / Delta 15min | Absolute change in glucose over the last 1, 5, and 15 minutes (mg/dL or mmol/L). Needs a few minutes of history after a restart. |
| Application Timestamp | When the current sensor was activated. Attributes show the serial number and the sensor lifetime in use. |
| Expiration Timestamp | When the current sensor expires: activation time plus the [sensor lifetime](#sensor-lifetime-14-or-15-days). |
| Last Measurement Timestamp | Time of the latest reading received from LibreLinkUp. |


### `binary_sensor`

| Sensor | Description |
|---|---|
| Is High | `true` when glucose is above the configured high threshold. |
| Is Low | `true` when glucose is below the configured low threshold. |       

## Dashboard Example

You can visualize glucose trends with a 
[`mini-graph-card`](https://github.com/kalkih/mini-graph-card):
<img width="612" height="414" alt="302025877-bfed1b2b-dbf7-4666-a202-885ff3db67b8" src="https://github.com/user-attachments/assets/19257952-2cce-4872-8db3-4738889430b2" />

See the full example here: [mini-graph-glucose.yml](https://github.com/dodog/librelink/blob/main/custom_components/librelink/mini-graph-glucose.yml) 

or you can use [LibreLink Extended Card](https://github.com/dodog/librelink-extended-card)    
<img width="586" height="265" alt="librelink-extended-card-screenshot" src="https://raw.githubusercontent.com/dodog/librelink-extended-card/refs/heads/main/assets/screenshot.jpg" />

## Installation

### Via **[HACS](https://hacs.xyz/)** (recommended)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dodog&repository=librelink&category=integration)

1. Add this repository `https://github.com/dodog/librelink` in HACS
2. Click **download** on bottom right corner and install it.
3. Restart Home Assistant.


### Manual

1. Copy the `custom_components/librelink` folder from this repository into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

  

## Configuration

Configuration is done entirely from the Home Assistant UI:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=librelink)

1. Go to **Settings → Devices & Services → Integrations**.
2. Click **+ Add Integration** and search for **Librelink**.
3. Enter the **username (email)** and **password** of your LibreLinkUp account, not Libreview, and select your region.
4. Select the **patient**, the **unit** for glucose values, and the **sensor lifetime** (see below). You can also enter an optional **display name**: a nickname used in the integration's title instead of the patient's real name.

If an account has several patients, add the integration once per patient. A patient can only be added once.

**Requirements:**
- A valid LibreLinkUp account.
- You must have accepted the Abbott user agreement inside the LibreLinkUp mobile app before the integration can retrieve data.

> An authentication token is retrieved automatically and remains valid for the duration of the Home Assistant session — no manual token management needed.

### Sensor lifetime (14 or 15 days)

LibreLinkUp does not report when a sensor expires, so the integration calculates it: **activation time + sensor lifetime**. The lifetime cannot be read reliably from the data either.

You therefore choose the lifetime:

| Option | Meaning |
|---|---|
| **Automatic** (default) | Old behaviour - a guess from the reported sensor type: type 3 → 14 days, type 4 → 15 days. This can be wrong, for example a Libre 2 Plus would be shown as 14 days. |
| **14 days** | Libre 2, Libre 3 |
| **15 days** | Libre 2 Plus, Libre 3 Plus |

The choice is saved for that patient and applies to every new sensor you activate, so you only need to change it when you switch to a different sensor type. To change it later, open **Settings → Devices & Services → LibreLink** and click **Configure** on the patient's entry. The *Expiration Timestamp* updates immediately, no restart needed.

### If your login stops working

If LibreLinkUp rejects the saved login (for example because you changed your password), polling stops and Home Assistant shows a repair notice for the integration. Click **Reconfigure** on the entry and enter the new password. The entry reloads and keeps its entities and recorded history; trend and delta values need a few minutes to rebuild.

## Removal

1. Go to **Settings → Devices & Services → LibreLink**.
2. Open the **⋮** menu of a patient's entry and choose **Delete**. Repeat for every patient.
3. If you installed via HACS, you can then remove the integration in HACS and restart Home Assistant.

Deleting an entry removes its devices and entities from Home Assistant. Your LibreLinkUp account and your data at Abbott are not affected.
                                              


## Contributing

Contributions, bug reports, and feature requests are welcome! Please read the [Contribution Guidelines](CONTRIBUTING.md) before opening a pull request or issue.

## ❤️ Support the Project

Like this integration? Give it a ⭐ on GitHub. And if this integration helps you manage your (or a loved one's) diabetes data, consider supporting its development:

- ☕ [Buy Me a Coffee](https://www.buymeacoffee.com/dodog)
- 💛 [Ko-fi](https://ko-fi.com/dodog)

## Credits

This project is forked from and built on the work of [@gillesvs](https://github.com/gillesvs/librelink), [@kubasaw](https://github.com/kubasaw/librelink) and others

## License

Distributed under the [MIT License](LICENSE.txt).

---

**Disclaimer:** This is an unofficial, community-maintained integration and is not affiliated with, endorsed by, or supported by Abbott. It is not a medical device and should not be used as the sole basis for diabetes management decisions. Always follow guidance from your healthcare provider and refer to your official LibreLinkUp/FreeStyle Libre app for critical readings.
                                                   
