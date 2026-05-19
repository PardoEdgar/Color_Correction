import subprocess
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog, messagebox

DNG_CONVERTER_PATH = r"F:\segmentationDataset\paralelizar_bayer\Adobe\Adobe DNG Converter\Adobe DNG Converter.exe"  # DNG_CONVERTER_PATH = r"C:\Program Files\Adobe\Adobe DNG Converter\Adobe DNG Converter.exe"


def select_input_dir():
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(
        title="Select folder with CR2 images to convert  (Press Cancel when finished)"
    )
    root.destroy()
    if not folder:
        raise SystemExit("No folder was selected.")
    return folder


def ask_overwrite(dng_dir: Path, existing: list[Path]) -> bool:
    root = tk.Tk()
    root.withdraw()
    answer = messagebox.askyesno(
        title="DNGs already exist",
        message=(f"{len(existing)} DNGs were found in:\n{dng_dir}\n\noverwrite?"),
    )
    root.destroy()
    return answer


def convert_cr2_to_dng(input_path: Path, output_dir: Path) -> tuple[str, str]:
    try:
        cmd = [
            DNG_CONVERTER_PATH,
            # "-u", # Uncompressed disabled to save space
            "-l",  # Linear (Wihout color transformation)
            "-p1",  # The preview is smaller  (p2 is a full size Preview)
            "-d",
            str(output_dir),  # Output directory
            str(input_path),  # Input path of CR2
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

    # Verify existing DNGs and ask overwrite
    existing_dngs = [
        output_dir / (p.stem + ".dng")
        for p in cr2_files
        if (output_dir / (p.stem + ".dng")).exists()
    ]
    if existing_dngs:
        overwrite = ask_overwrite(output_dir, existing_dngs)
        if not overwrite:
            cr2_files = [
                p for p in cr2_files if not (output_dir / (p.stem + ".dng")).exists()
            ]
            print(f"  Skipping {len(existing_dngs)} existing DNGs.")
            if not cr2_files:
                print(f" Nothing to convert in: {input_dir}")
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
