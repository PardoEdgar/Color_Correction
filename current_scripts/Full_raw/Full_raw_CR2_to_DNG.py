import subprocess
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog

# Path for DNG converter app
DNG_CONVERTER_PATH = r"F:\segmentationDataset\paralelizar_bayer\Adobe\Adobe DNG Converter\Adobe DNG Converter.exe"


def select_input_dir():
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select folder with CR2 images to convert")
    root.destroy()
    if not folder:
        raise SystemExit("No folder was selected.")
    return folder


def convert_cr2_to_dng(input_path: Path, output_dir: Path) -> tuple[str, str]:
    try:
        # Use the terminal for conversion
        cmd = [
            DNG_CONVERTER_PATH,
            "-p1", #Preview
            "-d",
            str(output_dir),  
            str(input_path),  
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120
        )
        if result.returncode != 0:
            return "ERROR", f"{input_path.name}: {result.stderr.decode().strip()}"

        return "OK", input_path.name

    except subprocess.TimeoutExpired:
        return "ERROR", f"{input_path.name}: Timeout"
    except Exception as e:
        return "ERROR", f"{input_path.name}: {e}"


def convert_folder_cr2_to_dng(
    input_dir: Path, output_dir: Path, max_workers: int | None = None
):
    output_dir.mkdir(parents=True, exist_ok=True)
    cr2_files = list(input_dir.glob("*.CR2"))

    if not cr2_files:
        print("CR2 files not found.")
        return

    if max_workers is None:
        max_workers = max(1, os.cpu_count() - 1)

    print(
        f"\n Converting {len(cr2_files)} files CR2 → DNG  |  Workers: {max_workers}\n"
    )

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(convert_cr2_to_dng, p, output_dir): p for p in cr2_files
        }
        for future in as_completed(futures):
            status, metadata = future.result()
            print(f" {metadata}: {status}")

    print(f"DNGs saved in: {output_dir}\n")


if __name__ == "__main__":
    cr2_dir = Path(select_input_dir())
    print(f"\n{cr2_dir} is the selected directory:\n")
    dng_dir = cr2_dir.parent / "DNG"
    convert_folder_cr2_to_dng(
        input_dir=cr2_dir, output_dir=dng_dir, max_workers=os.cpu_count() - 1
    )
