"""Utilities for storing and manipulating colors."""

from __future__ import annotations

import math
import random
from enum import Enum
from typing import Iterable


class Color(int):
    """Extension of integer to add common RGB color related functionality."""

    @property
    def blue(self) -> int:
        """Calculate the blue portion of the color.

        Returns:
            Last/rightmost 8 bit section of the color representing blue as 0-255.
        """
        return (0x0000FF & self) >> 0

    def darken(self, amount: float = 0.1) -> Color:
        """Decrease a color's lightness while maintaining RGB ratio.

        Args:
            amount: Percentage to darken the value.

        Returns:
            New RGB color with the lightness applied.
        """
        hsl = HSLColor.from_color(self)
        hsl_dark = hsl.with_lightness(max(0.0, min(hsl.lightness - amount, 1.0)))
        return hsl_dark.to_color()

    @staticmethod
    def from_rgb(red: int, green: int, blue: int) -> Color:
        """Create an RGB color instance using separate RGB values.

        Args:
            red: Red portion of the raw RGB color value (first/leftmost 8 bit group).
            green: Green portion of the raw RGB color value (second 8 bit group).
            blue: Blue portion of the raw RGB color value (last/rightmost 8 bit group).

        Returns:
            New color with a single integer value representing all RGB portions combined.
        """
        value = (((red & 0xFF) << 16) | ((green & 0xFF) << 8) | ((blue & 0xFF) << 0)) & 0xFFFFFFFF
        return Color(value)

    @property
    def green(self) -> int:
        """Calculate the green portion of the color.

        Returns:
            Second 8 bit section of the color representing green as 0-255.
        """
        return (0x00FF00 & self) >> 8

    def lighten(self, amount: float = 0.1) -> Color:
        """Increase a color's lightness while maintaining RGB ratio.

        Args:
            amount: Percentage to darken the value.

        Returns:
            New RGB color with the lightness applied.
        """
        hsl = HSLColor.from_color(self)
        hsl_light = hsl.with_lightness(max(0.0, min(hsl.lightness + amount, 1.0)))
        return hsl_light.to_color()

    @property
    def red(self) -> int:
        """Calculate the red portion of the color.

        Returns:
            First/leftmost 8 bit section of the color representing red as 0-255.
        """
        return (0xFF0000 & self) >> 16

    def to_rgb(self) -> str:
        """Convert the raw color value into RGB hex string.

        Returns:
            Hex string representing color.
        """
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"


class Colors(Enum):
    """Collection of predefined colors."""

    BLACK = Color(0x000000)
    RED = Color(0xFF0000)
    YELLOW = Color(0xFF9600)
    GREEN = Color(0x00FF00)
    CYAN = Color(0x00FFFF)
    BLUE = Color(0x0000FF)
    PURPLE = Color(0xB400FF)
    WHITE = Color(0xFFFFFF)


class HSLColor:
    """Color extension to calculate Hue, Saturation, and Lightness from RGB colors."""

    def __init__(self, hue: float, saturation: float, lightness: float) -> None:
        """Set up the color extension based on HSL values.

        Args:
            hue: Degree on the color wheel as 0.0-360.0.
            saturation: Percentage between grey and full color as 0.0-1.0.
            lightness: Percentage between black and white as 0.0-1.0.
        """
        self.hue = hue
        self.saturation = saturation
        self.lightness = lightness

    @staticmethod
    def from_color(color: Color) -> HSLColor:
        """Convert an RGB color to HSL color values.

        Args:
            color: Original color as RGB combined value.

        Returns:
            RGB value converted into HSL values.
        """
        red = color.red / 0xFF
        green = color.green / 0xFF
        blue = color.blue / 0xFF

        max_rgb = max(red, green, blue)
        min_rgb = min(red, green, blue)
        delta = max_rgb - min_rgb

        hue = rgb_to_hue(red, green, blue, max_rgb, delta)
        lightness = (max_rgb + min_rgb) / 2.0
        saturation = 0.0 if lightness == 1.0 else max(0.0, min(delta / (1.0 - abs(2.0 * lightness - 1.0)), 1.0))
        return HSLColor(hue, saturation, lightness)

    def to_color(self) -> Color:
        """Convert HSL color values to RGB color value.

        Returns:
            HSL values converted into RGB value.
        """
        chroma = (1.0 - abs(2.0 * self.lightness - 1.0)) * self.saturation
        secondary = chroma * (1.0 - abs(((self.hue / 60.0) % 2.0) - 1.0))
        match = self.lightness - chroma / 2.0
        return hue_to_rgb(self.hue, chroma, secondary, match)

    def with_lightness(self, lightness: float) -> HSLColor:
        """Create a new HSL color from the current with a new lightness level.

        Args:
            lightness: Percentage to swap the current lightness with.

        Returns:
            New HSL color with the previous hue/saturation values and new lightness level.
        """
        return HSLColor(self.hue, self.saturation, lightness)


def generate_pattern(
    colors: Iterable[int],
    length: int,
    mirror: bool = False,
    randomize: bool = False,
) -> list[int]:
    """Inflate a list of colors using a small selection of possible colors to create patterns.

    Args:
        colors: Colors to use in pattern.
        length: Total length of the combined pattern.
        mirror: Reverse the colors when the last color is used. Exclusive with other patterns.
        randomize: Randomly choose colors from the color list. Exclusive with other patterns.

    Returns:
        Full list patterned to the requested length.
    """
    colors = colors or [Colors.BLACK.value]
    pattern = []
    if randomize:
        if len(colors) > 1:
            for _ in range(length):
                pattern.append(random.choice(colors))  # nosec B311
        else:
            pattern = colors * length
    elif mirror:
        # Mirror (reverse) colors after all are used.
        current = 0
        for _ in range(length):
            pattern.append(colors[current])
            current += 1
            if current >= len(colors):
                current = 0
                colors = colors[::-1]
    else:
        # Repeat (start over) colors after all are used.
        current = 0
        for _ in range(length):
            pattern.append(colors[current])
            current += 1
            if current >= len(colors):
                current = 0
    return pattern


def hue_to_rgb(hue: float, chroma: float, secondary: float, match: float) -> Color:
    """Convert a hue into an RGB color.

    Args:
        hue: Degree on a color wheel representing the color.
        chroma: Intensity as the departure degree of a color from the neutral color of the same value.
        secondary: Second largest RGB value of the color.
        match: Lightness to apply to all RGB portions of the color.

    Returns:
        Final RGB color value equivalent to combined HSL values.
    """
    if hue < 60.0:
        red = chroma
        green = secondary
        blue = 0.0
    elif hue < 120.0:
        red = secondary
        green = chroma
        blue = 0.0
    elif hue < 180.0:
        red = 0.0
        green = chroma
        blue = secondary
    elif hue < 240.0:
        red = 0.0
        green = secondary
        blue = chroma
    elif hue < 300.0:
        red = secondary
        green = 0.0
        blue = chroma
    else:
        red = chroma
        green = 0.0
        blue = secondary
    return Color.from_rgb(round((red + match) * 0xFF), round((green + match) * 0xFF), round((blue + match) * 0xFF))


def rgb_to_hue(red: float, green: float, blue: float, max_rgb: float, delta: float) -> float:
    """Convert RGB color values into a hue.

    Args:
        red: Red portion of the raw RGB color value.
        green: Green portion of the raw RGB color value.
        blue: Blue portion of the raw RGB color value.
        max_rgb: Highest value from the RGB color value.
        delta: Difference between lowest and highest RGB color value.

    Returns:
        Degree on a color wheel representing the color.
    """
    hue = float("nan")
    if max_rgb == 0.0:
        hue = 0.0
    elif max_rgb == red:
        hue = 60.0 * (((green - blue) / delta) % 6)
    elif max_rgb == green:
        hue = 60.0 * (((blue - red) / delta) + 2)
    elif max_rgb == blue:
        hue = 60.0 * (((red - green) / delta) + 4)
    return 0.0 if math.isnan(hue) else hue


def parse_color(value: str | int | float | Colors) -> Color:
    """Helper to translate numerical values into a raw color int.

    Args:
        value: Numerical value, or string numerical value, representing a raw color. e.g. 0xff0000, '#ff0000', 16711680

    Returns:
        Translated value wrapped in Color int.
    """
    if isinstance(value, Color):
        return value
    if isinstance(value, Colors):
        return value.value
    if isinstance(value, (int, float)):
        return Color(value)
    if isinstance(value, str):
        raw_color = value.replace("#", "0x")
        return Color(raw_color, base=16)
    raise ValueError(f"{value} is not a valid color/int value")
