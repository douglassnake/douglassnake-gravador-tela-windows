"""Pure-function checks for compact UI sizing and mouse wheel behavior (headless)."""
import unittest
from gravador_v27_ui import initial_window_geometry, mousewheel_units


class InterfaceLayoutTests(unittest.TestCase):
    def test_laptop_1366x768(self):
        self.assertEqual(initial_window_geometry(1366, 768), (1100, 658))

    def test_desktop_1920x1080(self):
        self.assertEqual(initial_window_geometry(1920, 1080), (1100, 780))

    def test_smaller_screen(self):
        self.assertEqual(initial_window_geometry(1024, 720), (924, 610))

    def test_floor_for_narrow_screens(self):
        self.assertEqual(initial_window_geometry(800, 600), (900, 570))

    def test_windows_wheel_one_tick(self):
        self.assertEqual(mousewheel_units(-120), 1)
        self.assertEqual(mousewheel_units(120), -1)

    def test_windows_wheel_multiple_ticks(self):
        self.assertEqual(mousewheel_units(-360), 3)
        self.assertEqual(mousewheel_units(240), -2)

    def test_touchpad_fractional_tick(self):
        self.assertEqual(mousewheel_units(-1), 1)
        self.assertEqual(mousewheel_units(1), -1)

    def test_large_wheel_step_is_bounded(self):
        self.assertEqual(mousewheel_units(-10000), 6)
        self.assertEqual(mousewheel_units(10000), -6)

    def test_linux_wheel_buttons(self):
        self.assertEqual(mousewheel_units(0, 4), -3)
        self.assertEqual(mousewheel_units(0, 5), 3)

    def test_no_wheel(self):
        self.assertEqual(mousewheel_units(0), 0)


if __name__ == '__main__':
    unittest.main()
