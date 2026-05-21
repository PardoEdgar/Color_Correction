import pandas as pd
import rawpy
import numpy as np
import exifread
import csv
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog
from PIL import Image
import subprocess
import tifffile

EXIFTOOL_PATH = r"F:/segmentationDataset/paralelizar_bayer/exiftool-13.52_64/exiftool.exe"

def select_input_dir() -> Path:
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select folder with DNG files")
    root.destroy()
    if not folder:
        raise SystemExit("No folder was selected.")
    return Path(folder)

def select_csv_file() -> Path:
    root = tk.Tk()
    root.withdraw()
    file = filedialog.askopenfilename(
        title="Select input CSV with white balancing factors",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    root.destroy()
    if not file:
        raise SystemExit("No CSV file was selected.")
    return Path(file)

def check_output_dirs_are_safe(output_dir_gamma_tiff: Path, output_dir_non_gamma_tiff: Path):
    for output_dir in [output_dir_gamma_tiff, output_dir_non_gamma_tiff]:
        if output_dir.exists():
            with_tiff = any(output_dir.glob("*.tiff"))
            if with_tiff:
                raise SystemExit(
                    f"\noutput dir '{output_dir}' This directory already contains files (tiff).\n"
                )
            
def copy_metadata_single(dng_path: Path, output_path: Path):
    cmd = [
        EXIFTOOL_PATH,
        "-overwrite_original",
        "-TagsFromFile", str(dng_path),
        "-all:all",
        "-unsafe",
        "-F",
        str(output_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def process_dng_image(input_path: Path, output_dir_gamma_tiff: Path, output_dir_non_gamma_tiff: Path, wb_factors: np.ndarray, high_val: float):
    try:
        # Date (EXIF)
        Date = "N/A"
        try:
            with open(input_path, "rb") as f:
                tags = exifread.process_file(f, stop_tag="EXIF DateTimeOriginal", details=False)
                if "EXIF DateTimeOriginal" in tags:
                    Date = str(tags["EXIF DateTimeOriginal"])
                    Date = Date.replace(":","/",2)
        except Exception:
            pass

        img_raw = rawpy.imread(str(input_path))

        # Extracting important metadata.
        white_level = img_raw.white_level
        black_level = np.array(img_raw.black_level_per_channel[:3], dtype=np.float64)
        cam2sRGB    = img_raw.color_matrix[:, :3]

        img = img_raw.postprocess(
            output_color          = rawpy.ColorSpace.raw,
            output_bps            = 16,
            no_auto_bright        = True,
            fbdd_noise_reduction  = rawpy.FBDDNoiseReductionMode.Off,
            highlight_mode        = rawpy.HighlightMode.Ignore,
            adjust_maximum_thr    = 0,
            use_camera_wb         = False,
            use_auto_wb           = False,
            user_wb               = [1.0, 1.0, 1.0, 1.0],
            user_black            = 0,
            user_sat              = (2**16 - 1),
            gamma                 = (1.0, 1.0)).astype(np.float64)

        # White and black level adjustment.
        img = (img - black_level) / (white_level - black_level)
        img = np.clip(img, 0, 1)

        # WB factors from CSV.
        img = img * wb_factors
        img = np.clip(img, 0, 1)

        # Color transform from the camera color space to the LINEAR sRGB color space.
        img = img @ cam2sRGB.T
        img = np.clip(img, 0, 1)

        # Save non_gamma TIFF.
        tiff_non_gamma_path = output_dir_non_gamma_tiff / (input_path.stem + ".tiff")
        tifffile.imwrite(str(tiff_non_gamma_path), (img * 65535).astype(np.uint16))
        copy_metadata_single(input_path, tiff_non_gamma_path)

        # Gamma correction.
        img = np.power(img, 1.0 / 2.2)
        img = np.clip(img, 0, 1)

        # Contrast stretching con high_val tambien desde CSV.
        low_val  = np.percentile(img, 2)
        #high_val = np.percentile(img, 98) #comentado porque se toma desde CSV
        img = np.clip(img, low_val, high_val)
        img = (img - low_val) / (high_val - low_val)

        # Guardar gamma tiff.
        tiff_gamma_path = output_dir_gamma_tiff / (input_path.stem + ".tiff")
        tifffile.imwrite(str(tiff_gamma_path), (img * 65535).astype(np.uint16))
        copy_metadata_single(input_path, tiff_gamma_path)

        metadata = {
            "file_name" : input_path.name,
            "Date"     : Date,
            "wbfactor_R"     : float(wb_factors[0]),
            "wbfactor_G"     : float(wb_factors[1]),
            "wbfactor_B"     : float(wb_factors[2]),
            "high_val"      : float(high_val),
        }
        return "OK", metadata

    except Exception as e:
        return f"ERROR: {e}", {"file_name": input_path.name, "Date": "N/A"}


def process_folder_parallel(input_dir: Path, max_workers: int | None = None):

    output_dir_gamma_tiff  = input_dir.parent / f"Tiff_gamma" ##{input_dir.name}_JPG_GW o GW_CHC o CGW_CHC
    output_dir_non_gamma_tiff = input_dir.parent / f"TIFF_non_gamma"##

    #Protección sobreescribir carpetas
    check_output_dirs_are_safe(output_dir_gamma_tiff, output_dir_non_gamma_tiff)

    output_dir_gamma_tiff.mkdir(parents=True, exist_ok=True)
    output_dir_non_gamma_tiff.mkdir(parents=True, exist_ok=True)

    # Cargar CSV desde DNG.
    csv_path = select_csv_file()
    if not csv_path.exists():
        raise SystemExit(f"not found CSV in : {csv_path}") 

    df = pd.read_csv(csv_path)
    columnas_requeridas = {"file_name", "wbfactor_R", "wbfactor_G", "wbfactor_B", "high_val"}
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"CSV dosn't have the required columns: {faltantes}")

    wb_lookup = {
        Path(row["file_name"]).stem: (np.array([row["wbfactor_R"], row["wbfactor_G"], row["wbfactor_B"]]), float(row["high_val"])) 
        for _, row in df.iterrows()
    }
    print(f"CSV cargado: {len(wb_lookup)} entradas desde {csv_path.name}")

    dng_files = list(input_dir.glob("*.dng"))
    sin_wb    = [f for f in dng_files if f.stem not in wb_lookup]
    if sin_wb:
        print(f"\n  {len(sin_wb)} archivos sin entrada en CSV:")
        for f in sin_wb:
            print(f"    {f.name}")

    dng_files = [f for f in dng_files if f.stem in wb_lookup]

    if not dng_files:
        print("No hay archivos DNG para procesar.")
        return

    if max_workers is None:
        max_workers = max(1, os.cpu_count() - 1)

    print(f"\nProcesando {len(dng_files)} imágenes con {max_workers} procesos\n")

    all_metadata = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                process_dng_image,
                raw_path,
                output_dir_gamma_tiff,
                output_dir_non_gamma_tiff,
                wb_lookup[raw_path.stem][0], #wb_factors
                wb_lookup[raw_path.stem][1]  #high_val
            ): raw_path
            for raw_path in dng_files
        }
        for future in as_completed(futures):
            status, metadata = future.result()
            print(f"  {metadata['file_name']} → {status}")
            all_metadata.append(metadata)

    # Guardar CSV de salida en DNG.
    if all_metadata:
        out_csv = output_dir_gamma_tiff / "metadata_applied.csv"
        fieldnames = list(all_metadata[0].keys())
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=",")
            writer.writeheader()
            writer.writerows(all_metadata)
        print(f"\nCSV guardado in: {out_csv}")

    print(f"Gamma corrected Tiffs in: {output_dir_gamma_tiff}")
    print(f"Non gamma corrected Tiffs in: {output_dir_non_gamma_tiff}\n")


if __name__ == "__main__":
    input_dir = select_input_dir()
    print(f"Directorio: {input_dir}")
    process_folder_parallel(input_dir=input_dir, max_workers=10)
