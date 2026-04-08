"""Tests for LCDController frame diffing logic (with stubbed CharLCD)."""

from unittest.mock import MagicMock, patch

import pytest


def _make_controller():
    """Build an LCDController with a mocked CharLCD backend."""
    # Import inside the function so the conftest stubs are fully in place.
    from lcd.lcd import LCDController

    with patch("lcd.lcd.CharLCD") as fake_cls:
        fake = MagicMock()
        fake_cls.return_value = fake
        ctrl = LCDController(i2c_addr=0x27)
        # fake_cls.return_value guarantees __init__ stored `fake` as _lcd.
        assert ctrl._lcd is fake
        return ctrl, fake


class TestWriteDiffing:
    def test_first_write_performs_clear_and_writes_all_rows(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])

        fake.clear.assert_called_once()
        assert fake.write_string.call_count == 2
        # First frame is cached
        assert ctrl._last_frame == ["hello", "world"]

    def test_identical_second_write_is_noop(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        fake.reset_mock()

        ctrl.write(["hello", "world"])

        fake.clear.assert_not_called()
        fake.write_string.assert_not_called()

    def test_partial_change_writes_only_changed_row(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        fake.reset_mock()

        ctrl.write(["hello", "earth"])

        fake.clear.assert_not_called()
        assert fake.write_string.call_count == 1
        # Verify the actual changed row was written (not the unchanged one).
        written = fake.write_string.call_args_list[0].args[0]
        assert written.rstrip() == "earth"

    def test_force_triggers_full_rewrite_even_if_same(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        fake.reset_mock()

        ctrl.write(["hello", "world"], force=True)

        fake.clear.assert_called_once()
        assert fake.write_string.call_count == 2

    def test_row_count_change_triggers_full_rewrite(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        fake.reset_mock()

        ctrl.write(["just one"])

        fake.clear.assert_called_once()
        assert fake.write_string.call_count == 1

    def test_written_lines_are_padded_to_full_width_with_spaces(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hi", "bye"])

        # Every write_string call should receive a COLS-char string padded
        # with spaces (not NULs, tabs, or any other character). ljust(COLS)
        # is the production contract — verify it byte-for-byte.
        written = [call.args[0] for call in fake.write_string.call_args_list]
        assert written == ["hi".ljust(ctrl.COLS), "bye".ljust(ctrl.COLS)]

    def test_string_input_accepted(self):
        ctrl, fake = _make_controller()
        ctrl.write("single line")
        assert ctrl._last_frame == ["single line"]

    def test_too_many_rows_raises(self):
        ctrl, _ = _make_controller()
        with pytest.raises(ValueError):
            ctrl.write(["a", "b", "c"])

    def test_clear_resets_cache(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        ctrl.clear()
        assert ctrl._last_frame == []
        fake.reset_mock()

        # Next write should be a full rewrite, not a no-op.
        ctrl.write(["hello", "world"])
        fake.clear.assert_called_once()


class TestReinit:
    def test_reinit_clears_frame_cache(self):
        ctrl, _ = _make_controller()
        ctrl.write(["hello", "world"])
        assert ctrl._last_frame == ["hello", "world"]

        with patch("lcd.lcd.CharLCD") as new_cls:
            new_cls.return_value = MagicMock()
            ctrl.reinit()

        assert ctrl._last_frame == []

    def test_reinit_replaces_backing_lcd(self):
        ctrl, old_fake = _make_controller()
        ctrl.write(["hello", "world"])

        with patch("lcd.lcd.CharLCD") as new_cls:
            new_fake = MagicMock()
            new_cls.return_value = new_fake
            ctrl.reinit()

        assert ctrl._lcd is new_fake
        assert ctrl._lcd is not old_fake

    def test_reinit_swallows_close_failure(self):
        ctrl, old_fake = _make_controller()
        # Make the old handle raise when closed — reinit must still replace it.
        old_fake.close.side_effect = OSError("i2c bus gone")

        with patch("lcd.lcd.CharLCD") as new_cls:
            new_fake = MagicMock()
            new_cls.return_value = new_fake
            ctrl.reinit()  # must not raise

        assert ctrl._lcd is new_fake

    def test_write_after_reinit_is_full_rewrite_not_noop(self):
        ctrl, _ = _make_controller()
        ctrl.write(["hello", "world"])

        with patch("lcd.lcd.CharLCD") as new_cls:
            new_fake = MagicMock()
            new_cls.return_value = new_fake
            ctrl.reinit()

        # After reinit, _last_frame is empty so the same frame should be
        # written in full (clear + two write_string calls), not short-circuited.
        ctrl.write(["hello", "world"])
        new_fake.clear.assert_called_once()
        assert new_fake.write_string.call_count == 2
