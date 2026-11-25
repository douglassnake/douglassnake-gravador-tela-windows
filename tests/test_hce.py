"""Teste isolado do HCE: sem dependencias ou drivers do Windows."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import video360_hce as hce

CIM = json.dumps({
    "cpu": {"Name":"Intel(R) Core(TM) i7", "NumberOfCores":4,"NumberOfLogicalProcessors":8,"Manufacturer":"GenuineIntel"},
    "os":{"Caption":"Windows 10", "Version":"10.0", "TotalVisibleMemorySize":8192000,"FreePhysicalMemory":4096000},
    "gpus":[{"Name":"NVIDIA Quadro K3100M", "DriverVersion":"1.2", "AdapterRAM":4294967295},
             {"Name":"Intel HD 4600", "DriverVersion":"9.9", "AdapterRAM":123456}]
})

class CIMTests(unittest.TestCase):
    def test_two_gpus_and_ram(self):
        data=hce.parse_cim_output(CIM)
        self.assertEqual(len(data["gpus"]), 2)
        self.assertEqual(data["memory"]["total_bytes"], 8192000 * 1024)
        self.assertEqual(data["cpu"]["logical_processors_reported"], 8)
        self.assertFalse(data["gpus"][0]["adapter_ram_reliable"])
        self.assertEqual(data["cpu"]["simd_avx2"]["status"],"untested")
    def test_single_gpu_dict(self):
        row=json.loads(CIM);row["gpus"]=row["gpus"][0]
        self.assertEqual(len(hce.parse_cim_output(json.dumps(row))["gpus"]),1)
    def test_invalid_input(self):
        for value in ("", "[]", "invalid", "null"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hce.parse_cim_output(value)
    def test_missing_fields_safe(self):
        d=hce.parse_cim_output('{"cpu":null,"os":{},"gpus":null}')
        self.assertEqual(d["gpus"], [])
        self.assertIsNone(d["memory"]["total_bytes"])

class EncoderTests(unittest.TestCase):
    def test_parse_encoders_only_video(self):
        s=" V..... h264_nvenc NVIDIA\n V..... h264_qsv INTEL\n A..... h264_amf fake\n V..... libx264 CPU\n"
        self.assertEqual(hce.parse_encoders(s),{"h264_nvenc","h264_qsv","libx264"})
    def test_probe_success(self):
        def runner(argv,timeout=12): return 0,"",""
        self.assertEqual(hce.probe_encoder("ffmpeg","h264_qsv",runner)["status"],"supported")
    def test_probe_failure(self):
        def runner(argv,timeout=12): return 1,"","Unsupported encoder"
        self.assertEqual(hce.probe_encoder("ffmpeg","h264_nvenc",runner)["status"],"unsupported")
    def test_probe_timeout(self):
        def runner(argv,timeout=12): return 124,"","timeout"
        self.assertEqual(hce.probe_encoder("ffmpeg","h264_nvenc",runner)["status"],"unavailable")
    def test_invalid_codec_not_executed(self):
        with self.assertRaises(ValueError): hce.probe_encoder("ffmpeg","injection;bad")
    def test_ffmpeg_redacts_local_path(self):
        data=hce.probe_ffmpeg(r"C:\\Users\\Profile\\AppData\\ffmpeg.exe", command=lambda argv,timeout=12:(1,"","fail"))
        self.assertEqual(data["path"], "ffmpeg.exe")
        self.assertNotIn("Profile", json.dumps(data))

    def test_ffmpeg_unavailable_has_untested(self):
        data=hce.probe_ffmpeg(None)
        self.assertEqual(data["status"]["status"],"unavailable")
        self.assertEqual(data["codecs"]["h264_nvenc"]["status"],"untested")
    def test_only_listed_codecs_probe(self):
        calls=[]
        def runner(argv,timeout=12):
            calls.append(argv)
            if argv[-1]=="-encoders":return 0," V..... libx264 CPU\n V..... h264_qsv Intel\n",""
            if argv[-1]=="-hwaccels":return 0,"Hardware acceleration methods:\nd3d11va\nqsv\n",""
            return (0,"","") if "libx264" in argv else (1,"","no hardware")
        data=hce.probe_ffmpeg("ffmpeg",runner)
        self.assertEqual(data["codecs"]["h264_nvenc"]["status"],"unsupported")
        self.assertEqual(data["codecs"]["h264_qsv"]["status"],"unsupported")
        self.assertEqual(data["codecs"]["libx264"]["status"],"supported")
        self.assertEqual(data["decode"]["nvdec"]["status"],"untested")
        self.assertEqual(len([c for c in calls if "-frames:v" in c]),2)

class SafetyTests(unittest.TestCase):
    def test_non_windows_does_not_probe(self):
        with patch.object(hce,"collect_windows_inventory",side_effect=AssertionError("CIM accessed")),\
             patch.object(hce,"probe_nvidia_smi",side_effect=AssertionError("Nvidia accessed")):
            data=hce.hardware_report(system="Linux")
        self.assertEqual(data["inventory_status"]["status"],"unavailable")
        self.assertTrue(data["privacy"]["no_network_requests"])
    def test_report_write_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"hce.json"
            hce.save_report(path,{"schema_version":1})
            with self.assertRaises(FileExistsError):hce.save_report(path,{"schema_version":2})
            self.assertEqual(json.loads(path.read_text()),{"schema_version":1})
    def test_windows_stub_not_claim_inference(self):
        def fake_cmd(argv, timeout=12):
            if "-Command" in argv:return 0,CIM,""
            if "-encoders" in argv:return 0," V..... libx264 CPU\n",""
            if "-hwaccels" in argv:return 0,"d3d11va\n",""
            return 0,"",""
        with patch.object(hce.shutil,"which",side_effect=lambda name: "powershell.exe" if name=="powershell.exe" else None),\
             patch.object(hce,"_dll_present",return_value=True),\
             patch.object(hce,"detect_ffmpeg",return_value="ffmpeg"):
            data=hce.hardware_report(command=fake_cmd,system="Windows")
        self.assertEqual(data["runtime_features"]["directml"]["status"],"untested")
        self.assertEqual(data["runtime_features"]["tensor_cores"]["status"],"untested")
        self.assertEqual(data["ffmpeg"]["codecs"]["libx264"]["status"],"supported")
        self.assertEqual(data["ffmpeg"]["codecs"]["h264_nvenc"]["status"],"unsupported")

if __name__ == "__main__": unittest.main()