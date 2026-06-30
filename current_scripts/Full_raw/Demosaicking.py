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


def demosaicking(file, output_dir_tiff):
    img_raw = rawpy.imread(str(file))
    img = img_raw.raw_image_visible.astype(np.float32)
    white = img_raw.white_level
    black = img_raw.black_level_per_channel
    # R
    img[0::2, 0::2] = (img[0::2, 0::2] - black[0]) / (white - black[0])
    # G1
    img[0::2, 1::2] = (img[0::2, 1::2] - black[1]) / (white - black[1])
    # G2
    img[1::2, 0::2] = (img[1::2, 0::2] - black[3]) / (white - black[3])
    # B
    img[1::2, 1::2] = (img[1::2, 1::2] - black[2]) / (white - black[2])
    img = (
            img_raw.postprocess(
                output_bps=16,
                #no_auto_bright=False,
                #auto_bright_thr=10,
                four_color_rgb = False, #Establece independencia entre los canales G del RGGB
                demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                output_color=rawpy.ColorSpace.sRGB,
                fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
                highlight_mode=rawpy.HighlightMode.Ignore,
                use_camera_wb=False, #Usa el balance de blancos que la camara guarda en RAW
                use_auto_wb=True, #Calculo de multiplicadores con rawpy
                #user_wb=[1.0, 1.0, 1.0, 1.0],
                #user_black=1,
                bright = 2,
                no_auto_scale = False, #Usa un escalado automatico
                gamma=(2.22, 4.5),  
                #user_sat=(2**16 - 1),
            )
        
        )

    tiff_path = output_dir_tiff / (
            f"{file.stem}.tiff"
        )
    tifffile.imwrite(str(tiff_path), (img).astype(np.uint16))

    img_raw.close()

    return "ok", {"file_name": file.name}


def process_folder_parallel(input_dir: Path, max_workers: int | None = None):

    output_dir_tiff = input_dir.parent  /  "tiff_gamma"

    output_dir_tiff.mkdir(parents=True, exist_ok=True)

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
                output_dir_tiff,
            ): raw_path
            for raw_path in dng_files
        }
        for future in as_completed(futures):
            status, metadata = future.result()
            print(f"  {metadata['file_name']} → {status}")
            all_metadata.append(metadata)


    print(f"fdd demosaicked Tiffs in: {output_dir_tiff}")

    return


if __name__ == "__main__":
    folder = load_data()
    print(f"Directorio: {folder}")
    process_folder_parallel(input_dir=folder, max_workers=15)
