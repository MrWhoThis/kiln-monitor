# Kiln Monitor for Home Assistant

A custom integration that surfaces your Bartlett Instruments kiln in Home Assistant by polling the KilnAid cloud service. Once configured, your kiln's temperature, status, and firing history are exposed as native Home Assistant sensors that you can dashboard, automate, and graph like any other entity.

## Features

- **Live kiln telemetry** — temperature, kiln status, firmware version, lifetime firings count, and zone count.
- **Multiple kilns per account** — every kiln on your KilnAid account gets its own device and sensors automatically.
- **Adaptive polling** — polls frequently (default: every 5 minutes) while a kiln is actively firing and backs off (default: every 15 minutes) when idle. Both intervals are configurable in the integration's options.
- **Reauthentication flow** — if your stored password stops working (e.g. after changing it in the KilnAid app), Home Assistant prompts you to re-enter it without losing your sensors or history.
- **UI-based setup** — no YAML required. Configure via **Settings → Devices & Services**.

## Sensors

For each kiln on your account, the following sensors are created:

| Sensor | Unit | Notes |
| --- | --- | --- |
| Temperature | °F | Live kiln temperature reading |
| Status | — | Current kiln state (e.g. `Firing`, `Idle`, `Cooling`) |
| Firmware Version | — | Reported firmware version of the kiln controller |
| Number of Firings | firings | Lifetime firing counter |
| Zone Count | zones | Number of controlled zones on the kiln |

Sensor names are prefixed with the kiln name so they remain unambiguous when multiple kilns are configured.

## Installation (via HACS)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant.
2. In HACS, open **Integrations**, click the three-dot menu in the top right, and choose **Custom repositories**.
3. Add this repository:
   ```
   https://github.com/MrWhoThis/kiln-monitor
   ```
   with category **Integration**.
4. Search for **Kiln Monitor** in HACS and install it.
5. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration** and search for **Kiln Monitor**.
2. Enter the email and password you use to sign in to the KilnAid mobile app.
3. The integration will discover every kiln on your account and create a device and sensor set for each one.

If you don't yet have a KilnAid account, create one in the KilnAid mobile app first and pair it with your kiln before setting up this integration.

### Polling intervals

After the integration is set up, open it and click **Configure** to adjust the polling intervals:

- **Active polling interval** — used while any kiln on the account is firing. Range: 5–60 minutes (default: 5).
- **Idle polling interval** — used when no kiln is firing. Range: 5–120 minutes (default: 15).

Setting both intervals to the same value disables adaptive polling and polls at a constant rate.

## Reauthentication

If KilnAid starts rejecting the stored credentials, Home Assistant will surface a "Repair" notification prompting you to re-enter your password. Completing the prompt restores the connection without removing your sensors, so dashboards and long-term statistics are preserved.

## Troubleshooting

- **`invalid_auth` during setup** — verify the same email and password work in the KilnAid mobile app. The integration uses the same login.
- **`cannot_connect`** — usually a transient network issue or a KilnAid outage. The integration will retry automatically on its next polling cycle.
- **Stale or missing data** — check the Home Assistant logs for `kiln_monitor` entries. The coordinator logs poll failures and recovery.
- **Polling feels slow** — lower the active and/or idle intervals in the integration's options. Keep in mind these limits exist to be polite to Bartlett's servers.

## Reporting issues

Please open issues at [github.com/MrWhoThis/kiln-monitor/issues](https://github.com/MrWhoThis/kiln-monitor/issues). Logs from `kiln_monitor` at debug level are extremely helpful.
