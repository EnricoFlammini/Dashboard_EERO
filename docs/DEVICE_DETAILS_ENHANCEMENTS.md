# Device Details Enhancements (backlog)

Findings from the Devices tab / device settings review against the eero API. Items 1–7 shipped on `feat/devices-card-view`; the rest are proposals, not yet built.
Field names for the B items assume the usual eero device payload and should be checked against a real device object.

## Shipped
1. The modal's hostname row shows the name the device reports (`reported_hostname`), not the display name.
2. `POST /api/devices/{mac}/profile` requires `action_edit_devices`.
3. MQTT device trackers cap at 1000 (`MAX_TRACKED_DEVICES`) and log a warning once when truncated.
4. Manufacturer and model on cards and in the modal, and included in search.
5. Last active in the modal; cards show "Last seen" for offline devices.
6. Wi-Fi standard (`phy_type`) and channel width on cards and in the modal.
7. Guest-network flag (`is_guest`) as a badge and in the modal.

## Proposed
- **Per-device pause:** Pause/resume switch in the modal and on the card. Needs a new endpoint gated by `action_pause_devices`; the cloud call already exists (used by Focus Mode).
- **Forget/remove or block a device**, if the eero API allows it.
- **Device notifications:** offline/back-online for favorites, and a gaming-target-offline alert (today only "new device" notifies).
- **Search and filters:** filter by guest, paused, and offline for more than N days; sort by last active.
- **Export:** verify hosts/AdGuard export includes IPv6 and honours "exclude from DNS sync".
- **MQTT trackers:** use `custom_name`, propagate renames after first publish, expose last-seen.
- **Signal quality:** show TX bitrate, signal average and score from `connectivity`.
- **Polish:** clearer paused state in the table; deep links from a card to the modal's Static IP and Port Forwarding tabs; manufacturer in the list view's name cell.
