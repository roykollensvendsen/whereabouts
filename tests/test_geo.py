"""Directions, speed, and what is on each side of the way Roy is going."""

import time

import pytest

from whereabouts import geo as moving

#: Skuggevik, heading due east at 60 km/h.
DRIVING = moving.Fix(latitude=58.6, longitude=9.0, heading=90.0, speed=60 / 3.6, at=time.time())
STILL = moving.Fix(latitude=58.6, longitude=9.0, heading=None, speed=0.0, at=time.time())


def _thing(name, north_m, east_m, **tags):
    """A named thing this far north and east of DRIVING."""
    lat = DRIVING.latitude + north_m / 111_195
    lon = DRIVING.longitude + east_m / (111_195 * 0.5210)  # cos(58.6°)
    return {"type": "node", "lat": lat, "lon": lon, "tags": {"name": name, **tags}}


NEAR = [
    _thing("Skuggevik kirke", 200, 0, amenity="place_of_worship"),  # north: left when going east
    _thing("Holmen", -150, 20, natural="islet"),  # south: right
    _thing("Butikken", 0, 300, amenity="supermarket"),  # east: ahead
]


@pytest.mark.parametrize(
    ("said", "side"),
    [
        ("Hva er det til venstre for oss?", "venstre"),
        ("hva er det vi kjører forbi på høyre side", "høyre"),
        ("Hva er det foran oss nå", "foran"),
        ("what is that on the left", "venstre"),
        ("kjør til venstre", None),
    ],
)
def test_a_question_about_a_side_is_recognised(said, side):
    assert moving.side_asked(said) == side


def test_what_is_on_each_side_is_found_from_the_direction_of_travel():
    assert moving.on_the_side(DRIVING, "venstre", NEAR).startswith(
        "Til venstre: Skuggevik kirke, kirke, omtrent 200 meter"
    )
    assert moving.on_the_side(DRIVING, "høyre", NEAR).startswith("Til høyre: Holmen, holme")
    assert moving.on_the_side(DRIVING, "foran", NEAR).startswith(
        "Foran deg: Butikken, butikk, omtrent 300 meter"
    )
    assert "finner ikke" in moving.on_the_side(DRIVING, "bak", NEAR)


def test_standing_still_there_is_no_left_or_right():
    assert "i bevegelse" in moving.on_the_side(STILL, "venstre", NEAR)


def test_where_you_are_says_the_way_and_the_speed_while_moving():
    assert (
        moving.described(DRIVING, "Skuggevik")
        == "Du er i Skuggevik, på vei øst i omtrent 60 kilometer i timen."
    )
    assert moving.described(STILL, "Skuggevik") == "Du er i Skuggevik."
