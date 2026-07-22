import rawpy
from tkinter import filedialog
import numpy as np
import tkinter as tk
from pathlib import Path
import os
import tifffile
from concurrent.futures import ProcessPoolExecutor, as_completed
from PIL import Image
import exifread
import subprocess

EXIFTOOL_PATH = r"F:/segmentationDataset/paralelizar_bayer/exiftool-13.52_64/exiftool.exe"


def load_data():
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Please, selecte folder with DNG files")
    return Path(folder)

def copy_datetime_metadata(dng_path, jpg_path):
    cmd = [
        EXIFTOOL_PATH,
        "-overwrite_original",
        "-TagsFromFile", str(dng_path),
        "-DateTimeOriginal",
        "-CreateDate",
        "-ModifyDate",
        str(jpg_path)
    ]

    subprocess.run(cmd, check=True)

def demosaicking(file,output_dir_jpg):
    img_raw = rawpy.imread(str(file))    
    img = (
            img_raw.postprocess(
                output_bps=16,
                #no_auto_bright=False,
                #auto_bright_thr=10,
                four_color_rgb = True, #Establece independencia entre los canales G del RGGB
                demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                output_color=rawpy.ColorSpace.sRGB,
                fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
                highlight_mode=rawpy.HighlightMode.Clip, #El maximo de los factores de WB (Comparando R,G,B) es igual al minimo
                no_auto_scale = False, #Control para ejecutar funcion scale_colors() que contiene correccion nivel negro, use_auto_wb, user_wv   use_camera_wb. Sin esta, no se realiza nigun Wb_correction y queda con valores lineales de sensor

                #use_camera_wb=True, #Usa el balance de blancos que la camara guarda en RAW
                use_auto_wb=True, 
                #Calculo de multiplicadores de white balanceing con rawpy. Utiliza el greybox (Region donde hay colores neutros) y analiza imagen por bloques de 8x8 , 
                # suma colores dentro del bloque por cada canal y descarta bloques saturados, resta nivel de negro, y valores negativos quedan en 0 y calcula promedio por cada canal. 
                # Los factores de WB serian el inverso del promedio (1/promedio) y realiza un clipping value despues de multiplicar los pixels por los WB factors normalizados (WBfacor por canal / max wbfactor) 
           
                #user_wb=[1.0, 1.0, 1.0, 1.0],
                #user_black=1,
                #bright = 1,
                gamma=(2.22, 4.5),  
                #user_sat=(2**16 - 1),
            )
        
        )

    low_val = np.percentile(img, 2)
    high_val = np.percentile(img, 98)
    img = np.clip(img, low_val, high_val)
    img = (img - low_val) / (high_val - low_val)    


  #  tiff_path = output_dir_tiff / (
   #         f"{file.stem}.tiff"
    #    )
    #tifffile.imwrite(str(tiff_path), (img * 65535).astype(np.uint16))
    
    jpg_path = output_dir_jpg / (
            f"{file.stem}.jpg"
        )
    Image.fromarray((img * 255).astype(np.uint8), mode="RGB").save(jpg_path, format="JPEG", quality=95)
    copy_datetime_metadata(file, jpg_path)
    img_raw.close()
    

    return "ok", {"file_name": file.name}

    

def process_folder_parallel(input_dir: Path, max_workers: int | None = None):

   # output_dir_tiff = input_dir.parent  /  "tiff_gamma"
    #output_dir_tiff.mkdir(parents=True, exist_ok=True)

    output_dir_jpg = input_dir.parent  /  "jpg_gamma"
    output_dir_jpg.mkdir(parents=True, exist_ok=True)

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
             #   output_dir_tiff,
                output_dir_jpg
            ): raw_path
            for raw_path in dng_files
        }
        for future in as_completed(futures):
            status, metadata = future.result()
            print(f"  {metadata['file_name']} → {status}")
            all_metadata.append(metadata)


    print(f"fdd demosaicked Tiffs in: {output_dir_jpg}")

    return


if __name__ == "__main__":
    folder = load_data()
    print(f"Directorio: {folder}")
    process_folder_parallel(input_dir=folder, max_workers=10)
