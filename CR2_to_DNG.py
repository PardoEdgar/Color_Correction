import subprocess
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog, messagebox

#DNG_CONVERTER_PATH = r"C:\Program Files\Adobe\Adobe DNG Converter\Adobe DNG Converter.exe"
DNG_CONVERTER_PATH = r"F:\segmentationDataset\paralelizar_bayer\Adobe\Adobe DNG Converter\Adobe DNG Converter.exe"
USE_FOLDER_DIALOG = True   # usar o no INPUT_DIR directamente
INPUT_DIR = [
    Path("F:/photos/Canales_17_August_2025/Canales_17_August_2025_0to25/CR2"),
    Path("F:/photos/MogoMogo_31_July_2025/MogoMogo_31_July_2025_0to25/CR2"),
]

def select_input_dir() -> list[Path]:
    folders = []
    while True:
        root = tk.Tk()
        root.withdraw()
        folder = filedialog.askdirectory(title="Select folder with CR2 files to convert  (Press Cancel when finished)")
        root.destroy()
        if not folder:
            break
        selected_path = Path(folder)
        # finding subfolders named "CR2" (in case the user selects a parent folder)
        cr2_subfolders = list(selected_path.rglob("CR2"))
        if not cr2_subfolders:
            print(f"no folder named 'CR2' found in: {selected_path}")
            continue

        for cr2_folder in cr2_subfolders:
            folders.append(Path(cr2_folder))
            print(f"Selected: {cr2_folder}")
    if not folders:
        raise SystemExit("No folder was selected.")
    return folders

def ask_overwrite(dng_dir: Path, existing: list[Path]) -> bool:
    root = tk.Tk()
    root.withdraw()
    answer = messagebox.askyesno(
        title="DNG ya existen",
        message=(
            f"Se encontraron {len(existing)} DNG ya existentes en:\n{dng_dir}\n\n"
            f"overwrite?"
        )
    )
    root.destroy()
    return answer

def convert_cr2_to_dng(input_path: Path, output_dir: Path) -> tuple[str, str]:
    try:
        cmd = [
            DNG_CONVERTER_PATH,
            #"-u",                    # Uncompressed desactivado para ahorrar espacio
            "-l",                    # Linear (sin transformación de color)
            "-p1",                 # la preview mas pequeña (p2 es Preview full size)
            "-d", str(output_dir),   # Directorio de salida
            str(input_path)          # CR2 de entrada
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120
        )

        if result.returncode != 0:
            return "ERROR", f"{input_path.name}: {result.stderr.decode().strip()}"

        return "OK", input_path.name

    except subprocess.TimeoutExpired:
        return "ERROR", f"{input_path.name}: Timeout"
    except Exception as e:
        return "ERROR", f"{input_path.name}: {e}"


def convert_folder_cr2_to_dng(
    input_dir:   Path,
    output_dir:  Path,
    max_workers: int | None = None
):
    output_dir.mkdir(parents=True, exist_ok=True)
    cr2_files = list(input_dir.glob("*.CR2"))

    if not cr2_files:
        print("No se encontraron archivos CR2.")
        return
    
    # Verificar DNG existentes y preguntar si sobreescribir
    existing_dngs = [output_dir / (p.stem + ".dng") for p in cr2_files if (output_dir / (p.stem + ".dng")).exists()]
    if existing_dngs:
        overwrite = ask_overwrite(output_dir, existing_dngs)
        if not overwrite:
            cr2_files = [p for p in cr2_files if not (output_dir / (p.stem + ".dng")).exists()]
            print(f"  Saltando {len(existing_dngs)} DNG existentes.")
            if not cr2_files:
                print(f"  Nada que convertir en: {input_dir}")
                return
            
    if max_workers is None:
        max_workers = max(1, os.cpu_count() - 1)

    print(f"\nConvirtiendo {len(cr2_files)} archivos CR2 → DNG  |  Workers: {max_workers}\n")


    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(convert_cr2_to_dng, p, output_dir): p
            for p in cr2_files
        }
        for future in as_completed(futures):
            status, metadata = future.result()
            print(f" {metadata}: {status}")

    print(f"DNGs guardados en: {output_dir}\n")

if __name__ == "__main__":
    cr2_dirs = select_input_dir() if USE_FOLDER_DIALOG else INPUT_DIR
    print(f"\n{len(cr2_dirs)} carpetas seleccionadas:\n")
    for cr2_dir in cr2_dirs:
        print(f"  {cr2_dir}")
    for cr2_dir in cr2_dirs:
        dng_dir = cr2_dir.parent / "DNG"
        print(f"\n── {cr2_dir.name} ──")
        convert_folder_cr2_to_dng(input_dir=cr2_dir, output_dir=dng_dir, max_workers=10)
