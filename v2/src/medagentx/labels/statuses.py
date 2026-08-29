"""Canonical status values shared by label policies and evaluation."""

from enum import Enum


class LabelStatus(str, Enum):
    """A validated CheXpert observation status."""

    PRESENT = "present"
    ABSENT = "absent"
    UNCERTAIN = "uncertain"
    UNMENTIONED = "unmentioned"
