"""Select one Apple device without changing targets during a task."""


class ConnectionUnavailableError(RuntimeError):
    """No unambiguous device is reachable on the allowed transports."""


def discovery_target(devices, active_serial=None, preferred_serial=None):
    """A new USB connection chooses the target; reconnects never change it."""
    if active_serial is not None:
        return active_serial
    return (
        None if any(d.connection_type == "USB" for d in devices) else preferred_serial
    )


def select_device(devices, allow_wifi=False, serial=None):
    """Prefer USB; Wi-Fi is opt-in and reconnects stay on the same device."""
    allowed = {"USB", "Network"} if allow_wifi else {"USB"}
    candidates = [d for d in devices if d.connection_type in allowed]
    if serial is not None:
        candidates = [d for d in candidates if d.serial == serial]
    usb = [d for d in candidates if d.connection_type == "USB"]
    candidates = usb or candidates
    unique = {d.serial: d for d in candidates}
    if len(unique) != 1:
        if serial is not None and not unique:
            raise ConnectionUnavailableError(
                "Reconnect the same iPhone or iPad used when the task started. "
                "For Wi-Fi, keep both devices on the same network, or reconnect USB."
            )
        detail = (
            "Connect one unlocked, trusted iPhone or iPad by USB. For Wi-Fi, "
            "complete setup once by USB and keep both devices on the same network."
            if allow_wifi
            else "Connect exactly one unlocked, trusted iPhone or iPad by USB."
        )
        raise ConnectionUnavailableError(detail)
    return next(iter(unique.values()))
