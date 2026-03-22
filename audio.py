"""Windows mic and speaker mute control via Core Audio API."""

import logging

import comtypes
from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
from pycaw.api.endpointvolume import IAudioEndpointVolume
from pycaw.constants import CLSID_MMDeviceEnumerator, EDataFlow, ERole

log = logging.getLogger(__name__)


def _get_volume_interface(data_flow: EDataFlow):
    """Get IAudioEndpointVolume for the default render or capture device."""
    enumerator = comtypes.CoCreateInstance(
        CLSID_MMDeviceEnumerator,
        IMMDeviceEnumerator,
        comtypes.CLSCTX_INPROC_SERVER,
    )
    device = enumerator.GetDefaultAudioEndpoint(
        data_flow.value, ERole.eMultimedia.value
    )
    iface = device.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
    return iface.QueryInterface(IAudioEndpointVolume)


def _get_mic():
    return _get_volume_interface(EDataFlow.eCapture)


def _get_speakers():
    return _get_volume_interface(EDataFlow.eRender)


# --- Microphone ---

def get_mic_muted() -> bool:
    try:
        return bool(_get_mic().GetMute())
    except Exception as e:
        log.warning("Failed to get mic mute state: %s", e)
        return False


def set_mic_mute(state: bool) -> None:
    try:
        _get_mic().SetMute(int(state), None)
        log.info("Mic mute set to %s", state)
    except Exception as e:
        log.warning("Failed to set mic mute: %s", e)


# --- Speakers ---

def get_speaker_muted() -> bool:
    try:
        return bool(_get_speakers().GetMute())
    except Exception as e:
        log.warning("Failed to get speaker mute state: %s", e)
        return False


def set_speaker_mute(state: bool) -> None:
    try:
        _get_speakers().SetMute(int(state), None)
        log.info("Speaker mute set to %s", state)
    except Exception as e:
        log.warning("Failed to set speaker mute: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    comtypes.CoInitialize()
    try:
        muted = get_mic_muted()
        print(f"Mic is currently: {'MUTED' if muted else 'UNMUTED'}")
        set_mic_mute(not muted)
        print(f"Mic is now: {'MUTED' if not muted else 'UNMUTED'}")
        print()
        spk = get_speaker_muted()
        print(f"Speakers are currently: {'MUTED' if spk else 'UNMUTED'}")
    finally:
        comtypes.CoUninitialize()
