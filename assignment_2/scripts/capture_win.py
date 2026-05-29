"""
Windows-compatible packet capture for Task 4.

Replaces capture.sh on Windows where tshark is not in PATH and
the loopback interface name differs from Linux's 'lo'.

Usage (with MQTT publisher and CoAP server running in other terminals):
    python scripts/capture_win.py
"""

import os
import subprocess
import sys
import time

DURATION = 30
OUTDIR = "captures"
TSHARK_DEFAULT = r"C:\Program Files\Wireshark\tshark.exe"


def find_tshark() -> str:
    for candidate in [TSHARK_DEFAULT, "tshark"]:
        try:
            subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                check=True,
            )
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    sys.exit(
        "tshark not found.\n"
        "Install Wireshark: winget install Wireshark.Wireshark\n"
        f"Or verify it exists at: {TSHARK_DEFAULT}"
    )


def find_loopback_iface(tshark: str) -> str:
    out = subprocess.check_output(
        [tshark, "-D"], text=True, stderr=subprocess.DEVNULL
    )
    for line in out.splitlines():
        low = line.lower()
        if "loopback" in low or "npf_loopback" in low:
            return line.split(".")[0].strip()
    # Fallback: use the first interface listed
    first = out.splitlines()[0].split(".")[0].strip()
    print(f"  Warning: no loopback interface found, using: {first}")
    return first


def start_capture(tshark: str, iface: str, filt: str, outfile: str) -> subprocess.Popen:
    return subprocess.Popen(
        [tshark, "-i", iface, "-f", filt, "-w", outfile, "-a", f"duration:{DURATION}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    tshark = find_tshark()
    print(f"tshark: {tshark}")

    iface = find_loopback_iface(tshark)
    print(f"Interface: {iface}")

    os.makedirs(OUTDIR, exist_ok=True)

    print(f"\nStarting {DURATION}-second capture...")
    print("Make sure your MQTT publisher and CoAP server are running.\n")

    procs = [
        ("MQTT",  start_capture(tshark, iface, "port 1883",     f"{OUTDIR}/mqtt.pcap")),
        ("CoAP",  start_capture(tshark, iface, "udp port 5683", f"{OUTDIR}/coap.pcap")),
    ]

    for elapsed in range(DURATION, 0, -5):
        print(f"  {elapsed}s remaining...", flush=True)
        time.sleep(5)

    for name, proc in procs:
        proc.wait()

    print("\nCaptures written:")
    for name, _ in procs:
        fname = name.lower()
        path = f"{OUTDIR}/{fname}.pcap"
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  {path}  ({size} bytes)")
        else:
            print(f"  {path}  (MISSING — was traffic flowing?)")

    print("\n--- First 5 MQTT frames ---")
    subprocess.run(
        [tshark, "-r", f"{OUTDIR}/mqtt.pcap", "-Y", "mqtt"],
        check=False,
    )

    print("\n--- First 5 CoAP frames ---")
    subprocess.run(
        [tshark, "-r", f"{OUTDIR}/coap.pcap", "-Y", "coap", "-c", "5"],
        check=False,
    )

    print("\nTo inspect full packet detail:")
    print(f'  & "{tshark}" -r {OUTDIR}/mqtt.pcap -V -Y mqtt | more')
    print(f'  & "{tshark}" -r {OUTDIR}/coap.pcap -V | more')


if __name__ == "__main__":
    main()
