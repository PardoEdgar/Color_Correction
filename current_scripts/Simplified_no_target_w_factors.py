import rawpy
import numpy as np
import exifread
import csv
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog


def select_input_dir():
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select folder with DNG files")
    root.destroy()
    if not folder:
        raise SystemExit("No folder was selected.")
    return Path(folder)


def process_raw_image(input_path):
    try:
        with rawpy.imread(str(input_path)) as img_raw:
            # Date (EXIF)
            Date = "N/A"
            try:
                with open(input_path, "rb") as f:
                    tags = exifread.process_file(
                        f, stop_tag="EXIF DateTimeOriginal", details=False
                    )
                    if "EXIF DateTimeOriginal" in tags:
                        Date = str(tags["EXIF DateTimeOriginal"])
            except Exception:
                pass

            # Extracting important metadata.
            white_level = img_raw.white_level
            black_level = np.array(
                img_raw.black_level_per_channel[:3], dtype=np.float64
            )
            cam2sRGB = img_raw.color_matrix[:, :3]

            img_proc = img_raw.postprocess(
                output_color=rawpy.ColorSpace.raw,
                output_bps=16,
                no_auto_bright=True,
                fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
                highlight_mode=rawpy.HighlightMode.Ignore,
                adjust_maximum_thr=0,
                use_camera_wb=False,
                use_auto_wb=False,
                user_wb=[1.0, 1.0, 1.0, 1.0],
                user_black=0,
                user_sat=(2**16 - 1),
                gamma=(1.0, 1.0),
            ).astype(np.float64)

            # White and black level adjustment.
            img = (img_proc - black_level) / (white_level - black_level)
            img = np.clip(img, 0, 1)

            # Grey world WB factors
            rgb_avg = img.mean(axis=(0, 1))
            white_balance_factors = rgb_avg[1] / rgb_avg
            img = img * white_balance_factors
            img = np.clip(img, 0, 1)

            # Color transform from the camera color space (which is some sort of RGB) to the LINEAR sRGB color space.
            img = img @ cam2sRGB.T
            img = np.clip(img, 0, 1)

            # Gamma correction.
            img = np.power(img, 1.0 / 2.2)
            img = np.clip(img, 0, 1)

            # Contrast stretching.
            low_val = np.percentile(img, 2)
            high_val = np.percentile(img, 98)
            img = np.clip(img, low_val, high_val)
            img = (img - low_val) / (high_val - low_val)

            metadata = {
                "file_name": input_path.name,
                "Date": Date,
                "rgb_avg_R": round(float(rgb_avg[0]), 20),
                "rgb_avg_G": round(float(rgb_avg[1]),  20),
                "rgb_avg_B": round(float(rgb_avg[2]),  20),
                "wbfactor_R": round(float(white_balance_factors[0]),  20),
                "wbfactor_G": round(float(white_balance_factors[1]),  20),
                "wbfactor_B": round(float(white_balance_factors[2]),  20),
                "high_val": float(high_val),
            }

            return "OK", metadata

    except Exception as e:
        print(
            f"[DETALLE ERROR] {input_path.name}: {type(e).__name__}: {e}"
        )  # ← cambia esta línea
        return "ERROR", {
            "file_name": input_path.name,
            "Date": "N/A",
            "rgb_avg_R": None,
            "rgb_avg_G": None,
            "rgb_avg_B": None,
            "wbfactor_R": None,
            "wbfactor_G": None,
            "wbfactor_B": None,
            "high_val": None,
        }


def process_folder_parallel(
    input_dir: Path,
    max_workers: int | None = None,
):
    all_metadata = []
    raw_files = list(input_dir.glob("*.DNG"))
    if not raw_files:
        print("No se encontraron archivos DNG.")
        return

    if max_workers is None:
        max_workers = max(1, os.cpu_count() - 1)

    print(f"Calculate WB factors from {len(raw_files)} |  Workers: {max_workers}\n")

    with ProcessPoolExecutor(
        max_workers=max_workers,
    ) as executor:
        futures = {
            executor.submit(process_raw_image, raw_path): raw_path
            for raw_path in raw_files
        }
        for future in as_completed(futures):
            status, metadata = future.result()
            print(f"{metadata['file_name']}: {status}")
            all_metadata.append(metadata)

    # Save CSV
    if all_metadata:
        parent_folder_name = input_dir.parent.name
        csv_path = input_dir / f"{parent_folder_name}_GW.csv"
        fieldnames = list(all_metadata[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=",")
            writer.writeheader()
            writer.writerows(all_metadata)
        print(f"Saved CSV in: {csv_path}\n")


if __name__ == "__main__":
    input_dir = select_input_dir()
    print(f"Selected directory: {input_dir}")
    process_folder_parallel(input_dir=input_dir, max_workers=os.cpu_count() - 3)
