from tkinter import filedialog
import exifread
import tkinter as tk
import pandas as pd
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import subprocess


def select_folder():
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select folder with DNG files")
    root.destroy()
    return Path(folder)


def get_cfa_data(filepath: Path):
    result = subprocess.run(
        [
            r"C:\Users\jandr\Downloads\exiftool-13.59_64\exiftool-13.59_64\exiftool.exe",
            "-PhotometricInterpretation",
            "-CFARepeatPatternDim",
            "-CFAPattern2",
            str(filepath),
        ],
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


def read_data(filepath: Path):
    result = {"file_name": filepath.name}
    with open(filepath, "rb") as dng_file:
        data = exifread.process_file(dng_file, details=True)
    for tag, value in sorted(data.items()):
        result[tag] = str(value)
        result["CFA_data"] = get_cfa_data(filepath)
    return result


def run_process(dng_file):
    all_exifdata = []
    with ProcessPoolExecutor(max_workers=max(1, os.cpu_count() - 1)) as executor:
        futures = {executor.submit(read_data, path): path for path in dng_file}
        for future in as_completed(futures):
            filepath = futures[future]
            exif_record = future.result()
            all_exifdata.append(exif_record)
            print(f"{filepath.name}")
    return all_exifdata


def export_metadata(all_exifdata, outputdir):
    outputdir.mkdir(parents=True, exist_ok=True)
    exifpath = outputdir / "csvexifdata.csv"
    csvexifdata = pd.DataFrame(all_exifdata)
    csvexifdata.to_csv(exifpath, index=False)


def main():
    folder = select_folder()
    dng_files = sorted(folder.glob("*.dng"))
    all_exifdata = run_process(dng_files)
    outputdir = folder.parent / f"{folder.name}_exifmetadata"
    export_metadata(all_exifdata, outputdir)


if __name__ == "__main__":
    main()
