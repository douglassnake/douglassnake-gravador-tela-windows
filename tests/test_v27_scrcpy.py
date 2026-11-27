"""RC4: Android USB camera without DirectShow re-capture (no physical phone needed)."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

from gravador_v27_scrcpy import (
    SCRCPY_B_SOURCE, parse_adb_devices, locate_scrcpy, check_usb_android,
    scrcpy_camera_command, gracefully_stop_camera,
)


class ScrcpyUsbTests(unittest.TestCase):
    def test_parse_devices_only_adb_states(self):
        parsed=parse_adb_devices('List of devices attached\n'
            'R58XX device usb:1-1 product:a model:Galaxy transport_id:7\n'
            '123 unauthorized usb:2-1\n127.0.0.1:5555 device product:foo\n'
            'xx offline usb:1-3\n')
        self.assertEqual(len(parsed), 4)
        self.assertTrue(parsed[0]['usb'])
        self.assertFalse(parsed[2]['usb'])
        self.assertEqual(parsed[1]['state'], 'unauthorized')

    def test_manual_path_and_no_driver_install(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'scrcpy.exe').write_bytes(b'example')
            with self.assertRaisesRegex(ValueError,'adb.exe'):
                locate_scrcpy(root/'scrcpy.exe')
            (root/'adb.exe').write_bytes(b'example')
            exe,adb=locate_scrcpy(root/'scrcpy.exe')
            self.assertEqual(exe, (root/'scrcpy.exe').resolve())
            self.assertEqual(adb, (root/'adb.exe').resolve())
            with self.assertRaises(ValueError):
                locate_scrcpy(root/'adb.exe')

    def test_authorized_usb_selected_robustly(self):
        calls=[]
        def run(args,**_kwargs):
            calls.append(args)
            if args[1:] == ['devices','-l']:
                return SimpleNamespace(returncode=0, stdout='List of devices attached\nA device usb:1-2\n',stderr='')
            if args[1:] == ['-d','get-state']:
                return SimpleNamespace(returncode=0,stdout='device\n',stderr='')
            raise AssertionError(args)
        status=check_usb_android(Path('adb.exe'),runner=run)
        self.assertTrue(status['authorized'])
        self.assertEqual(calls[1][1:],['-d','get-state'])

    def test_reject_unauthorized_and_wifi_only(self):
        def unauth(args,**kw):
            return SimpleNamespace(returncode=0,stdout='List of devices attached\nB unauthorized usb:1-2\n',stderr='')
        with self.assertRaisesRegex(ValueError,'Autorize'):
            check_usb_android(Path('adb.exe'),runner=unauth)
        def wifi(args,**kw):
            if args[1]=='devices':
                return SimpleNamespace(returncode=0,stdout='List of devices attached\n192.168.0.2:5555 device\n',stderr='')
            return SimpleNamespace(returncode=1,stdout='',stderr='no usb devices')
        with self.assertRaises(ValueError):
            check_usb_android(Path('adb.exe'),runner=wifi)

    def test_command_direct_record_sanitized(self):
        path=Path(tempfile.gettempdir()).resolve()/'video A.mkv'
        cmd=scrcpy_camera_command(Path('scrcpy.exe'),path,facing='Traseira',fluidez=True)
        self.assertIn('--select-usb',cmd)
        self.assertIn('--video-source=camera',cmd)
        self.assertIn('--camera-facing=back',cmd)
        self.assertIn('--video-codec=h264',cmd)
        self.assertIn('--no-audio',cmd)
        self.assertIn('--max-size=1280',cmd)
        self.assertIn('--record='+str(path),cmd)
        self.assertNotIn('-f',cmd)
        self.assertFalse(any('gdigrab' in arg or 'dshow' in arg for arg in cmd))
        front=scrcpy_camera_command(Path('scrcpy.exe'),path,facing='Frontal',fluidez=False)
        self.assertIn('--camera-facing=front',front)
        self.assertNotIn('--max-size=1280',front)
        with self.assertRaises(ValueError):
            scrcpy_camera_command(Path('scrcpy.exe'),path,facing='meio')
        with self.assertRaises(ValueError):
            scrcpy_camera_command(Path('scrcpy.exe'),path.with_suffix('.exe'))

    def test_no_forced_termination_if_no_window(self):
        proc=SimpleNamespace(pid=123,poll=lambda:None)
        with patch('gravador_v27_scrcpy.sys.platform','win32'), patch('gravador_v27_scrcpy._windows_for_pid',return_value=[]):
            self.assertFalse(gracefully_stop_camera(proc))


if __name__ == '__main__':
    unittest.main()
