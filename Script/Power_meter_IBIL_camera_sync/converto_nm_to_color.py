import sys

def wavelength_to_hex(wavelength):
    """
    Convert wavelength (nm) to RGB hex color
    Valid range: 380-750 nm
    """
    if wavelength < 380 or wavelength > 750:
        return "#000000"

    if wavelength < 440:
        r = -(wavelength - 440) / (440 - 380)
        g = 0
        b = 1

    elif wavelength < 490:
        r = 0
        g = (wavelength - 440) / (490 - 440)
        b = 1

    elif wavelength < 510:
        r = 0
        g = 1
        b = -(wavelength - 510) / (510 - 490)

    elif wavelength < 580:
        r = (wavelength - 510) / (580 - 510)
        g = 1
        b = 0

    elif wavelength < 645:
        r = 1
        g = -(wavelength - 645) / (645 - 580)
        b = 0

    else:
        r = 1
        g = 0
        b = 0

    rgb = (
        int(r * 255),
        int(g * 255),
        int(b * 255)
    )

    return "#{:02x}{:02x}{:02x}".format(*rgb)