# Kiln Monitor for Home Assistant

A custom integration that surfaces your Bartlett Instruments kiln in Home Assistant by polling the KilnAid cloud service. Once configured, your kiln's temperature, status, and firing history are exposed as native Home Assistant sensors that you can dashboard, automate, and graph like any other entity.

## Features

- **Live kiln telemetry** — temperature, kiln status, firmware version, lifetime firings count, and zone count.
- **Firing progress** — estimated time remaining, elapsed firing time, current program segment, set point, and the active program name while a firing is in progress.
- **Element-set tracking** — record when a new set of heating elements was installed and track how many firings are on the current set, so you know when they're due for replacement.
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
| Estimated Time Remaining | — | Time left in the current firing (e.g. `9h 53m`) |
| Firing Time | — | Elapsed time since the firing started (e.g. `4:49`) |
| Hold Remaining Time | — | Time left in the current hold (e.g. `0:00`) |
| Current Segment | — | Active program segment (e.g. `Ramp 3 of 6`) |
| Set Point | °F | Target temperature the controller is driving toward |
| Program Name | — | Name of the running firing program (e.g. `Cone 06 Slow`) |

The firing-progress sensors come from the kiln's live status feed and are only
meaningful while a firing is in progress; the service reports stale values when
the kiln is idle.

Sensor names are prefixed with the kiln name so they remain unambiguous when multiple kilns are configured.

## Element-set tracking

Kiln heating elements wear out after a number of firings. Since the kiln's
**Number of Firings** is a lifetime counter that never resets, the integration
adds a per-kiln set of element-tracking entities:

| Entity | Type | Purpose |
| --- | --- | --- |
| Elements installed | Date *(Configuration)* | The date the current element set was installed. This is the only thing you set — enter it whenever you fit new elements. |
| Firings on current elements | Sensor | Read-only count of how many firings are on the current set. Counts up as the kiln fires and is graphed in history. |

You only ever set the **Elements installed** date. From it, *Firings on current
elements* is derived as the lifetime **Number of Firings** today minus what it
was on that date — read back from Home Assistant's own recorded history of the
firing counter. After fitting new elements, just set the date and the count
starts from 0.

This means the date can be entered retroactively: set it to when the elements
were actually changed and the count is computed from history, no manual
correction needed. The firing counter is recorded as long-term statistics
(kept indefinitely), so old dates still work. If you enter a date from *before*
Home Assistant began recording this kiln, the count shows **unknown** rather
than a guess.

No separate history of past element sets is stored — Home Assistant keeps it
natively: the **Elements installed** date logs each replacement, and the
**Firings on current elements** value is recorded in history so you can graph
each set's wear over time.

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
