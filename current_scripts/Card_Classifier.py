import torch
from torchvision import models
import torch.nn as nn
import rawpy
import csv
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog
import torchvision.transforms as transforms
from io import BytesIO
from PIL import Image

MODEL = None


def select_input_dir():
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select folder with DNG files")
    root.destroy()
    if not folder:
        raise SystemExit("No folder was selected.")
    return Path(folder)


def select_output_csv():
    root = tk.Tk()
    root.withdraw()
    csv_data = filedialog.askopenfilename(
        title="Select csv with colorimetric features data"
    )
    root.destroy()
    if not csv_data:
        raise SystemExit("No csv was selected.")
    return Path(csv_data)


def load_model(
    model_path="F:/segmentationDataset/paralelizar_bayer/DNG/card_classifier_4.pth",
):
    model = models.resnet50(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 2)  # Classification with 2 classes
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()  # Only prediction
    return model


def initialize_worker(model_path):
    global MODEL
    MODEL = load_model(model_path)


inference_transform_pil = transforms.Compose(
    [
        transforms.Resize((512, 512)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]
)


def predict_card_type_from_pil(img_pil, model):
    try:
        img_tensor = inference_transform_pil(img_pil)
        img_tensor = img_tensor.unsqueeze(0)
        with torch.no_grad():
            outputs = model(img_tensor)
            pred = torch.argmax(outputs, dim=1).item()
        return "Card" if pred == 1 else "No Card"
    except Exception:
        return "No Card"


def process_raw_image(input_path):
    global MODEL
    try:
        # Classification with preview
        with rawpy.imread(str(input_path)) as img_raw:
            thumb = img_raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                preview_img = Image.open(BytesIO(thumb.data)).convert("RGB")
            else:
                preview_img = Image.fromarray(thumb.data).convert("RGB")
            # Prediction
            card_type = predict_card_type_from_pil(preview_img, MODEL)

            metadata = {
                "card_type": card_type,
            }

            return "OK", metadata

    except Exception as e:
        print(
            f"[DETALLE ERROR] {input_path.name}: {type(e).__name__}: {e}"
        )  # ← cambia esta línea
        return "ERROR", {
            "card_type": "No Card",
        }


def process_folder_parallel(
    input_dir: Path,
    csv_path: Path,
    max_workers: int | None = None,
):
    with open(csv_path) as data:
        rows = {}
        for row in csv.DictReader(data):
            rows[row["file_name"]] = row

    raw_files = list(input_dir.glob("*.DNG"))
    if not raw_files:
        print("DNG files not found")
        return

    if max_workers is None:
        max_workers = max(1, os.cpu_count() - 1)

    print(f"Classifying {len(raw_files)} files | Workers: {max_workers}")

    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=initialize_worker,
        initargs=(
            "F:/segmentationDataset/paralelizar_bayer/DNG/card_classifier_4.pth",
        ),
    ) as executor:
        futures = {
            executor.submit(process_raw_image, raw_path): raw_path
            for raw_path in raw_files
        }
        for future in as_completed(futures):
            source_path = futures[future]
            filename = source_path.name
            status, metadata = future.result()

            if filename in rows:
                rows[filename]["card_type"] = metadata["card_type"]
            else:
                print(f"{filename} not found in csv")
    all_rows = list(rows.values())
    names = list(all_rows[0].keys())
    out_path = csv_path.parent / (csv_path.stem + "_classified.csv")
    with open(out_path, "w", newline="") as final_csv:
        writer = csv.DictWriter(final_csv, names)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Saved csv: {out_path}")


if __name__ == "__main__":
    input_dir = select_input_dir()
    csv_path = select_output_csv()
    process_folder_parallel(input_dir=input_dir, csv_path=csv_path)
