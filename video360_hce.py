# -*- coding: utf-8 -*-
"""Video360 AI / HCE 0.1 - inventario e sondagens locais, sem alterar drivers.

Python stdlib; em sistemas nao Windows, diagnostico apenas informa a limitacao.
Uma DLL, um nome de GPU ou um encoder listado NAO comprovam compatibilidade.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
PROBE_VERSION = "0.1.0"
ENCODERS = ("h264_nvenc", "h264_qsv", "h264_amf", "libx264")
VALID_STATES = ("supported", "unsupported", "unavailable", "untested")
CIM_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors, Manufacturer
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, TotalVisibleMemorySize, FreePhysicalMemory
$gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name, PNPDeviceID, DriverVersion, AdapterRAM, VideoProcessor, Status)
[pscustomobject]@{cpu=$cpu; os=$os; gpus=$gpus} | ConvertTo-Json -Compress -Depth 5
"""


def state(value: str, detail: str, **extra: Any) -> dict[str, Any]:
    if value not in VALID_STATES:
        raise ValueError(f"Estado invalido: {value}")
    return {"status": value, "detail": detail[:500], **extra}


def run_command(argv: list[str], timeout: int = 12) -> tuple[int, str, str]:
    """Sem shell, com limite de tempo e sem usar entradas capturadas do usuario."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                           timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode, p.stdout[:128000], p.stderr[-3000:]
    except FileNotFoundError:
        return 127, "", "Ferramenta ausente"
    except subprocess.TimeoutExpired:
        return 124, "", "Tempo limite excedido"
    except (OSError, ValueError) as exc:
        return 126, "", f"Falha ao executar: {type(exc).__name__}"


def _objects(value: Any) -> list[dict]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def _number(value: Any) -> int | None:
    try:
        n = int(value)
        return n if n >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def parse_cim_output(output: str) -> dict[str, Any]:
    """Suporta inventario de 1 ou multiplas GPUs; RAM do CIM vem em KiB."""
    try:
        raw = json.loads(output)
    except (ValueError, TypeError) as exc:
        raise ValueError("Resposta CIM nao e JSON valido") from exc
    if not isinstance(raw, dict):
        raise ValueError("Inventario CIM deve ser um objeto")
    cpu = next(iter(_objects(raw.get("cpu"))), {})
    windows = next(iter(_objects(raw.get("os"))), {})
    gpus = []
    for item in _objects(raw.get("gpus")):
        # Win32_VideoController.AdapterRAM e DWORD, nao e medida confiavel de VRAM.
        ram = _number(item.get("AdapterRAM"))
        gpus.append({
            "name": str(item.get("Name") or "Nao identificado")[:180],
            "pnp_device_id": str(item.get("PNPDeviceID") or "")[:300],
            "driver_version": str(item.get("DriverVersion") or "")[:100],
            "video_processor": str(item.get("VideoProcessor") or "")[:180],
            "status_reported": str(item.get("Status") or "")[:60],
            "adapter_ram_reported_bytes": ram,
            "adapter_ram_reliable": False,
        })
    total = _number(windows.get("TotalVisibleMemorySize"))
    free = _number(windows.get("FreePhysicalMemory"))
    return {
        "cpu": {
            "name": str(cpu.get("Name") or "Nao identificado")[:180],
            "manufacturer": str(cpu.get("Manufacturer") or "")[:100],
            "physical_cores_reported": _number(cpu.get("NumberOfCores")),
            "logical_processors_reported": _number(cpu.get("NumberOfLogicalProcessors")),
            "simd_avx2": state("untested", "CPUID/XGETBV nao verificados nesta etapa"),
        },
        "memory": {
            "total_bytes": total * 1024 if total is not None else None,
            "available_bytes": free * 1024 if free is not None else None,
            "source": "Win32_OperatingSystem (KiB)",
        },
        "os": {"name": str(windows.get("Caption") or "")[:180],
               "version": str(windows.get("Version") or "")[:80]},
        "gpus": gpus,
    }


def collect_windows_inventory(command=run_command) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    ps = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not ps:
        return None, state("unavailable", "PowerShell nao localizado; inventario CIM nao executado")
    rc, output, error = command([ps, "-NoProfile", "-NonInteractive", "-Command", CIM_SCRIPT], timeout=18)
    if rc:
        return None, state("unavailable", f"CIM nao respondeu: {error[:160]} (codigo {rc})")
    try:
        return parse_cim_output(output), state("supported", "Inventario obtido via Windows CIM")
    except ValueError as exc:
        return None, state("unavailable", str(exc))


def detect_ffmpeg() -> str | None:
    """Nao faz download nem instala FFmpeg ou pacotes Python."""
    try:
        import imageio_ffmpeg  # type: ignore
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(path).is_file():
            return path
    except (ImportError, OSError, RuntimeError):
        pass
    return shutil.which("ffmpeg")


def parse_encoders(text: str) -> set[str]:
    return set(re.findall(r"(?m)^\s*V\S*\s+(h264_(?:nvenc|qsv|amf)|libx264)\s", text))


def probe_encoder(ffmpeg: str, codec: str, command=run_command) -> dict[str, Any]:
    if codec not in ENCODERS:
        raise ValueError("Codec nao autorizado")
    argv = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "lavfi", "-i", "color=c=black:s=128x128:r=30",
            "-frames:v", "3", "-an", "-pix_fmt", "yuv420p", "-c:v", codec,
            "-f", "null", "-"]
    rc, _out, err = command(argv, timeout=12)
    if rc == 0:
        return state("supported", "Codificacao sintetica de 3 quadros executada", probed=True)
    if rc in (124, 126, 127):
        return state("unavailable", f"Falha na sondagem: {err[:220]}", probed=True)
    return state("unsupported", "Codificacao sintetica falhou no ambiente atual", probed=True,
                 error_excerpt=err[-300:])


def probe_ffmpeg(ffmpeg: str | None, command=run_command) -> dict[str, Any]:
    result: dict[str, Any] = {"path": ffmpeg, "codecs": {}, "acceleration_listed": [], "decode": {}}
    if not ffmpeg:
        result["status"] = state("unavailable", "FFmpeg nao encontrado; nenhum codec testado")
        result["codecs"] = {codec: state("untested", "FFmpeg ausente") for codec in ENCODERS}
        return result
    rc, stdout, stderr = command([ffmpeg, "-hide_banner", "-encoders"], timeout=12)
    if rc != 0:
        result["status"] = state("unavailable", f"Falha ao consultar FFmpeg: {stderr[:180]}")
        result["codecs"] = {codec: state("untested", "Lista de codificadores indisponivel") for codec in ENCODERS}
        return result
    listed = parse_encoders(stdout)
    result["status"] = state("supported", "FFmpeg respondeu a consulta de codificadores")
    for codec in ENCODERS:
        result["codecs"][codec] = (probe_encoder(ffmpeg, codec, command=command) if codec in listed
                                   else state("unsupported", "Codificador nao incluído neste FFmpeg", probed=False))
    rc, stdout, _ = command([ffmpeg, "-hide_banner", "-hwaccels"], timeout=8)
    if rc == 0:
        result["acceleration_listed"] = [line.strip() for line in stdout.splitlines()
                                          if line.strip() and line.strip() != "Hardware acceleration methods:"][:32]
    result["decode"] = {
        "nvdec": state("untested", "Lista -hwaccels nao comprova decodificacao nesta GPU"),
        "qsv": state("untested", "Decodificacao real sera testada na Etapa 03"),
        "d3d11va": state("untested", "Decodificacao real sera testada na Etapa 03"),
    }
    return result


def probe_nvidia_smi(command=run_command) -> tuple[list[dict], dict]:
    exe = shutil.which("nvidia-smi.exe") or shutil.which("nvidia-smi")
    if not exe:
        return [], state("unavailable", "nvidia-smi nao encontrado; CUDA nao comprovado")
    rc, out, err = command([exe, "--query-gpu=index,name,driver_version,memory.total", "--format=csv,noheader,nounits"], timeout=10)
    if rc != 0:
        return [], state("unavailable", f"nvidia-smi indisponivel: {err[:170]}")
    rows = []
    for line in out.splitlines():
        parts = [s.strip() for s in line.split(",", 3)]
        if len(parts) != 4:
            continue
        rows.append({"index": _number(parts[0]), "name": parts[1][:180],
                     "driver_version": parts[2][:80], "memory_total_mib": _number(parts[3])})
    return rows, state("supported", "nvidia-smi consultou GPU e driver; CUDA runtime nao testado") if rows else state("unavailable", "nvidia-smi nao retornou GPUs")


def _dll_present(name: str) -> bool:
    if platform.system() != "Windows":
        return False
    root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return (root / "System32" / name).is_file()


def runtime_features() -> dict[str, Any]:
    # Existencia de DLL nao comprova suporte por hardware nem compatibilidade da GPU.
    def dll_feature(dll: str) -> dict[str, Any]:
        return state("untested" if _dll_present(dll) else "unavailable",
                     f"{dll}: {'biblioteca localizada, execucao nao testada' if _dll_present(dll) else 'biblioteca nao localizada'}")
    return {
        "directx11": dll_feature("d3d11.dll"),
        "directx12": dll_feature("d3d12.dll"),
        "directml": dll_feature("DirectML.dll"),
        "opencl": dll_feature("OpenCL.dll"),
        "vulkan": state("untested", "Vulkan sera verificado por dispositivo e driver na Etapa 03"),
        "cuda": state("untested", "Exige sonda de runtime CUDA, nao apenas GPU NVIDIA"),
        "tensor_cores": state("untested", "Depende de arquitetura e teste do provedor de IA"),
        "inference": state("untested", "Nenhum modelo de IA ou runtime instalado nesta etapa"),
    }


def hardware_report(command=run_command, system: str | None = None,
                    ffmpeg: str | None = None) -> dict[str, Any]:
    system = system or platform.system()
    output: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "hce_version": PROBE_VERSION,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "os": {"family": system, "version": platform.version()},
        "inventory": None,
        "inventory_status": state("untested", "Somente Windows e suportado nesta fase"),
        "nvidia_driver_gpus": [],
        "nvidia_status": state("untested", "Aguardando execucao no Windows"),
        "runtime_features": {},
        "ffmpeg": {},
        "privacy": {"no_video_audio_or_screenshots_collected": True,
                    "no_network_requests": True, "driver_changes": False},
        "warnings": ["Inventario e sondagens nao medem FPS ou desempenho em tempo real."],
    }
    if system != "Windows":
        output["inventory_status"] = state("unavailable", "HCE v0.1 exige Windows 10/11; nada foi sondado")
        output["runtime_features"] = {x: state("untested", "Executar no Windows") for x in
                                      ("directx11", "directx12", "directml", "opencl", "vulkan", "cuda", "tensor_cores", "inference")}
        output["ffmpeg"] = {"status": state("untested", "FFmpeg nao sondado fora do Windows"), "codecs": {}}
        return output
    inventory, inventory_status = collect_windows_inventory(command)
    output["inventory"] = inventory
    output["inventory_status"] = inventory_status
    gpus, nvidia_status = probe_nvidia_smi(command)
    output["nvidia_driver_gpus"] = gpus
    output["nvidia_status"] = nvidia_status
    output["runtime_features"] = runtime_features()
    output["ffmpeg"] = probe_ffmpeg(ffmpeg if ffmpeg is not None else detect_ffmpeg(), command)
    output["warnings"].append("AdapterRAM do CIM pode truncar VRAM; confira memory_total_mib do nvidia-smi quando disponivel.")
    return output


def save_report(path: Path, report: dict[str, Any]) -> Path:
    """Salva so quando solicitado; evita sobrescrita e deixa arquivo completo."""
    path = path.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"Arquivo ja existe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Video360 AI: HCE - diagnostico local de hardware")
    parser.add_argument("--output", type=Path, help="Caminho de saida JSON (nao sobrescreve)")
    parser.add_argument("--ffmpeg", help="Caminho FFmpeg opcional, sem shell")
    args = parser.parse_args(argv)
    report = hardware_report(ffmpeg=args.ffmpeg)
    if args.output:
        try:
            path = save_report(args.output, report)
            print(f"Relatorio salvo: {path}")
        except (OSError, ValueError) as exc:
            print(f"Erro ao salvar: {exc}", file=sys.stderr)
            return 2
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["os"]["family"] == "Windows" else 3


if __name__ == "__main__":
    raise SystemExit(main())