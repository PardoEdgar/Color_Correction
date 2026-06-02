# Demosaicking comparison
import rawpy
from tkinter import filedialog
import numpy as np
import tkinter as tk
from pathlib import Path
import os
import tifffile
from concurrent.futures import ProcessPoolExecutor, as_completed


def load_data():
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Please, selecte folder with DNG files")
    return Path(folder)


def demosaicking(file, output_dir_fbdd_tiff, output_dir_nofbdd_tiff):
    available_Demos = list(rawpy.DemosaicAlgorithm)
    results_FBDD = {}
    results_non_FBDD = {}
    img_raw = rawpy.imread(str(file))
    white_level = img_raw.white_level
    black_level = np.array(img_raw.black_level_per_channel[:3], dtype=np.float64)
    for demosaickings in available_Demos:
        img_FBDD = (
            img_raw.postprocess(
                output_color=rawpy.ColorSpace.sRGB,
                output_bps=16,
                no_auto_bright=True,
                demosaic_algorithm=demosaickings,
                fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Full,
                highlight_mode=rawpy.HighlightMode.Ignore,
                adjust_maximum_thr=0,
                use_camera_wb=True,
                use_auto_wb=True,
                # user_wb=[1.0, 1.0, 1.0, 1.0],
                user_black=0,
                user_sat=(2**16 - 1),
                gamma=(1.0, 1.0),
            ).astype(np.float64)
            / 65535.0
        )

        img_FBDD = (img_FBDD - black_level) / (white_level - black_level)
        img_FBDD = np.clip(img_FBDD, 0, 1)

        img_FBDD = np.power(img_FBDD, 1.0 / 2.2)
        img_FBDD = np.clip(img_FBDD, 0, 1)

        img_non_FBDD = (
            img_raw.postprocess(
                output_color=rawpy.ColorSpace.sRGB,
                output_bps=16,
                no_auto_bright=True,
                demosaic_algorithm=demosaickings,
                fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
                highlight_mode=rawpy.HighlightMode.Ignore,
                adjust_maximum_thr=0,
                use_camera_wb=True,
                use_auto_wb=True,
                # user_wb=[1.0, 1.0, 1.0, 1.0],
                user_black=0,
                user_sat=(2**16 - 1),
                gamma=(1.0, 1.0),
            ).astype(np.float64)
            / 65535.0
        )

        img_non_FBDD = (img_non_FBDD - black_level) / (white_level - black_level)
        img_non_FBDD = np.clip(img_non_FBDD, 0, 1)

        img_non_FBDD = np.power(img_non_FBDD, 1.0 / 2.2)
        img_non_FBDD = np.clip(img_non_FBDD, 0, 1)

        results_FBDD[demosaickings.name] = img_FBDD
        results_non_FBDD[demosaickings.name] = img_non_FBDD

        img_raw.close()

        demosaicking_name = demosaickings.name
        tiff_fbdd_path = output_dir_fbdd_tiff / (
            f"{file.stem}{demosaicking_name}fbdd.tiff"
        )
        tifffile.imwrite(str(tiff_fbdd_path), (img_FBDD * 65535).astype(np.uint16))

        tiff_nofbdd_path = output_dir_nofbdd_tiff / (
            f"{file.stem}{demosaicking_name}NO_fbdd.tiff"
        )

        tifffile.imwrite(
            str(tiff_nofbdd_path), (img_non_FBDD * 65535).astype(np.uint16)
        )

    return "ok", {"file_name": file.name}


def process_folder_parallel(input_dir: Path, max_workers: int | None = None):

    output_dir_fbdd_tiff = input_dir.parent / f"fbdd"
    output_dir_nofbdd_tiff = input_dir.parent / f"non_fbdd"

    output_dir_fbdd_tiff.mkdir(parents=True, exist_ok=True)
    output_dir_nofbdd_tiff.mkdir(parents=True, exist_ok=True)

    dng_files = list(input_dir.glob("*.dng"))

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
                demosaicking,
                raw_path,
                output_dir_fbdd_tiff,
                output_dir_nofbdd_tiff,
            ): raw_path
            for raw_path in dng_files
        }
        for future in as_completed(futures):
            status, metadata = future.result()
            print(f"  {metadata['file_name']} → {status}")
            all_metadata.append(metadata)

    # Guardar CSV de salida en DNG.

    print(f"fbdd demosaicked Tiffs in: {output_dir_fbdd_tiff}")
    print(f"NONfbdd demosaicked Tiffs in: {output_dir_nofbdd_tiff}")

    return


if __name__ == "__main__":
    folder = load_data()
    print(f"Directorio: {folder}")
    process_folder_parallel(input_dir=folder, max_workers=10)
