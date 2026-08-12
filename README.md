[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/Naereen/StrapDown.js/graphs/commit-activity)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate with Hassfest](https://github.com/dodog/librelink/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/dodog/librelink/actions/workflows/hassfest.yaml)
[![Validate with HACS](https://github.com/dodog/librelink/actions/workflows/validate.yaml/badge.svg)](https://github.com/dodog/librelink/actions/workflows/validate.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
 

# LibrelinkUp Integration for Home Assistant 


[integration_librelink]: https://github.com/dodog/librelink.git
[buymecoffee]: https://www.buymeacoffee.com/dodog


> **Note:** This fork is a continuation of [librelink](https://github.com/gillesvs/librelink) integration by [@gillesvs](https://github.com/gillesvs) 

Bring your Abbott FreeStyle Libre Link continuous glucose monitor (CGM) data into Home Assistant, straight from your **LibreLinkUp** account — no extra hardware, no scraping required.

For every patient linked to your LibreLinkUp account, this integration creates a full set of sensors with an enhanced, noise-reduced trend calculation that's more accurate than the sensor's native trend readout.

## Features
- 📈 **Enhanced trend calculation** — More accurate than the sensor's native trend. Uses a weighted average across multiple time windows (1-min, 5-min, 15-min) with smoothing logic to reduce noise and better reflect true physiological changes, instead of relying on the sensor's raw native trend.
- 🎯 **Time In Range (24h)** — Rolling 24-hour percentage of readings within your target range, persisted across Home Assistant restarts.
- 🩸 **Per-patient sensors** — automatically sets up entities for every patient linked to your LibreLinkUp account.
- ⚠️ **High/low binary sensors** — instantly know when glucose is out of range.
- 🖥️ **Configured entirely through the Home Assistant UI** — no YAML required to get started.
- 🔁 **Session-based authentication** — token retrieved automatically for the duration of the Home Assistant session.
- 🌍 **Multi language support** — English, German, French, Slovak, Polish.
   
## Entities Created

### `sensor`

| Sensor | Description |
|---|---|
| Expiration of Sensor (days) | Number of days remaining until the CGM sensor expires |
| Glucose Measurement (mg/dL) | Latest glucose reading, updated every minute. |
| Time In Range (24h) | Percentage of readings within your target range over a rolling 24-hour window. Survives Home Assistant restarts by rebuilding from recorder history. |
| Glucose Trend | Direction and speed of glucose change, classified using clinical thresholds. |
| Trend Arrow | Visual arrow indicator: ↑ ↗ → ↘ ↓ |
| Rate of Change | Precise speed of change, in mg/dL/min or mmol/L/min. |
| Delta 1 / 5 / 15 Min | Absolute change in glucose over the last 1, 5, and 15 minutes (mg/dL or mmol/L). |
| Minutes Since Update | Time elapsed since the last reading was received. |


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

### Via HACS (recommended)

1. In Home Assistant, go to **[HACS](https://hacs.xyz/)**.
2. Add this repository as a **custom repository**:
   `https://github.com/dodog/librelink`
3. Search for **Librelink** and install it.
4. Restart Home Assistant.


### Manual

1. Copy the `custom_components/librelink` folder from this repository into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

  

## Configuration

Configuration is done entirely from the Home Assistant UI:

1. Go to **Settings → Devices & Services → Integrations**.
2. Click **+ Add Integration** and search for **Librelink**.
3. Enter the **username (email)** and **password** of your LibreLinkUp account, not Libreview.

**Requirements:**
- A valid LibreLinkUp account.
- You must have accepted the Abbott user agreement inside the LibreLinkUp mobile app before the integration can retrieve data.

> An authentication token is retrieved automatically and remains valid for the duration of the Home Assistant session — no manual token management needed.
                                              


## Contributing

Contributions, bug reports, and feature requests are welcome! Please read the [Contribution Guidelines](CONTRIBUTING.md) before opening a pull request or issue.

## Support the Project

If this integration helps you manage your (or a loved one's) diabetes data, consider supporting its development:

- ☕ [Buy Me a Coffee](https://www.buymeacoffee.com/dodog)
- 💛 [Ko-fi](https://ko-fi.com/dodog)

## Credits

This project is forked from and built on the work of:

- [@gillesvs](https://github.com/gillesvs/librelink)
- [@kubasaw](https://github.com/kubasaw/librelink)

## License

Distributed under the [MIT License](LICENSE.txt).

---

**Disclaimer:** This is an unofficial, community-maintained integration and is not affiliated with, endorsed by, or supported by Abbott. It is not a medical device and should not be used as the sole basis for diabetes management decisions. Always follow guidance from your healthcare provider and refer to your official LibreLinkUp/FreeStyle Libre app for critical readings.
                                                   
